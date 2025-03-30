from pathlib import Path # just for type hints
from tempfile import TemporaryDirectory # just for type hints

PROGRAM_DIR = Path(__file__).parent # default paths for subdirectories are under program's directory
assert(PROGRAM_DIR.is_dir()); # implies '.exists()'.  __file__ returns absolute path, by the way

# toplevel directory: contains 'WORKING_DIR'(s) and 'magicklogs'
TOPLEVEL_NAME = "RGB_TOPLEVEL"
MAGICKLIBRARY = "GM" # GM/IM

# set at runtime in 'CLI.py'
WORKING_DIR:Path|None = None
SRCIMG_PATH:Path|None = None
LOGGING_DIR:Path|None = None

# global reference to prevent tempdir from deleting itself instantly
TEMPDIR_REF:TemporaryDirectory|Path|None = None

# these flags may be set by 'ApplyDebugFlags' or 'ApplyConfig' (Config.py)
# once a flag has been set (True), 'ApplyDebugFlags' will never disable it
DEBUG_PRINT_CMDS:bool|None = None # print commands before passing to 'SubCommand'
DEBUG_PRINT_ONLY:bool|None = None # exit after printing commands; do not execute
DEBUG_PARSE_ONLY:bool|None = None # exit after parsing commandline args and Init
DEBUG_PRINT_GLOBALS = None # print variables during init and 'RGB.PrintGlobals()'

debug_flag_names = ("PRINT_CMDS", "PRINT_ONLY", "PARSE_ONLY", "PRINT_GLOBALS",)
break_limits = {}; break_counts = {}

def DBGFLAG(name:str, value:bool|None = None) -> bool|None:
    """lookup and return debug-flag by name. set value if specified."""
    flag = f"DEBUG_{(name := name.upper())}"
    if not (name in debug_flag_names): raise NameError(f"{flag}");
    if (value is not None): globals()[flag] = value; return value;
    else: return eval(flag, globals());

def Break(name:str) -> None:
    """check debug-flag and conditionally exit."""
    if not DBGFLAG(ID := name.upper()): return;
    break_counts[ID] = break_counts.get(ID,0)+1
    if break_counts[ID] >= break_limits.get(ID,0):
        print(f"[DEBUG_{ID}] exiting!!"); exit(0);
    print(f"[DEBUG_{ID}_BREAK{break_counts[ID]}]")
    return

def ApplyDebugFlags(debug_flags: list):
    if (len(debug_flags) > 0): print(f"applying debug-flags: {debug_flags}");
    if len(unknown := [F for F in debug_flags if F not in debug_flag_names]):
        print(f"[ERROR] input contains unrecognized debug-flags: {unknown}")
        raise NameError(f"[ApplyDebugFlags] invalid debug-flags: {unknown}")
    
    global break_limits
    for flag_name in debug_flag_names:
        if not (wasPassed := (flag_name in debug_flags)) or (global_val := DBGFLAG(flag_name)): continue;
        if (global_val != (new_val := DBGFLAG(flag_name, wasPassed))): # 'wasPassed' is always True here.
            # break_limits[flag_name] = 0; break_counts[flag_name] = 0 # reset if flag changed
            print(f"set debug_flag '{flag_name}': {new_val}")
        limit = break_limits.get(flag_name,0)
        limit += debug_flags.count(flag_name)
        break_limits[flag_name] = limit
    
    # auto-enable 'DEBUG_PRINT_CMDS' when 'DEBUG_PRINT_ONLY'
    if (DEBUG_PRINT_ONLY and (not DEBUG_PRINT_CMDS)):
        print(f"set debug_flag 'PRINT_CMDS': True")
        DBGFLAG("PRINT_CMDS", True)
    
    return


def UpdateGlobals(workdir:Path, srcimg:Path, logdir:Path, dbgprint: bool | None=None):
    """ specifying dbgprint here will also affect 'RGB.PrintGlobals()'\n
    'srcimg' must be located within 'workdir'
    :param workdir: subdirectory where images are processed
    :param srcimg: (potentially) preprocessed source image
    :param logdir: log directory
    :param dbgprint: sets (global) DEBUG_PRINT_GLOBALS if specified """
    global DEBUG_PRINT_GLOBALS
    assert (srcimg.is_relative_to(workdir)), "'srcimg' should be within 'workdir'"
    if(dbgprint is None): dbgprint = DEBUG_PRINT_GLOBALS;
    DEBUG_PRINT_GLOBALS = dbgprint
    
    if dbgprint: print(f"{'='*100}"); print(f"[initializing globals]");
    global WORKING_DIR; WORKING_DIR = workdir
    global SRCIMG_PATH; SRCIMG_PATH = srcimg
    global LOGGING_DIR; LOGGING_DIR = logdir
    
    assert(workdir.is_dir())
    assert(workdir.parent.name == TOPLEVEL_NAME), f"work directory expected to be under '{TOPLEVEL_NAME}'";
    assert(SRCIMG_PATH.is_relative_to(WORKING_DIR)), f"srcimg_path expected to be under '{TOPLEVEL_NAME}'";
    
    if not dbgprint: return
    print(f"DEBUG_PRINT_GLOBALS: {DEBUG_PRINT_GLOBALS}")
    print(f"DEBUG_PRINT_CMDS: {DEBUG_PRINT_CMDS}")
    print(f"DEBUG_PRINT_ONLY: {DEBUG_PRINT_ONLY}")
    print("")
    print(f"WORKING_DIR: {WORKING_DIR}")
    print(f"SRCIMG_PATH: {SRCIMG_PATH}")
    print(f"LOGGING_DIR: {LOGGING_DIR}")
    print("")
    print(f"break_limits: {break_limits}")
    print(f"break_counts: {break_counts}")
    print(f"{'='*100}\n")
    return
