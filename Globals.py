from pathlib import Path # just for type hints

# toplevel directory: contains 'WORKING_DIR'(s) and 'magicklogs'
TOPLEVEL_NAME = "RGB_TOPLEVEL"

# set at runtime in 'CLI.py'
WORKING_DIR:Path|None = None
SRCIMG_PATH:Path|None = None
LOGGING_DIR:Path|None = None

DEBUG_PRINT_GLOBALS = False # print variables during init and 'RGB.PrintGlobals()'
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
    print(f"WORKING_DIR: {WORKING_DIR}")
    print(f"SRCIMG_PATH: {SRCIMG_PATH}")
    print(f"LOGGING_DIR: {LOGGING_DIR}")
    print(f"{'='*100}\n")
    return
