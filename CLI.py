import pathlib
import argparse
import tempfile
import textwrap
import subprocess
import os

from collections import Counter
from datetime import datetime

import Globals
import Config
import Task
import RGB


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str) -> str:
    if text.isalnum(): return text
    ok_chars = {'_'}
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


def PrintDict(D:dict, name=None):
    if name is not None: print(f"{name} = "+"{ ");
    for (k,v) in D.items(): print(f"  {k}: {v},");
    if name is not None: print("}\n");


class ExplicitPath(pathlib.Path):
    """Path which differentiates explicit and implicit relativity, and preserves any single-dots ('.') within input"""
    def __init__(self, *args):
        (self.argzero, self.argz) = tuple(
            (str(args[0]).strip(), ''.join(str(arg).strip() for arg in args))
            if bool(args) else ('','')
        )
        self.is_empty = (not args) or (not self.argz) or (not self.argzero)
        self.is_absol = self.argzero.startswith(('/','~')) or pathlib.Path(self.argz).expanduser().is_absolute()
        self.explicit = self.argzero.startswith(('.','..','./'))
        self.relative = self.explicit or ((not self.is_absol) and (not self.is_empty))
        super().__init__(self.argz)
    
    def __str__(self):  return self.argz;
    def __repr__(self): return f"ExplicitPath('{self.argz}')";
    def PrintDict(self): PrintDict(self.__dict__, repr(self));
    
    def under(self, newparent:pathlib.Path):
        if self.is_empty: return newparent;
        top_parent = (self.parents[-1] if (len(self.parents) > 0) else '/')
        return newparent.joinpath(
            pathlib.Path(self.argz).relative_to(top_parent)
            if (self.is_absol) else pathlib.Path(self.argz)
        )
    
    # division operator: (path / str|path)
    def __truediv__(self, key:str|pathlib.Path) -> pathlib.Path:
        if self.is_empty: return pathlib.Path(key);
        try: return pathlib.Path(self.argz).joinpath(key);
        except TypeError: return NotImplemented;
    
    def __rtruediv__(self, key:str|pathlib.Path):
        if self.is_empty: return pathlib.Path(key);
        try: return self.under(pathlib.Path(key));
        except TypeError: return NotImplemented;


#valid_fileformats
class FormatList():
    """String-list with lenient (caseless) comparisons and inclusion-rules"""
    def __init__(self, *strings:str): self.strings = tuple((S.upper() for S in strings));
    def __contains__(self,other:str): return (other.lstrip('.').upper() in self.strings); # operator 'in'
    def __eq__(self,other:str):       return (other.lstrip('.').upper() in self.strings);
    def __repr__(self): return repr((*self.strings, *(S.lower() for S in self.strings))); # display for debugger/interpreter
    def __str__(self):  return str(self.strings);  # display for print() and str()
    def __iter__(self): return self.strings.__iter__(); # using argparse 'choices'
    def __getitem__(self, at): return self.strings.__getitem__(at); # []-subscript


# custom formatter_class combining the behavior of two arparse formatters
# allows newlines within help-text and automatically appends info about default value
class CustomFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, prog): super().__init__(prog, indent_increment=2, max_help_position=32, width=72);


def ParseCmdline(arglist:list[str]|None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="RGBifier", allow_abbrev=False,
        formatter_class=CustomFormatter
    )
    #TODO: description and epilog
    
    group_system = parser.add_argument_group("system-options")
    primary_args = parser.add_argument_group("main arguments")
    grp_relative = parser.add_argument_group("relative-flags")
    group_output = parser.add_argument_group("output-options")
    group_relopt = grp_relative.add_mutually_exclusive_group()
    # group_relopt = group_output.add_mutually_exclusive_group()
    grp_transform = parser.add_argument_group("transformations")
    
    # grp_relative.title = None # prevents title from printing; leaving a single empty line above group
    
    group_system.add_argument("--magick", choices=["IM","GM"], default="GM", help="select magick library (ImageMagick / GraphicsMagick)")
    group_system.add_argument("--tmpfs", dest="use_tmpfs", action="store_true", help="use tmpfs (RAM filesystem) for workdir and tempfiles - preventing all disk writes")
    #group_system.add_argument("--autodelete", dest="autodelete", action="store_true", default=True, help="wipe the (temp) working directory after processing")
    group_system.add_argument("--noclean", dest="autodelete", action="store_false", help="preserve temp-files (deleted by default - ignore the following 'default' message)")
    # TODO: fix the display of '--noclean'/autodelete's default message
    group_system.add_argument("--print-only", nargs='?', metavar="limit", type=int, const=1, help="exit after printing the commands that would have been executed")
    group_system.add_argument("--parse-only", nargs='?', metavar="limit", type=int, const=1, help="exit after completing commandline parsing (and loading config)")
    
    group_output.add_argument("--mkdir", action="store_true", help="create output-directory if necessary (all parents must already exist)")
    group_output.add_argument("--mkdir-parent", action="store_true", help="mkdir also creates any missing parent-directories (implies '--mkdir')")
    group_relopt.add_argument("--relative-img", action="store_true", help="reinterpret the output-directory relative to location of source-image")
    group_relopt.add_argument("--relative-cwd", action="store_true", help="reinterpret the output-directory relative to CWD (currrent directory)")
    group_relopt.add_argument("--relative-tmp", action="store_true", help="reinterpret the output-directory relative to RGB_TOPLEVEL (tmpfs dir)")
    # TODO: explain interpretation of output-path and behavior of relative flags
    
    # parser.add_argument("--fps", dest="fps", type=int, default=60, help="FPS of RGB-ified video (default 60)")
    # TODO: duration/fps/numloops/reverse
    
    scale_help = textwrap.dedent("""\
        suffix: '%%' denotes percentage-scaling (integer)
        suffix: 'x' denotes multiplier-scaling (float)
        Outputs will be generated at each scale specified, instead of normal size
        include '100%%' or '1x' to also produce full-size output."""
    )
    
    grav = ["north","south","east","west"]; gravities = (*grav, *[''.join((P,S)) for P in grav[:2] for S in grav[2:]])
    grp_transform.add_argument("--crop", metavar="{[W]x[H][%]}[+X][+Y]", help="crop image to 'WxH', at (optional) offset 'X,Y'")
    grp_transform.add_argument("--gravity", choices=("center",*gravities), default="center", help="anchoring of crop operation")
    grp_transform.add_argument("--scale", nargs=1, dest="scales", action="extend", metavar="{int[%]|float[x]}")
    grp_transform.add_argument("--scales", nargs='+', action="extend", default=[], metavar="{int[%]|float[x]}", help=scale_help)
    
    parsed_args = None; print("\nparsing args...")
    if ((arglist is not None) and (len(arglist) > 0)):
        print(f"additional args given: {arglist}")
        parsed_args = parser.parse_args(arglist)
        print(f"[parsed arglist]: {parsed_args}")
    
    # TODO: use 'parse_known_args' and 'parse_intermixed_args' for this behavior
    # positional arguments must be added after initial arglist parse, otherwise it errors because they're required 
    primary_args.add_argument("image_path", type=pathlib.Path, metavar="IMAGE", help="path of image being RGBified (this argument is mandatory)")
    primary_args.add_argument("output_dir", type=ExplicitPath, metavar="DIRECTORY", nargs='?', help="output location - same as input by default")
    primary_args.add_argument("--stepsize", type=float, default=1.00, metavar='(float)', help="modulation per frame - 1/200th of full cycle")
    
    valid_fileformats = FormatList("GIF", "MP4", "APNG", "WEBP", "ALL")
    group_output.add_argument("--format", dest="output_formats", metavar="fmt",
        choices=valid_fileformats, nargs='+', action='append', default=["GIF"],
        help=f"list of output formats: {valid_fileformats}\n"
        +"names can be in lowercase and may have a leading dot ('.gif')\n"
        +"animated WebP specifically requires ImageMagick (--magick=IM)\n"
        +"MP4 and APNG outputs require ffmpeg"
    )
    
    parsed_args = parser.parse_args(namespace=parsed_args)
    print(f"[parsed cmdline]: {parsed_args}\n")
    
    parsed_args.image_path = parsed_args.image_path.expanduser().resolve().absolute()
    print(f"(expanded) image_path: '{parsed_args.image_path}'")
    
    # any args will be in a list appended to default, so just use that list if it exists 
    if (len(parsed_args.output_formats) > 1): parsed_args.output_formats = parsed_args.output_formats[1];
    parsed_args.output_formats = [*set(fmt.upper().removeprefix('.') for fmt in parsed_args.output_formats)]
    if ("ALL" in parsed_args.output_formats):
        lastindex = (3 if (parsed_args.magick == "GM") else 4) # GM won't include 'WEBP'
        parsed_args.output_formats = [fmt.upper() for fmt in valid_fileformats[:lastindex]]
    print(f"selected output-filetypes: {parsed_args.output_formats}")
    
    if (("WEBP" in (formats := parsed_args.output_formats)) and (parsed_args.magick == "GM")):
        print("\n[WARNING] 'WebP' format is only compatible with ImageMagick - not GraphicsMagick. (use: '--magick=IM')")
        if (len(formats) > 1): parsed_args.output_formats = [F for F in formats if (F != "WEBP")]; print("[WARNING] excluding WebP!");
        else: print("automatically switching to ImageMagick backend"); parsed_args.magick="IM"; # when no other format was selected
    print("")
    
    # assert(isinstance(parsed_args.fps, int))
    assert(parsed_args.stepsize != 0), "stepsize must not be zero"
    assert(len(parsed_args.output_formats) > 0), "missing output format"
    assert(all([(fmt in valid_fileformats) for fmt in parsed_args.output_formats])), "invalid format after processing cmdline"
    if not parsed_args.image_path.exists(): print(f"[ERROR] non-existent input_path: [{parsed_args.image_path}]"); exit(1);
    
    Globals.MAGICKLIBRARY = parsed_args.magick; debug_flags = []
    def Extend(S, C): debug_flags.extend([S for _ in range(C)]);
    if (FC := parsed_args.print_only): Extend("PRINT_ONLY", FC);
    if (FC := parsed_args.parse_only): Extend("PARSE_ONLY", FC);
    if (len(debug_flags)): Globals.ApplyDebugFlags(debug_flags);
    
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
    
    config_dir = pathlib.Path(os.getenv("MAGICK_CONFIGURE_PATH", (Globals.PROGRAM_DIR / "magick_configs/").absolute()))
    if (config_dir.exists() and config_dir.is_dir()): final_env["MAGICK_CONFIGURE_PATH"] = str(config_dir);
    else: print(f"[WARNING] bad path for 'MAGICK_CONFIGURE_PATH': {config_dir}");
    
    # "MAGICK_TMPDIR" might be GM-only?
    magick_tmp = pathlib.Path(os.getenv("MAGICK_TMPDIR", (Globals.WORKING_DIR.parent / f"TEMP_{Globals.MAGICKLIBRARY}/").absolute()))
    if (magick_tmp.is_dir()): final_env["MAGICK_TMPDIR"] = str(magick_tmp);
    else: print(f"[WARNING] invalid env 'MAGICK_TMPDIR': {magick_tmp}");
    
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
    :param use_tmpfs: toplevel is located on tmpfs instead of under program-directory (attempts to mount tmpfs if mountpoint doesn't exist)
    :return: new temp directory and flag indicating that a pre-existing directory was found. (path is 'None' if tmpfs-mount failed)
    """
    tempdir_toplevel = Globals.PROGRAM_DIR / f"{Globals.TOPLEVEL_NAME}" # parent of all per-process tempdirs
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
    
    # see 'temporary-path' in 'policy.xml' and "${MAGICK_TMPDIR}"
    for MK in ("IM", "GM"):
        magick_tmpdir = tempdir_toplevel / f"TEMP_{MK}"
        if not magick_tmpdir.exists(): magick_tmpdir.mkdir(); 
    
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



# output-directory cannot be resolved during initial parsing because 'relative_tmp' requires knowledge of 'TEMPDIR'
# also, the 'mkdir' calls would be a serious problem if they occurred before tmpfs was actually mounted
def ResolveOutputPath(parsed_args:argparse.Namespace, toplevel:pathlib.Path):
    """resolves output-directory path and handles related args \n
       this function must only be called after 'CreateTempdir()'
       :param parsed_args: namespace returned by 'ParseCmdline()'
       :param toplevel: "RGB_TOPLEVEL" directory (Globals.TOPLEVEL_NAME)
       :returns: output-directory path
    """
    assert(Globals.TEMPDIR_REF is not None), "TEMPDIR has not been initialized";
    assert(toplevel.name == Globals.TOPLEVEL_NAME), f"toplevel name: {toplevel.name}; expected: {Globals.TOPLEVEL_NAME}";
    assert(toplevel.is_dir()), "toplevel-path does not exist or is not a directory!";
    
    print(f"resolving output-path...")
    print(f"toplevel: {toplevel}")
    # print(f"parsed_args:\n{parsed_args}\n")
    # PrintDict(parsed_args.__dict__, "parsed_args")
    if isinstance(parsed_args.output_dir, ExplicitPath):
        dir_repr = "".join(parsed_args.output_dir.argz)
    else: dir_repr = parsed_args.output_dir;
    print(f"(unparsed) output_dir: '{dir_repr}'")
    
    relative_flags = (
        (parsed_args.relative_tmp, toplevel),
        (parsed_args.relative_cwd, pathlib.Path.cwd()),
        (parsed_args.relative_img, parsed_args.image_path.parent),
    )
    
    # when output-path is unspecified, relative flags may control the location 
    outdir_default = parsed_args.image_path.parent
    for (arg, path) in (relative_flags):
        if (arg): outdir_default = path; break;
    
    print(f"relative-flags: {relative_flags}")
    print(f"outdir-default: {outdir_default}")
    
    if ((out_path := parsed_args.output_dir) is None): out_path = ExplicitPath('.');
    parsed_args.output_dir = out_path = (
        outdir_default if (not parsed_args.output_dir) or out_path.is_empty
        else out_path.under(toplevel) if parsed_args.relative_tmp
        else out_path.under(pathlib.Path.cwd()) if parsed_args.relative_cwd or (out_path.explicit and not parsed_args.relative_img)
        else out_path.under(parsed_args.image_path.parent) if parsed_args.relative_img or (out_path.relative and not parsed_args.relative_cwd)
        else out_path
    ).expanduser().resolve().absolute()
    
    print(f"(expanded) output_dir: '{parsed_args.output_dir}/'")
    
    if parsed_args.mkdir_parent: parsed_args.mkdir = True;
    if not (mkdir_success := out_path.exists()):
        if parsed_args.mkdir and (out_path.parent.exists() or parsed_args.mkdir_parent):
            mkdir_success = True
            out_path.mkdir(parents=parsed_args.mkdir_parent)
            print(f"created output directory: '{out_path.name}'")
        elif not out_path.parent.exists():
            missing_parents = [*reversed([(highest := P).name for P in out_path.parents if not P.exists()])]
            above_top = f".../{abv.name}" if ((abv := highest.parent).parent.parts != tuple(out_path.root,)) else ''
            rel_miss = f"'{out_path.parent.name}/{out_path.name}' ({'/'.join([above_top, *missing_parents])}/)"
            top_miss = f"'{highest.name}' ({highest.absolute()}/)"
            print(f"[ERROR] cannot create parent of nested subdirectories: {rel_miss} under non-existent location: {top_miss}")
            print(f"  specify '--mkdir-parent' to auto-create all missing subdirectories: {[*missing_parents, out_path.name]}")
        elif not parsed_args.mkdir:
            print(f"[ERROR] nonexistent output-directory: {out_path}")
            print("  specify '--mkdir' to auto-create this directory")
    if not out_path.exists(): print("  output-directory could not be created."); mkdir_success = False;
    elif not out_path.is_dir(): print("  output-directory is not a directory."); mkdir_success = False;
    if not mkdir_success: print("  exiting...\n"); exit(6)
    
    return out_path



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
    #assert(toplevel.is_relative_to("/tmp/")), "reminder to change paths in 'log.mgk' and 'log.xml'";
    # the configs' filepaths shouldn't matter as long as the 'output' option is not set to 'file'
    # TODO: come up with some workaround to switch paths in the configs between tmpfs/cwd. maintain a symlink under cwd?
    
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
    if (len(cmdline) == 0): print(f"[WARNING] skipping subcommand: empty cmdline! (logname: {logname})"); return;
    
    print('_'*120); print(); L = "\n  "
    subcmd_str = ('commandseq: [{1}{0}\n]' if isCmdSequence else 'subcommand: "{0}"')
    print(subcmd_str.format((f",{L}".join(cmdline) if isCmdSequence else cmdline),L))
    if (log_dir := Globals.LOGGING_DIR) is None: print(f"[ERROR] no valid 'log_dir'"); return; 
    if not log_dir.exists(): print(f"creating log_dir: '{log_dir}'"); log_dir.mkdir();
    
    # TODO: Skip logging if None
    skiplog = (logname is None)
    log_filepath = log_dir / f"magickrgb_{logname}.log"
    if logname is None: log_filepath = log_dir/"magickrgb_main.log"; # still logs command, but not output
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
        cmdline_str = (cmdline if isinstance(cmdline,str) else ("\n" if isCmdSequence else " ").join(cmdline))
        logfile.write(cmdline_str); logfile.write("\n\n"); logfile.flush()
        cmd_seq = (cmdline if isCmdSequence else [cmdline])
        for cmd in cmd_seq:
            completed = subprocess.run(cmd, check=True, stdout=None, stderr=(logfile if not skiplog else None), encoding="utf-8", shell=(isinstance(cmd,str))) # prints stdout, logs stderr
        if (completed.returncode != 0): print(f"[ERROR] nonzero exit-status: {completed.returncode}\n");
        logfile.write('_'*120); logfile.write("\n\n")
    
    print("\n")
    return


def Main(identify_srcimg=False):
    (conf_cmdline_args, conf_env_defaults) = Config.Init()
    args = ParseCmdline(conf_cmdline_args); Globals.Break("PARSE_ONLY")
    
    image_md5sum = subprocess.check_output(["md5sum", str(args.image_path)])
    checksum = str(image_md5sum, encoding="utf-8").split()[0]
    assert(len(checksum) == 32), "MD5-hash did not match expected length"
    
    (workdir, wasNewlyCreated) = CreateTempdir(checksum, autodelete=args.autodelete, use_tmpfs=args.use_tmpfs)
    if (workdir is None): print(f"no workdir. exiting"); exit(2); # tmpfs mount attempted and failed
    assert(Globals.TEMPDIR_REF is not None); assert(workdir.exists());
    
    output_directory = ResolveOutputPath(args, workdir.parent)
    print(f"output_directory resolved to: {output_directory}")
    Globals.Break("PARSE_ONLY") # select with '--parse-only 2'
    
    log_directory = RotateMagickLogs(workdir.parent)
    (baseimg,srcimg) = MakeImageSources(workdir, args.image_path)
    Globals.UpdateGlobals(workdir, srcimg, log_directory) # dbgprint=True
    RGB.PrintGlobals() # no-op unless DEBUG_PRINT_GLOBALS / dbgprint
    
    # must be called after UpdateGlobals (needs Globals.WORKING_DIR)
    env_vars = SetupENV(conf_env_defaults)
    
    if identify_srcimg:
        print(baseimg); print(srcimg); print(f"\n{'_'*120}\n")
        SubCommand(f"{('gm convert -list resources' if (Globals.MAGICKLIBRARY=="GM") else 'identify -list resource')}", logname=None)
        SubCommand(f"{('gm ' if (Globals.MAGICKLIBRARY=="GM") else '')}identify -verbose {str(srcimg)}", logname=None)
    
    output_filename = f"{Globals.SRCIMG_PATH.with_suffix('').name}_RGB".removeprefix('srcimg_')
    # not using 'args.image_path' because that filename might be unsafe.
    print(f"output_filename: {output_filename}")
    print(f"original location: {args.image_path.parent.absolute()}")
    print(f"final: {(output_directory/output_filename).absolute()}")
    
    task = Task.TaskT(
        srcimg,
        workdir,
        checksum,
        args.crop,
        args.gravity,
        args.scales,
        'MIFF',
        output_filename,
        output_directory,
        args.output_formats,
    )
    
    expected_outputs = Task.FillExpectedOutputs(task)
    print('\n'); assert(len(expected_outputs) > 0), "no expected outputs"
    
    # command_names = ("preprocessing", "frame_generation", "rendering")
    commands = Task.GenerateFrames(task, RGB.EnumRotations(args.stepsize))
    (webp_rendercmds, ffmpeg_commands) = commands[-2:]; commands = commands[:3]
    
    cmd_names = ("preprocessing", "frame_generation", "rendering", "rendering_webp", "rendering_ffmpeg")
    batch_files = [RGB.SaveCommand(name, cmd) for (name, cmd) in zip(cmd_names[:3], commands[:3])][0::1]
    batch_commands = [f"gm batch -echo on -stop-on-error on '{batchfile}'" for batchfile in batch_files]
    
    if Globals.DEBUG_PRINT_CMDS:
        print(f"\n{'_'*120}\n\nDEBUG_PRINT_CMDS!\n{'_'*120}")
        all_command_lists=[*commands,webp_rendercmds,ffmpeg_commands]
        for (cmd_name, cmdlist) in zip(cmd_names, all_command_lists):
            print(f"\n{cmd_name}:\n  {'\n  '.join(cmdlist)}")
        print(f"\nbatch_commands:\n  {'\n  '.join(batch_commands)}")
        print(f"\n{'_'*120}\n")
    Globals.Break("PRINT_ONLY")
    
    if (use_IM := (Globals.MAGICKLIBRARY == "IM")): batch_commands = []; # prevents GM-only cmds
    batch_zip = zip(cmd_names, (batch_commands if (Globals.MAGICKLIBRARY == "GM") else commands))
    for (cmds_name, commands) in batch_zip: SubCommand(commands, cmds_name, isCmdSequence=use_IM)
    if  (len(webp_rendercmds) > 0): SubCommand(webp_rendercmds, cmd_names[3], isCmdSequence=True)
    if  (len(ffmpeg_commands) > 0): SubCommand(ffmpeg_commands, cmd_names[4], isCmdSequence=True)
    
    print(f"moving outputs to final destinations...")
    checked_outputs = Task.CheckExpectedOutputs(task)
    move_output_cmd = [
        f"cp --verbose --backup=numbered '{work_file}' '{final_dest}'"
        for (work_file, final_dest) in checked_outputs
    ]
    SubCommand(move_output_cmd, logname=None, isCmdSequence=True)
    
    print("\ndone\n")
    return


if __name__ == "__main__":
    print(f"program path: {Globals.PROGRAM_DIR}")
    print(f"this file: {pathlib.Path(__file__)}")
    Main()
