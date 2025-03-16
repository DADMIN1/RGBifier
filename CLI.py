import pathlib
import argparse
import tempfile
import subprocess
import os

from collections import Counter
from datetime import datetime

import Globals
import Config
import RGB


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str) -> str:
    if text.isalnum(): return text
    ok_chars = {'_'}
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
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
    
    parser.add_argument("--magick", choices=["IM","GM"], default="GM")
    parser.add_argument("--tmpfs", dest="use_tmpfs", action="store_true", default=False, help="ensure all temp-files are created on a tmpfs; arg is size of tmpfs")
    parser.add_argument("--noclean", dest="autodelete", action="store_false", default=True, help="preserve temp files (deleted by default)")
    
    # parser.add_argument("--fps", dest="fps", type=int, default=60, help="FPS of RGB-ified video (default 60)")
    # TODO: duration
    # TODO: resize (scale/crop)
    # TODO: output types (gif/mp4/script)
    # TODO: OUTPUT PATH !!!!!!!!!!
    
    parsed_args = None; print("\nparsing args...")
    if ((arglist is not None) and (len(arglist) > 0)):
        print(f"additional args given: {arglist}")
        parsed_args = parser.parse_args(arglist)
        print(f"[parsed arglist]: {parsed_args}")
    
    # positional arguments must be added after initial arglist parse, otherwise it errors because they're required 
    parser.add_argument("stepsize", type=float)
    parser.add_argument("image_path", type=pathlib.Path, metavar="IMAGE")
    
    parsed_args = parser.parse_args(namespace=parsed_args)
    print(f"[parsed cmdline]: {parsed_args}\n")
    parsed_args.image_path = parsed_args.image_path.expanduser().resolve().absolute()
    print(f"(expanded) image_path: '{parsed_args.image_path}'")
    
    # assert(type(parsed_args.fps) is int)
    assert(parsed_args.stepsize != 0), "stepsize must not be zero"
    
    Globals.MAGICKLIBRARY = parsed_args.magick
    
    print(parsed_args) # Namespace(...)
    PrintDict(parsed_args.__dict__, "args")
    return parsed_args



def SetupENV(alt_defaults:dict) -> dict:
    """ Sets config/log path, and some resource limits (mostly higher than builtin defaults). \n
    Checks environment and imports any defined ImageMagick/GraphicsMagick variables. \n
    Performs validation for 'MAGICK_DEBUG' if defined externally, otherwise defaults to 'All'. \n 
    Final values are applied and exported to both ImageMagick/GraphicsMagick-style variables """
    def VarNames(S:str): # lambda generating ImageMagick/GraphicsMagick-style environment-variables
        if (S.upper() == "THREADS"): return ("MAGICK_THREAD_LIMIT", "OMP_NUM_THREADS");
        if (S.upper() == "FILES"): return ("MAGICK_FILE_LIMIT", "MAGICK_LIMIT_FILES"); # non-plural in IM-style
        return (f"MAGICK_{S.upper()}_LIMIT", f"MAGICK_LIMIT_{S.upper()}")
        # "memory" -> [MAGICK_MEMORY_LIMIT, MAGICK_LIMIT_MEMORY]
    
    # values specified here will be exported to env if not already defined, unless the value is 'None'
    env_defaults = {
        # resources
          "FILES": 8192, # IM/GM will automatically increase soft-ulimit if necessary (ulimit -S -n)
        "THREADS": (os.cpu_count() // 2), # 'cpu_count()' reports 2 cpus per physical core (hyperthreading)
         "MEMORY": "64GB", # TODO: should match tmpfs size
            "MAP": "64GB", # normally 2x Memory-limit, for some reason
           "DISK": "64GB", # setting this equal to 'Memory' is necessary for tmpfs: imagemagick seems to count loading '.mpc' files as disk usage
          "WIDTH": "32KP", # width/height are hard limits (throws exception if exceeded)
         "HEIGHT": "32KP",
         "PIXELS": None, # GM-only?
           "AREA": None, # IM-only? width*height; suffix is 'KP/MP/GP'. soft limit (unlike height/width); caches to disk if exceeded.
           "READ": None,
          "WRITE": None,
    }
    
    print("reading environment...")
    # if both IM/GM-style variables are set for an entry, the last one (GM-style) will take precedence
    final_env = {
        EK: EV
        for (K,V) in env_defaults.items()
        for EV in [V, *[os.getenv(N) for N in VarNames(K)]]
        for EK in VarNames(K)
        if (EV is not None)
    }
    
    # MAGICK_DBG_SETTING: "None", "All", or comma-seperated domain list
    MAGICK_DBG_SETTING = os.getenv("MAGICK_DEBUG", alt_defaults.get("MAGICK_DEBUG", "None")).replace(" ", "")
    MAGICK_DBG_DOMAINS = ([
        'annotate','blob','cache','coder','configure',
        'deprecate','error','exception','fatalerror',
        'information','locale','option','render','resource',
        'temporaryfile','transform','user','warning','x11',
      ] if (Globals.MAGICKLIBRARY == "GM") else [
        'accelerate','annotate','blob','cache','coder',
        'deprecate','configure','command','exception',
        'locale','module','pixel','policy','resource',
        'draw','trace','transform','user','wand','x11',
    ])
    
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
    
    # TODO: should not be relative to cwd; add a global var for the program path
    config_dir = pathlib.Path(os.getenv("MAGICK_CONFIGURE_PATH", (pathlib.Path.cwd()/"magick_configs").absolute()))
    if (config_dir.exists() and config_dir.is_dir()): final_env["MAGICK_CONFIGURE_PATH"] = str(config_dir);
    else: print(f"[WARNING] bad path for 'MAGICK_CONFIGURE_PATH': {config_dir}");
    
    # adds info about file-access to '-monitor' output (including temporary files); "TRUE"/"FALSE"
    final_env["MAGICK_ACCESS_MONITOR"] = str(os.getenv("MAGICK_ACCESS_MONITOR", alt_defaults.get("MAGICK_ACCESS_MONITOR", False))).upper()
    
    print("updating magick environment variables...\n")
    PrintDict(env_defaults, name="defaults")
    PrintDict(final_env, name="environment")
    for (K,V) in final_env.items():
        os.putenv(K,str(V))  # doesn't update 'os.environ'
        os.environ[K] = str(V) # modifying this automatically calls 'putenv', supposedly
    
    return final_env



def CreateTempdir(checksum:str, autodelete=True, use_tmpfs=False) -> tuple[pathlib.Path|None,bool]:
    """ 
    :param checksum: hash of input file; used as prefix for temporary subdirectory
    :param autodelete: the new temporary-directory will be deleted when program exits (has no effect if pre-existing temporary is reused)
    :param use_tmpfs: toplevel will be located on tmpfs rather than under cwd. (attempts to mount tmpfs if mountpoint doesn't exist)
    :return: new temp directory and flag indicating that a pre-existing directory was found. (path is 'None' if tmpfs-mount failed)
    """
    tempdir_toplevel = pathlib.Path.cwd() / f"{Globals.TOPLEVEL_NAME}" # parent of all per-process tempdirs
    if use_tmpfs: tempdir_toplevel = pathlib.Path(f"/tmp/{Globals.TOPLEVEL_NAME}");
    if (isNewlyCreated := (not tempdir_toplevel.exists())):
        tempdir_toplevel.mkdir(); print(f"created toplevel directory: '{tempdir_toplevel}'")
    
    # attempt to mount tmpfs
    if (use_tmpfs and isNewlyCreated):
        print("mounting tmpfs...")
        # mounting tmpfs only seems to work properly when the mountpoint has been created manually?? ('mkdir' above apparently not good enough)
        #retval = os.system(f"mount --types tmpfs -o user,uid=1000,gid=1000,size=0,X-mount.mkdir tmpfs /tmp/{Globals.TOPLEVEL_NAME}")
        retval = os.system(f"mount /tmp/{Globals.TOPLEVEL_NAME}") # this command is more reliable, but requires an entry in '/etc/fstab'
        if not (retval == 0):
            print("Failed to mount tmpfs! Add an entry to '/etc/fstab' or mount it manually.")
            tempdir_toplevel.rmdir() # removing to ensure 'isNewlyCreated' will be 'True' again on next run
            return (None, False)
        print("mounted tmpfs!")
        # TODO: should verify that new or pre-existing tempdir_toplevel is actually tmpfs
    
    tmpdir_prefix=f"{checksum}_"
    tmpdir_suffix=f"_{Globals.MAGICKLIBRARY}"
    
    matching_dirs = [*tempdir_toplevel.glob(f"{tmpdir_prefix}*{tmpdir_suffix}/")]
    assert(len(matching_dirs) <= 1), "[ERROR]: multiple pre-existing subdirectory matches!!! (this is a bug)"
    
    if (isReusingSubdir := (len(matching_dirs) > 0)):
        if autodelete: print("[WARNING] 'autodelete' parameter will be ignored (directory already exists)");
        tempdir = matching_dirs[0] # per-process tempdir - optionally autodeleted when the program exits
        print(f"reusing work directory: {tempdir}")
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
            print("[WARNING]: pre-existing work-directory's relative-mtime is apparently zero. (this is probably a bug)")
            relative_time_str = '(now)'
        else: relative_time_str = f"{relative_time_str} ago";
        
        mtime_str = f"Last-Modified: {tmpdir_mtime.date().isoformat()} ({relative_time_str})"
        print(f"{tempdir.name}: [ {filecount} files | {dircount} folders ][ {mtime_str} ]")
        Globals.TEMPDIR_REF = tempdir
        return (tempdir, isReusingSubdir)
    
    # per-process tempdir - optionally autodeleted when the program exits
    tempdir = Globals.TEMPDIR_REF = tempfile.TemporaryDirectory(
        prefix=tmpdir_prefix, suffix=tmpdir_suffix, dir=tempdir_toplevel,
        delete=autodelete, ignore_cleanup_errors=False
    )
    print(f"created temp directory: '{tempdir.name}' [{'AUTO-DELETE' if autodelete else 'PRESERVE'}]")
    # must construct and return a 'pathlib.Path' because the behavior of '.name' is incompatible between the two classes
    # 'tempfile.TemporaryDirectory' returns the whole path, whereas 'pathlib.Path' would only return the last segment.
    # and the other branch (reusing work-directory) cannot return a Tempdir.
    return (pathlib.Path(tempdir.name), isReusingSubdir)



# GraphicsMagick does not provide any mechanism for specifying a relative-path for logfile, except for subdirectories under CWD.
# variable-expansion / substitution does not appear to be possible. Changing the path at runtime does not seem (reasonably) possible.
# If the path contains a directory, that directory must already exist, otherwise the logfile will simply not be written (silent failure; no warnings, of course)
# also, the mechanisms for writing numbered logfiles are only triggered by the event-limit (see log.mgk);
# otherwise, GraphicsMagick just overwrites the same logfile on every single run.
def RotateMagickLogs(toplevel:pathlib.Path) -> pathlib.Path:
    """ Create logging directory and rename existing logs.\n
    Logs prefixed with 'magickrgb' will be rotated. \n Logs' filenames should end with digits. \n
    Assumes that GraphicsMagick's logging-config (log.mgk) has 'filename' is set to: \n "/tmp/RGB_TOPLEVEL/magicklogs/magickrgb_%d.log" \n
    :param toplevel: see 'Globals.TOPLEVEL_NAME'
    :return: path to log-directory """
    assert(toplevel.name == Globals.TOPLEVEL_NAME), "expected log-directory to be under toplevel"
    assert(toplevel.is_relative_to("/tmp/")), "reminder to change path in 'log.mgk'";
    # TODO: come up with some workaround to switch paths between toplevel under tmpdir/cwd. maintain a symlink under cwd?
    
    new_logdir = toplevel / "magicklogs"
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
    
    # TODO: implement a limit for how many logs are kept, delete stale logs?
    for log in fresh_logs:
        current_name = log.name; log_num = log.stem.removeprefix("magickrgb_")
        middle_name = "".join(C for C in log_num if C.isalpha())
        if (len(middle_name) != 0): middle_name = f"_{middle_name}";
        if not (log_num.isdigit()):
            log_num = "".join(reversed([C for C in reversed(log_num) if C.isdigit()])) # this takes all digits in remaining text, not just trailing
            if (len(log_num) == 0): log_num = '0';
        if not (log_num.isdigit()): print(f"error parsing filename of log: ({log_num}); '{log}'"); continue;
        while((new_path := new_logdir / f"magickrgb{middle_name}_{str(log_num).zfill(3)}.log.old").exists()): log_num = int(log_num)+1;
        print(f"  rotating:  {current_name} -> {new_path.name}")
        log.rename(new_path.absolute())
    
    PrintLognames("moved", [F for F in new_logdir.glob("magickrgb_*.log.old") if ((not (F in stale_logs)) and (not F.is_dir()))])
    print(f"{len(fresh_logs)} logs rotated [{len(stale_logs)+len(fresh_logs)} total]\n")
    return new_logdir


def MakeImageSources(workdir:pathlib.Path, input_file:pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """
    :param workdir: temp subdirectory for image-processing
    :param input_file: image being RGBified; copied to workdir
    :return: [baseimg (unmodified original), srcimg (preprocessed source)]
    """
    assert(workdir.exists() and workdir.is_dir())
    assert(input_file.exists() and input_file.is_file() and (input_file.parent != workdir))
    
    # 'safe' filename makes it possible to parse output of 'identify'/'file' (otherwise splitting won't work if filename contained spaces)
    safe_filename = FilterText(str(input_file.stem))
    print(f"\nimage_path: '{input_file}'")
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


def SubCommand(cmdline:list[str]|str, logname:str|None = "main", isCmdSequence:bool = False):
    """ Run a command in subprocess and log output. Logs are appended to or created automatically.
    :param cmdline: string or args-list (including command itself)
    :param logname: identifier used in filename. Skip logging if None.
    :param isCmdSequence: 'cmdline' is a list of commands to execute (rather than a single cmdline split by word)
    """
    print('_'*120); print(); L = "\n  "
    subcmd_str = ('commandseq: [{1}{0}\n]' if isCmdSequence else 'subcommand: "{0}"')
    print(subcmd_str.format((f",{L}".join(cmdline) if isCmdSequence else cmdline),L))
    if (log_dir := Globals.LOGGING_DIR) is None: print(f"[ERROR] no valid 'log_dir'"); return; 
    if not log_dir.exists(): print(f"creating log_dir: '{log_dir}'"); log_dir.mkdir();
    
    # TODO: Skip logging if None
    skiplog = (logname is None)
    log_filepath = log_dir / f"magickrgb_{logname}.log"
    if logname is None: print("skipping logging"); log_filepath = log_dir/"magickrgb_main.log"; # still logs command, but not output
    else:  print(f"logging to: '{log_filepath}'");
    print('_'*120); print()
    
    # shell=True if cmdline is a single string
    # cwd=... <- could be useful
    # text=True: output is captured as string instead of bytes. implied by specifying 'encoding'
    # check=True: raises 'CalledProcessError' on nonzero return-status
    #completed = subprocess.run(cmdline, check=True, capture_output=True, encoding="utf-8")
    #completed = subprocess.run(cmdline, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
    #completed = subprocess.run(cmdline, check=True, stdout=None, stderr=subprocess.PIPE, encoding="utf-8")
    # 'capturing' either stream means it won't get printed; set them to 'None' if you want them printed.
    
    # mode='a' - append to existing file, or create new
    with log_filepath.open(mode='a', encoding="utf-8") as logfile:
        cmdline_str = (cmdline if (type(cmdline) is str) else ("\n" if isCmdSequence else " ").join(cmdline))
        logfile.write(cmdline_str); logfile.write("\n\n"); logfile.flush()
        cmd_seq = (cmdline if isCmdSequence else [cmdline])
        for cmd in cmd_seq:
            completed = subprocess.run(cmd, stdout=None, stderr=(logfile if not skiplog else None), encoding="utf-8", shell=(type(cmd) is str)) # prints stdout, logs stderr
        if (completed.returncode != 0): print(f"[ERROR] nonzero exit-status: {completed.returncode}\n");
        logfile.write('_'*120); logfile.write("\n\n")
    
    print("\n")
    return completed.returncode


if __name__ == "__main__":
    (conf_cmdline_args, conf_env_defaults) = Config.Init()
    args = ParseCmdline(conf_cmdline_args)
    env_vars = SetupENV(conf_env_defaults)
    
    if not args.image_path.exists():
        print(f"[ERROR] input-file: '{args.image_path}' does not exist")
        exit(1)
    
    md5sum_output = subprocess.check_output(["md5sum", str(args.image_path)])
    checksum = str(md5sum_output, encoding="utf-8").split()[0]
    assert(len(checksum) == 32), "MD5-hash did not match expected length"
    
    (workdir, wasNewlyCreated) = CreateTempdir(checksum, autodelete=args.autodelete, use_tmpfs=args.use_tmpfs)
    if(workdir is None): print(f"no workdir. exiting"); exit(2); # tmpfs mount attempted and failed
    assert(Globals.TEMPDIR_REF is not None)
    if(not workdir.exists()): print("workdir does not exist!!!!"); os.sync();
    if(not workdir.exists()): print("workdir does not exist!!!!"); exit(4)
    
    log_directory = RotateMagickLogs(workdir.parent)
    (baseimg,srcimg) = MakeImageSources(workdir, args.image_path)
    Globals.UpdateGlobals(workdir, srcimg, log_directory) # dbgprint=True
    RGB.PrintGlobals() # no-op unless DEBUG_PRINT_GLOBALS / dbgprint
    
    print(baseimg); print(srcimg); print(f"\n{'_'*120}\n")
    SubCommand(f"{('gm convert -list resources' if (Globals.MAGICKLIBRARY=="GM") else 'identify -list resource')}", logname=None)
    SubCommand(f"{('gm ' if (Globals.MAGICKLIBRARY=="GM") else '')}identify -verbose {str(srcimg)}", logname=None)
    
    output_filename = f"{Globals.SRCIMG_PATH.with_suffix('').name}_RGB".removeprefix('srcimg_')
    # not using 'args.image_path' because that filename might be unsafe.
    print(f"output_filename: {output_filename}")
    print(f"original directory: {args.image_path.parent.absolute()}")
    print(f"{(args.image_path.parent / output_filename).absolute()}")
    final_destination = pathlib.Path(args.image_path.parent / output_filename).with_suffix('.mp4')
    
    renamelimit = 10; renamecount=1
    while(final_destination.exists() and (renamecount < renamelimit)):
        print(f"[WARNING] final output already exists: '{final_destination.absolute()}'")
        output_filename = f"{final_destination.with_suffix('').name.removesuffix(f'_{renamecount-1}')}_{renamecount}"
        final_destination = (final_destination.parent / output_filename).with_suffix(final_destination.suffix)
        print(f"    renaming: '{final_destination.absolute()}'")
        renamecount += 1
    if renamecount >= renamelimit: print(f"hit rename limit. exiting."); exit(3);
    assert(final_destination.parent.exists());
    assert(final_destination.parent.absolute() == args.image_path.parent.absolute());
    print(f"final destination: '{final_destination.absolute()}'\n\n")
    
    #TODO: refactor this
    debug_print_cmds = Globals.DEBUG_PRINT_CMDS # print commands before passing to 'SubCommand'
    debug_print_only = Globals.DEBUG_PRINT_ONLY # exit after printing commands; do not execute
    debug_print_cmds = (debug_print_only or debug_print_cmds) # auto-enable when 'PRINT_ONLY' is True
    
    (cmdlist, batchfile) = RGB.GenerateCommands(args.stepsize, writeMPC=False, writePNG=True, writeBatchfile=True, output_name=output_filename)
    if (batchfile is not None):
        (batch_cmd, rendercmd) = cmdlist
        if(debug_print_cmds): print('\n'); print(batch_cmd); print(rendercmd);
        if(debug_print_only): print("[DEBUG_PRINT_ONLY] early exit"); exit(0);
        SubCommand(batch_cmd, "frame_gen")
        SubCommand(rendercmd, "rendering")
    else:
        framegen_cmds = cmdlist[1:-1]; rendercmd = cmdlist[-1]
        if (debug_print_cmds):
            print('\n'); print(cmdlist[0]) # cache_srcimg cmd
            print('\n'.join(framegen_cmds)); print(rendercmd)
        if (debug_print_only): print("[DEBUG_PRINT_ONLY] early exit"); exit(0);
        SubCommand(cmdlist[0], "cache_srcimg")
        SubCommand(framegen_cmds, "frame_gen", isCmdSequence=True)
        SubCommand(rendercmd, "rendering")
    
    # TODO: implement expected-output properly
    expected_output = (workdir/output_filename).absolute().with_suffix('.mp4'); os.sync()
    if not expected_output.exists(): print(f"[ERROR] expected output does not exist! ({expected_output})"); exit(4);
    SubCommand(f"cp --verbose --update=none '{expected_output}' '{final_destination.absolute()}'", logname=None)
    
    print("\ndone\n")
