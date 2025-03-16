from pathlib import Path # just for type hints
from tempfile import TemporaryDirectory # just for type hints

# toplevel directory: contains 'WORKING_DIR'(s) and 'magicklogs'
TOPLEVEL_NAME = "RGB_TOPLEVEL"
MAGICKLIBRARY = "GM" # GM/IM

# set at runtime in 'CLI.py'
WORKING_DIR:Path|None = None
SRCIMG_PATH:Path|None = None
LOGGING_DIR:Path|None = None

# global reference to prevent tempdir from deleting itself instantly
TEMPDIR_REF:TemporaryDirectory|None = None

# these flags may be set by 'ApplyConfig' in 'Config.py'
# once a flag has been set (True), 'ApplyConfig' will never disable it
DEBUG_PRINT_CMDS:bool|None = None # print commands before passing to 'SubCommand'
DEBUG_PRINT_ONLY:bool|None = None # exit after printing commands; do not execute
DEBUG_PRINT_GLOBALS = None # print variables during init and 'RGB.PrintGlobals()'

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
    
    if not dbgprint: return
    print(f"DEBUG_PRINT_GLOBALS: {DEBUG_PRINT_GLOBALS}")
    print(f"DEBUG_PRINT_CMDS: {DEBUG_PRINT_CMDS}")
    print(f"DEBUG_PRINT_ONLY: {DEBUG_PRINT_ONLY}")
    print("")
    print(f"WORKING_DIR: {WORKING_DIR}")
    print(f"SRCIMG_PATH: {SRCIMG_PATH}")
    print(f"LOGGING_DIR: {LOGGING_DIR}")
    print(f"{'='*100}\n")
    return
