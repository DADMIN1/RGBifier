import pathlib
import Globals

# defined here instead of in 'Globals' to ensure the values are checked within the scope/context of this file
def PrintGlobals(dbgprint:bool = False):
    """no-op unless dbgprint or DEBUG_PRINT_GLOBALS"""
    if not (dbgprint or Globals.DEBUG_PRINT_GLOBALS): return
    print(f"{'='*100}"); print("[printing globals]")
    print(f"WORKING_DIR: {Globals.WORKING_DIR}")
    print(f"SRCIMG_PATH: {Globals.SRCIMG_PATH}")
    print(f"{'='*100}\n")
    return


# same as normal range, except with floats. Includes both 'start' and 'end' values
def FloatRange(start:float, end:float, interval:float, precision:int=6) -> list[float]:
    return [*((I/(10**precision)) for I in range(*[int(F*(10**precision)) for F in (start, end, interval)])), float(end)]

# the interval between the penultimate number and the end can be awkward if it's not a clean divisor
# should it overshoot the end instead? can the start/end be adjusted to compensate?


def DecimalCount(F:float, parts:int=1) -> int | tuple[int,int] | tuple[int,int,int]:
    """ Count digits before or after the decimal-point in a float.
    :param parts: segment selection.
      '0/1': whole/decimal, '2': both,
      '-2': overall length, '3': (overall, both)
    :return: length of a single segment, or tuple of both lengths (and maybe total)."""
    (whole, decimal) = str(float(F)).rsplit('.', maxsplit=1)
    lengths = (len(whole),len(decimal))
    overall = (len(whole)+len(decimal))
    if(parts == 2): return  lengths;
    if(parts ==-2): return  overall;
    if(parts == 3): return (overall, *lengths);
    return lengths[parts]


def HueRotations(stepsize:float) -> list[str]:
    """ produces rotations for a given stepsize
    :param stepsize: hue-rotation per frame.
    :return: list of floating-point numbers as strings (formatted/padded to uniform length)
    """
    estPrecision = DecimalCount(stepsize) # digits after the decimal in stepsize
    # 100 is unchanged, and the domain is 0-200 (mod 200); the cycle completes at 300 (the original again) (GraphicsMagick 'modulate')
    endpoints = ([100, 300] if (stepsize > 0) else [300, 100])
    rotationSteps = FloatRange(*endpoints, stepsize, estPrecision)
    
    topPrecision = max([DecimalCount(num) for num in rotationSteps])
    if (topPrecision != estPrecision): # it shouldn't be possible for a decimal's whole-number multiples to increase in length.
        print(f"[WARNING] float-imprecision detected. FloatRange may be inaccurate.")
        # TODO: retry with a higher precision, within a limit
    
    fmtstr = '{' + f':3.{topPrecision}f' + '}' # assume 3 leading digits (range is 100-300)
    rotation_strs = [fmtstr.format(N) for N in rotationSteps]
    assert((strs_setlen := len(set(rotation_strs))) == (strs_len := len(rotation_strs))), f"name collision occurred! [#rotation_strs: {strs_len} | #unique: {strs_setlen}]";
    print(f"stepsize: {stepsize:.{estPrecision}f} | rotation steps: {strs_len}")
    return rotation_strs


def SaveCommand(filename: str, command:str|list[str], append:bool=False) -> pathlib.Path:
    """ writes/appends commands to file; returns written filepath"""
    cmdlist = (command if(type(command) is list) else [command]); del command
    workdir = Globals.WORKING_DIR; assert (workdir.exists() and workdir.is_dir());
    cmd_dir = workdir/"batchfile"; cmdfile = Globals.WORKING_DIR/cmd_dir/filename;
    if not cmd_dir.exists(): cmd_dir.mkdir(); assert(cmd_dir.is_dir());
    
    savs = ("appending" if (append and cmdfile.exists()) else "saving")
    len_str = f"{len(cmdlist)} command{('s' if(len(cmdlist) > 1) else '')}"
    if(cmdfile.exists() and not append): print(f"\n[WARNING] overwriting existing cmdfile!");
    print(f"{savs} {len_str} to {("new " if(not cmdfile.exists()) else '')}file: {cmdfile}")
    
    with cmdfile.open(mode=('a' if append else 'w'), encoding="utf-8") as newfile:
        newfile.write('\n'.join(cmdlist)); newfile.write('\n\n')
    assert(cmdfile.exists() and cmdfile.is_file())
    return cmdfile


def GenerateCommands(stepsize:float, frameformat="MPC", writeBatchfile:bool=True):
    valid_fmts = ["MPC","PNG"]; frameformat = frameformat.lower()
    workdir = Globals.WORKING_DIR; assert(workdir.exists() and workdir.is_dir())
    assert(workdir.parent.name == Globals.TOPLEVEL_NAME), f"working directory expected to be under '{Globals.TOPLEVEL_NAME}'";
    assert(Globals.SRCIMG_PATH.is_relative_to(Globals.WORKING_DIR)), f"srcimg expected to be under '{Globals.TOPLEVEL_NAME}'";
    assert(frameformat.upper() in valid_fmts), f"unsupported frameformat: '{frameformat}';\n available formats: {valid_fmts}";
    
    if (Globals.MAGICKLIBRARY == "IM"): writeBatchfile = False; # 'batch' is GM-only
    
    frames_directory = workdir/f"hue_rotations_{frameformat}"
    if frames_directory.exists(): assert(frames_directory.is_dir());
    else: frames_directory.mkdir();
    
    cache_srcimg_path = workdir/"cached_srcimg.mpc" # magick persistent cache
    cache_srcimg_str = f"convert '{Globals.SRCIMG_PATH}' '{cache_srcimg_path}'"
    
    rotation_strs = HueRotations(stepsize)
    cmdlist = [cache_srcimg_str, *[
        "convert '{0}' -modulate 100,100,{1} '{2}'".format(
            cache_srcimg_path,
            hue_rotation,
            f"{frames_directory}/{hue_rotation}.{frameformat}"
        ) for hue_rotation in rotation_strs
    ]]
    
    batchfile = (SaveCommand(f"generate_frames_{frameformat}", cmdlist) if writeBatchfile else None)
    use_morph = False; morph_arg = ("-morph 10" if use_morph else "")
    remap_arg = ("+remap" if (Globals.MAGICKLIBRARY=="IM") else "") # IM-only; GM does not recognize
    # batch_cmd can use '-tap-mode on'/'-feedback on' for PASS/FAIL info
    batch_cmd = f"gm batch -echo on -stop-on-error on '{batchfile}'"
    output_filename = f"{Globals.SRCIMG_PATH.with_suffix('').name}_RGB.gif".removeprefix('srcimg_')
    # imagemagick creates a gigantic multi-gigabyte log if '-verbose' and '-monitor' are enabled
    convert_cmd = ("gm convert -verbose -monitor" if (Globals.MAGICKLIBRARY=="GM") else "convert")
    createGIF = f"{convert_cmd} '{frames_directory}/*.{frameformat}' {morph_arg} {remap_arg} '{workdir/output_filename}'"
    # TODO: ffmpeg mp4, graphicsmagick MPEG (.mpg) output? APNG?
    
    #TODO: generate colormap
    if writeBatchfile: return ([batch_cmd, createGIF], batchfile);
    return ([*cmdlist, createGIF], None)


# TODO: transcode input image to PNG and downscale if necessary
# TODO: frames generated for GIF output need preprocessing to reduced (255) color-palette
# transparency doesn't seem to be a problem, as long as source was PNG

# TODO: handle GIF/video inputs (divide into frames and interpolate between them)
