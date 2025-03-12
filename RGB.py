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


def GenerateCommands(stepsize:float, writeMPC:bool=True, writePNG:bool=False, writeBatchfile:bool=True):
    workdir = Globals.WORKING_DIR; assert(workdir.exists() and workdir.is_dir())
    assert(workdir.parent.name == Globals.TOPLEVEL_NAME), f"working directory expected to be under '{Globals.TOPLEVEL_NAME}'";
    assert(Globals.SRCIMG_PATH.is_relative_to(Globals.WORKING_DIR)), f"srcimg expected to be under '{Globals.TOPLEVEL_NAME}'";
    assert(writeMPC or writePNG), "GenerateCommands expects at least one target format"
    
    magick_convert = "convert"
    magick_mogrify = "mogrify"
    if (Globals.MAGICKLIBRARY == "IM"):
        writeBatchfile = False # 'batch' is GM-only
        magick_convert = "convert-im6.q16"
        magick_mogrify = "mogrify-im6.q16"
    elif not writeBatchfile: # need to prefix subcommands if not writing to batchfile 
        magick_convert = f"gm {magick_convert}"
        magick_mogrify = f"gm {magick_mogrify}"
    
    cache_srcimg_path = workdir / "cached_srcimg.mpc" # 'MPC': magick persistent cache
    cache_srcimg_cmd = f"{magick_convert} '{Globals.SRCIMG_PATH}' '{cache_srcimg_path}'"
    cmdlist = [cache_srcimg_cmd]
    
    frameformats = [ A for (A,B) in zip(["MPC","PNG"],[writeMPC,writePNG]) if B ]
    framegen_dir = { "MPC": None, "PNG": None, }
    framegen_cmd = { "MPC": None, "PNG": None, }
    
    for frameformat in frameformats:
        frames_directory = workdir/f"hue_rotations_{frameformat.lower()}"
        if frames_directory.exists(): assert(frames_directory.is_dir());
        else: frames_directory.mkdir();
        framegen_dir[frameformat] = frames_directory
    
    rotation_strs = HueRotations(stepsize)
    
    if (writeMPC or writePNG):
        frameformat = frameformats[0]
        frames_directory = framegen_dir[frameformat]
        framegen_cmd[frameformat] = [
            magick_convert+" '{0}' -modulate 100,100,{1} '{2}'".format(
                cache_srcimg_path,
                hue_rotation,
                f"{frames_directory}/{hue_rotation}.{frameformat.lower()}"
            ) for hue_rotation in rotation_strs
        ]
        cmdlist.extend(framegen_cmd[frameformat])
    
    # if both formats are enabled, simply convert MPC to PNG (instead of modulating twice)
    if (writeMPC and writePNG):
        assert(framegen_cmd['MPC'] is not None), "framegen_cmd 'MPC' should have already been written! (always first format)"  
        if (Globals.MAGICKLIBRARY == "IM"): # ImageMagick-mogrify can perform PNG conversion in a single command 
            convert_frames_PNG = [f"{magick_mogrify} -format png -path '{framegen_dir['PNG']}' '{framegen_dir['MPC']}/*.mpc'"]
        else: # GraphicsMagick-mogrify creates a retarded directory structure ('-output-directory' always appends absolute-path of inputs); generate 'convert' command-list instead
            convert_frames_PNG = [
                magick_convert+" '{0}' '{1}'".format(
                    f"{framegen_dir['MPC']}/{hue_rotation}.mpc",
                    f"{framegen_dir['PNG']}/{hue_rotation}.png"
                ) for hue_rotation in rotation_strs
            ]
        framegen_cmd['PNG'] = convert_frames_PNG
        cmdlist.extend(convert_frames_PNG)
    
    batchfile = None
    batch_cmd = None
    if writeBatchfile:
        batchfile = SaveCommand("generate_frames", cache_srcimg_cmd)
        for (K,V) in framegen_cmd.items():
            if (V is None): continue;
            SaveCommand(f"generate_frames_{K.lower()}", V)
            SaveCommand("generate_frames", V, append=True)
        # batch_cmd can use '-tap-mode on'/'-feedback on' for PASS/FAIL info
        batch_cmd = f"gm batch -echo on -stop-on-error on '{batchfile}'"
    
    # frames generated for GIF output need preprocessing to reduced (255) color-palette
    # 'fuzz' and 'treedepth' options have no effect (IM and GM), regardless of value and remap/morph options. (output has identical checksum)
    remap_arg = ("+remap" if (Globals.MAGICKLIBRARY == "IM") else "") # IM-only; GM does not recognize 'remap'
    use_morph = False; morph_arg = ("-morph 10" if use_morph else "")
    
    # imagemagick creates a gigantic multi-gigabyte log if '-verbose' and '-monitor' are enabled
    convert_cmd = ("gm convert -verbose -monitor" if (Globals.MAGICKLIBRARY=="GM") else magick_convert)
    output_filename = f"{Globals.SRCIMG_PATH.with_suffix('').name}_RGB.gif".removeprefix('srcimg_')
    frameformat = frameformats[0].lower(); frames_directory = framegen_dir[frameformat.upper()] # uses "MPC" unless "PNG" is only format
    createGIF = f"{convert_cmd} '{frames_directory}/*.{frameformat}' {morph_arg} {remap_arg} '{workdir/output_filename}'"
    cmdlist.append(createGIF)
    
    if writeBatchfile: return ([batch_cmd, createGIF], batchfile);
    return (cmdlist, None)


# TODO: ffmpeg mp4, graphicsmagick MPEG (.mpg) output? APNG?
# TODO: generate colormap without 'remap'

# TODO: transcode input image to PNG and downscale/crop if necessary
# transparency doesn't seem to be a problem, as long as source was PNG

# TODO: handle GIF/video inputs (divide into frames and interpolate between them)
