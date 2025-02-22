import pathlib
import argparse
import tempfile
import os

from collections import Counter
from datetime import datetime


# name of folder used to store temporary-files
TOPLEVEL_CACHE_NAME = "rgb_cache"


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str) -> str:
    if text.isalnum(): return text
    bad_chars = {C for C in text if ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


def PrintDict(D:dict, name=None):
    if name is not None: print(f"{name} = "+"{");
    for (k,v) in D.items(): print(f"  {k}: {v},");
    if name is not None: print("}\n")


# TODO: add parsing/env for which magick library (imagemagick/graphicsmagick) to use
# maybe add a switch for imagemagick 6/7 compat?


def ParseCmdline(arglist:list[str]|None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    #TODO: group args
    
    parser.add_argument("--tmpfs", dest="use_tmpfs", action="store_true", default=False, help="ensure all temp-files are created on a tmpfs; arg is size of tmpfs")
    parser.add_argument("--noclean", dest="autodelete", action="store_false", default=True, help="preserve temp files (deleted by default)")
    
    # parser.add_argument("--fps", dest="fps", type=int, default=60, help="FPS of RGB-ified video (default 60)")
    # TODO: duration
    # TODO: resize (scale/crop)
    # TODO: output types (gif/mp4/script)
    
    parser.add_argument("input_path", type=pathlib.Path, metavar="IMAGE_FILE")
    
    if arglist is None: parsed_args = parser.parse_args()
    else: parsed_args = parser.parse_args(arglist)
    # assert(type(parsed_args.fps) is int)
    
    print(parsed_args) # Namespace(...)
    PrintDict(parsed_args.__dict__, "args")
    return parsed_args



def SetupENV() -> dict:
    print("reading environment...")
    def VarNames(S:str): # lambda generating ImageMagick/GraphicsMagick-style environment-variables
        if (S.upper() == "THREADS"): return ("MAGICK_THREAD_LIMIT", "OMP_NUM_THREADS");
        if (S.upper() == "FILES"): return ("MAGICK_FILE_LIMIT", "MAGICK_LIMIT_FILES"); # non-plural in IM-style
        return (f"MAGICK_{S.upper()}_LIMIT", f"MAGICK_LIMIT_{S.upper()}")
        # "memory" -> [MAGICK_MEMORY_LIMIT, MAGICK_LIMIT_MEMORY]
    
    # values specified here will be exported to env if not already defined, unless the value is 'None'
    env_defaults = {
        # resources
           "DISK": "1GB",
          "FILES": 4096, # ulimit reports 1024 as soft-limit; should probably be increased (ulimit -n 4096).
            "MAP": "64GB", # normally 2x Memory-limit, for some reason
         "MEMORY": "64GB",
         "PIXELS": None, # GM-only?
        "THREADS": os.cpu_count()//2, # 'cpu_count()' reports 2 cpus per physical core (hyperthreading)
          "WIDTH": "128MP",
         "HEIGHT": "128MP",
           "AREA": None, # IM-only? suffix is 'KP/MP/GP'
           "READ": None,
          "WRITE": None,
    }
    
    # if both IM/GM-style variables are set for an entry, the last one (GM-style) will take precedence
    final_env = {
        EK: EV
        for (K,V) in env_defaults.items()
        for EV in [V, *[os.getenv(N) for N in VarNames(K)]]
        for EK in VarNames(K)
        if (EV is not None)
    }
    
    # MAGICK_DBG_SETTING: "None", "All", or comma-seperated domain list
    MAGICK_DBG_SETTING = os.getenv("MAGICK_DEBUG", "all").replace(" ","")
    MAGICK_DBG_DOMAINS = [
        'annotate','blob','cache','coder','configure',
        'deprecate','error','exception','fatalerror',
        'information','locale','option','render','resource',
        'temporaryfile','transform','user','warning','x11',
    ] # seems to be case-insensitive for GraphicsMagick
    
    # GraphicsMagick simply ignores any invalid domains, without any warnings/errors
    print(f"parsing MAGICK_DEBUG[env]: '{MAGICK_DBG_SETTING}'")
    warnings = []; shouldPrintDomains = False; dbg_setting_isvalid = (len(MAGICK_DBG_SETTING) >= 3) # shortest valid strings are 'all'/'X11'
    if (len(MAGICK_DBG_SETTING) == 0): warnings.append("MAGICK_DEBUG[env] set to empty string!!");
    elif not dbg_setting_isvalid: warnings.append(f"[WARNING] MAGICK_DEBUG[env] is invalid: '{MAGICK_DBG_SETTING}'"); shouldPrintDomains=True;
    elif ((stripped := MAGICK_DBG_SETTING.replace(',','').lower()) in ['all','none']): MAGICK_DBG_SETTING = stripped;
    else: # must be comma-seperated list of debug-domains
        checked_domains = {
            W.lower(): (W.lower() in ['all', 'none', *MAGICK_DBG_DOMAINS])
            for W in MAGICK_DBG_SETTING.split(',') if (len(W) > 0)
        }
        # GraphicsMagick seems to ignore 'none' when any other flags are present, and 'all' takes precedence. Order doesn't seem to matter.
        exclusive_domains = [EXD for EXD in ['all','none'] if (EXD in checked_domains.keys())]
        invalid_domains = [K for (K,V) in checked_domains.items() if (not V)]
        normal_domains = [K for (K,V) in checked_domains.items() if (V and (K not in exclusive_domains))]
        assert((len(exclusive_domains) + len(invalid_domains) + len(normal_domains)) > 0), "domains should not be empty here";
        
        # normally, the exclusive-domains would be omitted; but the first one should be kept if there are no other valid domains
        if (len(normal_domains) == 0): normal_domains = exclusive_domains[:1];
        MAGICK_DBG_SETTING = ','.join(normal_domains)
        
        warnings.extend([f"[WARNING] MAGICK_DEBUG[env]: unrecognized domain: '{K}'" for K in invalid_domains])
        warnings.extend([f"[WARNING] MAGICK_DEBUG[env]: exclusive domain '{EXD}' should not be specified with other domains!" for EXD in exclusive_domains])
        shouldPrintDomains = (len(invalid_domains) > 0)
        dbg_setting_isvalid = (
            ((len(normal_domains) > 0) or (len(exclusive_domains) == 1)) and
            ((len(exclusive_domains) < len(normal_domains)) or (len(exclusive_domains) == 1))
        ) # WTF am I doing (works perfectly LMAO)
    
    if (len(warnings) > 0):
        for warning in warnings: print(f" {warning}");
        if ((not dbg_setting_isvalid) and (len(MAGICK_DBG_SETTING) <= 3)): MAGICK_DBG_SETTING="none";
        if shouldPrintDomains:
            print("[WARNING] invalid domain in MAGICK_DEBUG[env]!\nAvailable (unused) domains are: ")
            print('\n'.join(f" {D.title()}" for D in MAGICK_DBG_DOMAINS if D not in MAGICK_DBG_SETTING),end="\n\n")
    
    print(f"using MAGICK_DEBUG:'{MAGICK_DBG_SETTING}'")
    final_env["MAGICK_DEBUG"] = (MAGICK_DBG_SETTING)
    
    config_dir = os.getenv("MAGICK_CONFIGURE_PATH", (pathlib.Path.cwd()/"magick_configs").absolute())
    if (config_dir.exists() and config_dir.is_dir()): final_env["MAGICK_CONFIGURE_PATH"] = str(config_dir);
    else: print(f"[WARNING] bad path for 'MAGICK_CONFIGURE_PATH': {config_dir}");
    
    # adds info about file-access to '-monitor' output (including temporary files); "TRUE"/"FALSE"
    final_env["MAGICK_ACCESS_MONITOR"] = str(os.getenv("MAGICK_ACCESS_MONITOR", True)).upper()
    
    print("updating magick environment variables...\n")
    PrintDict(env_defaults, name="defaults")
    PrintDict(final_env, name="environment")
    for (K,V) in final_env.items():
        os.putenv(K,str(V))  # doesn't update 'os.environ'
        os.environ[K] = str(V) # modifying this automatically calls 'putenv', supposedly
    
    return final_env



# GraphicsMagick does not provide any mechanism for specifying a relative-path for logfile, except for subdirectories under CWD.
# variable-expansion / substitution does not appear to be possible. Changing the path at runtime does not seem (reasonably) possible.
# If the path contains a directory, that directory must already exist, otherwise the logfile will simply not be written (silent failure; no warnings, of course)
# also, the mechanisms for writing numbered logfiles are only triggered by the event-limit (see log.mgk);
# otherwise, GraphicsMagick just overwrites the same logfile on every single run.
# TODO: come up with some workaround to switch paths between cache under tmpdir/cwd. maintain a symlink under cwd?
def RotateMagickLogs(toplevel_cache_dir:pathlib.Path) -> pathlib.Path:
    """
    Create logging directory and rename existing logs.
    Assumes that GraphicsMagick's logging-config (log.mgk) has 'filename' set to: "/tmp/rgb_cache/magicklogs/magickrgb_%d.log"
    :param toplevel_cache_dir: the directory referred to by 'TOPLEVEL_CACHE_NAME'
    :return: path to log-directory
    """
    assert(toplevel_cache_dir.name == TOPLEVEL_CACHE_NAME), "expected log-directory to be under toplevel cache"
    assert(toplevel_cache_dir.is_relative_to("/tmp/")), "reminder to change path in 'log.mgk'";
    
    new_logdir = toplevel_cache_dir / "magicklogs"
    if new_logdir.exists(): assert(new_logdir.is_dir()), "existing log-directory was not actually a directory!?"
    else: new_logdir.mkdir(); print(f"created log-directory: '{new_logdir}'");
    
    stale_logs:list[pathlib.Path] = [F for F in new_logdir.glob("magickrgb_*.log.old") if (not F.is_dir())]
    fresh_logs:list[pathlib.Path] = [F for F in new_logdir.glob("magickrgb_*.log") if ((F not in stale_logs) and (not F.is_dir()))]
    
    def PrintLognames(name, loglist:list[pathlib.Path]):
        if((length := len(loglist)) > 0): print(f"{name} ({str(length).zfill(2)}): [" + ", ".join([L.name for L in loglist]) + "]");
    
    if(len(fresh_logs) == 0): return new_logdir;
    print(f"\nrotating logs under: '{new_logdir}'...")
    PrintLognames("fresh", fresh_logs)
    PrintLognames("stale", stale_logs)
    
    # TODO: delete stale logs?
    for log in fresh_logs:
        current_name = log.name; log_num = log.stem.removeprefix("magickrgb_")
        if not (log_num.isdigit()): print(f"error parsing filename of log: ({log_num}); '{log}'"); continue;
        while((new_path := new_logdir / f"magickrgb_{str(log_num).zfill(3)}.log.old").exists()): log_num = int(log_num)+1;
        print(f"  rotating:  {current_name} -> {new_path.name}")
        log.rename(new_path.absolute())
    
    # moving stale logs back to fresh filenames for testing/debug
    # for log in stale_logs:
    #     current_name = log.name; log_num = log.stem.removeprefix("magickrgb_")
    #     for suffix in log.suffixes: log_num = log_num.removesuffix(suffix);
    #     if not (log_num.isdigit()): print(f"error parsing filename of log: ({log_num}); '{log}'"); continue;
    #     while((new_path := new_logdir / f"magickrgb_{str(log_num)[-1]}{str(log_num)[:-3:-1]}.log").exists()): log_num = int(log_num)+1;
    #     print(f" unrotating: {current_name} -> {new_path.name}")
    #     log.rename(new_path.absolute())
    # PrintLognames("unmoved", [F for F in new_logdir.glob("magickrgb_*.log") if ((not (F in fresh_logs)) and (not F.is_dir()))])
    
    PrintLognames("moved", [F for F in new_logdir.glob("magickrgb_*.log.old") if ((not (F in stale_logs)) and (not F.is_dir()))])
    print(f"{len(fresh_logs)} logs rotated [{len(stale_logs)+len(fresh_logs)} total]\n")
    return new_logdir



def CreateTempdir(autodelete=True, use_tmpfs=False) -> tuple[pathlib.Path|None,bool]:
    """ 
    :param autodelete: the new cache-directory will be deleted when program exits (has no effect if pre-existing cache is found)
    :param use_tmpfs: the new cache-directory will be located on tmpfs rather than under cwd. (attempts to mount tmpfs if mountpoint doesn't exist)
    :return: cache-directory's path and flag indicating that a pre-existing directory was found. (path is 'None' if tmpfs-mount failed)
    """
    tempdir_toplevel = pathlib.Path.cwd() / f"{TOPLEVEL_CACHE_NAME}" # parent of all per-process tempdirs
    if use_tmpfs: tempdir_toplevel = pathlib.Path(f"/tmp/{TOPLEVEL_CACHE_NAME}");
    if (isNewlyCreated := (not tempdir_toplevel.exists())):
        tempdir_toplevel.mkdir(); print(f"created toplevel cache: '{tempdir_toplevel}'")
    
    # attempt to mount tmpfs
    if (use_tmpfs and isNewlyCreated):
        print("mounting tmpfs...")
        # mounting tmpfs only seems to work properly when the mountpoint has been created manually?? ('mkdir' above apparently not good enough)
        #retval = os.system(f"mount --types tmpfs -o user,uid=1000,gid=1000,size=0,X-mount.mkdir tmpfs /tmp/{TOPLEVEL_CACHE_NAME}")
        retval = os.system(f"mount /tmp/{TOPLEVEL_CACHE_NAME}") # this command is more reliable, but requires an entry in '/etc/fstab'
        if not (retval == 0):
            print("Failed to mount tmpfs! Add an entry to '/etc/fstab' or mount it manually.")
            tempdir_toplevel.rmdir() # removing to ensure 'isNewlyCreated' will be 'True' again on next run
            return (None, False)
        print("mounted tmpfs!")
        # TODO: should verify that new or pre-existing tempdir_toplevel is actually tmpfs
    
    # TODO: generate tempdir prefix/suffix based on: input-file checksum and options.
    tmpdir_prefix="pfix_"
    tmpdir_suffix="_sfix"
    
    matching_dirs = [*tempdir_toplevel.glob(f"{tmpdir_prefix}*{tmpdir_suffix}/")]
    assert(len(matching_dirs) <= 1), "[ERROR]: multiple cache directory matches!!! (this is a bug)"
    
    if (isReusingCache := (len(matching_dirs) > 0)):
        if autodelete: print("[WARNING] 'autodelete' parameter will be ignored (directory already exists)");
        tempdir = matching_dirs[0] # per-process tempdir - optionally autodeleted when the program exits
        print(f"reusing cache directory: {tempdir} ")
        assert(tempdir.is_dir()), "location on matching path was not actually a directory!?";
        iter_counts = Counter([F.is_file() for F in tempdir.iterdir()])
        (filecount, dircount) = (iter_counts.get(B,0) for B in (True,False))
        tmpdir_mtime = datetime.fromtimestamp(tempdir.stat().st_mtime)
        
        # for debug/testing; ensuring mtime has nonzero 'day'
        # mtime_delta_tomorrow = (datetime.today().replace(day=(datetime.today().day+1)) - tmpdir_mtime)
        
        mtime_delta = (datetime.now() - tmpdir_mtime)
        (days, sec) = (mtime_delta.days, mtime_delta.seconds)
        (hrs, mins) = ( (sec // 3600), ((sec % 3600) // 60) )
        sec = (sec % 60)
        # ignore any 'unused' warnings related to these variables; 
        # they're referenced by 'eval' in 'MaybePlural()' below
        
        def MaybePlural(S:str,localz=locals()) -> str:
            if ((N := eval(S, localz)) == 0): return "";
            return f"{N} {S if (N>1) else S.removesuffix('s')}"
        
        # 'num_time_segments': limits the granularity of the reported mtime-delta to 'N' nonzero segments, ordered largest-first
        # for example, with 'N=2', the mtime-delta will report 'days'/'hrs' if both are nonzero, otherwise 'hrs'/'min', 'min'/'sec', or just 'sec'
        num_time_segments = 2; assert((num_time_segments > 0) and (num_time_segments <= 4));
        relative_time_str = " ".join([*filter(lambda S:(len(S)>0), 
            [MaybePlural(varname) for varname in ['days','hrs','mins','sec']]
        )][:num_time_segments])
        
        if (len(relative_time_str) == 0): 
            print("[WARNING]: pre-existing cache-directory's relative-mtime is apparently zero. (this is probably a bug)")
            relative_time_str = '(now)'
        else: relative_time_str = f"{relative_time_str} ago";
        
        mtime_str = f"Last-Modified: {tmpdir_mtime.date().isoformat()} ({relative_time_str})"
        print(f"{tempdir.name}: [ {filecount} files | {dircount} folders ][ {mtime_str} ]")
        return (tempdir, isReusingCache)
    
    # per-process tempdir - optionally autodeleted when the program exits
    tempdir = tempfile.TemporaryDirectory(
        prefix=tmpdir_prefix, suffix=tmpdir_suffix, dir=tempdir_toplevel,
        delete=autodelete, ignore_cleanup_errors=False
    )
    print(f"created temp directory: '{tempdir.name}' [{'AUTO-DELETE' if autodelete else 'PRESERVE'}]")
    # must construct and return a 'pathlib.Path' because the behavior of '.name' is incompatible between the two classes
    # 'tempfile.TemporaryDirectory' returns the whole path, whereas 'pathlib.Path' would only return the last segment.
    # and the other branch (reusing cache-directory) cannot return a Tempdir.
    return (pathlib.Path(tempdir.name), isReusingCache)



def MakeImageSources(workdir:pathlib.Path, input_file:pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """
    :param workdir: location of temp/cache directory
    :param input_file: image being RGBified
    :return: paths for: [baseimg (unmodified original), srcimg (preprocessed source)]
    """
    assert(workdir.exists() and workdir.is_dir())
    assert(input_file.exists() and input_file.is_file())
    
    # 'safe' filename makes it possible to parse output of 'identify'/'file' (otherwise splitting won't work if filename contained spaces)
    safe_filename = FilterText(str(input_file.stem))
    print(f"\ninput_path: '{input_file}'")
    print(f"safe filename: '{safe_filename}'\n")
    
    # baseimg: copy of unmodified original
    # srcimg: transcoded / preprocessed image optimized for target pipelines
    baseimg_path = pathlib.Path(workdir, f"baseimg_{safe_filename}").with_suffix(input_file.suffix)
    srcimg_path = pathlib.Path(workdir, f"srcimg_{safe_filename}").with_suffix('.png')
    
    if baseimg_path.exists(): print(f"skipping baseimg copy (already exists)")
    else:
        print(f"copying baseimg: '{baseimg_path}'")
        os.system(f"cp '{input_file}' '{baseimg_path}'")
    
    if srcimg_path.exists():
        print(f"skipping srcimg creation (already exists)\n")
        return (baseimg_path, srcimg_path)
    
    print("preprocessing baseimg...")
    # TODO: actually verify the filetype/encoding of baseimg
    # TODO: actually preprocess the baseimg for gif/mp4
    if not (baseimg_path.suffix == srcimg_path.suffix):
        print("warning: conversion needed!")
        #TODO: handle conversion
    
    os.system(f"cp '{baseimg_path}' '{srcimg_path}'")
    print(f"preprocessed source created: '{srcimg_path}'")
    
    print("") # newline
    return (baseimg_path, srcimg_path)


if __name__ == "__main__":
    # args = ParseCmdline()
    args = ParseCmdline(["--tmpfs", "--noclean", "TestImage.png"])
    env_vars = SetupENV()
    
    if not args.input_path.exists():
        print(f"[ERROR] input-file: '{args.input_path}' does not exist")
        exit(1)
    
    (workdir, wasNewlyCreated) = CreateTempdir(autodelete=args.autodelete, use_tmpfs=args.use_tmpfs)
    log_directory = RotateMagickLogs(workdir.parent)  # TODO: don't call this function unless log-output is set to 'txtfile'
    (baseimg,srcimg) = MakeImageSources(workdir, args.input_path)
    
    print(baseimg); print(srcimg)
    #os.system("identify -list resource") # imagemagick syntax
    os.system(f"gm convert -list resources"); print("\n\n")
    os.system(f"gm identify -verbose '{srcimg}'")
    
