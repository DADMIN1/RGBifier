from math import log10
import pathlib
import Globals

# defined here instead of in 'Globals' to ensure the values are checked within the scope/context of this file
def PrintGlobals(dbgprint:bool = False):
    """no-op unless dbgprint or DEBUG_PRINT_GLOBALS"""
    if not (dbgprint or Globals.DEBUG_PRINT_GLOBALS): return
    print(f"{'='*100}"); print("[printing globals]")
    print(f"PROGRAM_DIR: {Globals.PROGRAM_DIR}")
    print(f"WORKING_DIR: {Globals.WORKING_DIR}")
    print(f"SRCIMG_PATH: {Globals.SRCIMG_PATH}")
    print(f"TEMPDIR_REF: {Globals.TEMPDIR_REF}")
    print("")
    print(f"break_limits: {Globals.break_limits}")
    print(f"break_counts: {Globals.break_counts}")
    print(f"{'='*100}\n")
    return


# same as normal range, except with floats. does not include 'end' value
def FloatRange(start:float, end:float, interval:float, precision:int=6) -> list[float]:
    return [(I/(10**precision)) for I in range(*[int(F*(10**precision)) for F in (start, end, interval)])]

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
    print(f"stepsize: {stepsize:.{estPrecision}f} | rotation steps: {len(rotation_strs)}")
    return rotation_strs


def EnumRotations(stepsize:float, length:int = 0) -> list[tuple[str,str]]:
    assert(length >= 0), "rotation length must be positive";
    rotation_strs = HueRotations(stepsize)
    if (length != 0):
        extended_rotations = rotation_strs.copy()
        while(len(extended_rotations) < length): extended_rotations.extend(rotation_strs);
        rotation_strs = extended_rotations[:length]; assert(len(rotation_strs) == length);
    padding = 1 + int(log10(len(rotation_strs)))
    enumRotations = [
        (str(index).zfill(padding), rotation)
        for (index, rotation) in enumerate(rotation_strs)
    ]
    return enumRotations


def SaveCommand(filename: str, command:str|list[str], append:bool=False) -> pathlib.Path:
    """ writes/appends commands to file; returns written filepath"""
    cmdlist = (command if(isinstance(command, list)) else [command]); del command;
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


# TODO: refactor or remove
def GenerateCommands(stepsize:float, writeMPC:bool=True, writePNG:bool=False, writeBatchfile:bool=True, output_name:str|None=None):
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
        frames_directory = workdir/f"frames_{frameformat.lower()}"
        if frames_directory.exists(): assert(frames_directory.is_dir());
        else: frames_directory.mkdir();
        framegen_dir[frameformat] = frames_directory
    
    rotation_strs = HueRotations(stepsize)
    padding = 1 + int(log10(len(rotation_strs)))
    enumRotations = [
        (str(index).zfill(padding), rotation)
        for (index, rotation) in enumerate(rotation_strs)
    ]
    
    if (writeMPC or writePNG):
        frameformat = frameformats[0]
        frames_directory = framegen_dir[frameformat]
        framegen_cmd[frameformat] = [
            magick_convert+" '{0}' -scene {1} -modulate 100,100,{2} '{3}'".format(
                cache_srcimg_path,
                index, hue_rotation,
                f"{frames_directory}/frame{index}.{frameformat.lower()}"
            ) for (index, hue_rotation) in enumRotations
        ]
        cmdlist.extend(framegen_cmd[frameformat])
    
    # if both formats are enabled, simply convert MPC to PNG (instead of modulating twice)
    if (writeMPC and writePNG):
        assert(framegen_cmd['MPC'] is not None), "framegen_cmd 'MPC' should have already been written! (always first frameformat)"
        if (Globals.MAGICKLIBRARY == "IM"): # ImageMagick-mogrify can perform PNG conversion in a single command 
            convert_frames_PNG = [f"{magick_mogrify} -format png -path '{framegen_dir['PNG']}' '{framegen_dir['MPC']}/frame*.mpc'"]
        else: # GraphicsMagick-mogrify creates a retarded directory structure ('-output-directory' always appends absolute-path of inputs); generate 'convert' command-list instead
            convert_frames_PNG = [
                magick_convert+" '{0}' '{1}'".format(
                    f"{framegen_dir['MPC']}/frame{index}.mpc",
                    f"{framegen_dir['PNG']}/frame{index}.png"
                ) for (index, hue_rotation) in enumRotations
            ]
        framegen_cmd['PNG'] = convert_frames_PNG
        cmdlist.extend(convert_frames_PNG)
    
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
    def_delay = False; delay_arg = (f"-delay {int(stepsize)}" if def_delay else "")
    disposing = "-dispose None" # "Undefined | Background | Previous"
    GIFargstr = f"{morph_arg} {delay_arg} {disposing} {remap_arg}".strip()
    
    # imagemagick creates a gigantic multi-gigabyte log if '-verbose' and '-monitor' are enabled
    convert_cmd = ("gm convert -verbose -monitor" if (Globals.MAGICKLIBRARY=="GM") else magick_convert)
    output_name = (output_name if output_name else f"{Globals.SRCIMG_PATH.with_suffix('').name}_RGB".removeprefix('srcimg_')) 
    frameformat = frameformats[0].lower(); frames_directory = framegen_dir[frameformat.upper()] # uses "MPC" unless "PNG" is only format
    createGIF = f"{convert_cmd} '{frames_directory}/frame*.{frameformat}' {GIFargstr} '{workdir/output_name}.gif'"
    createMP4 = f"ffmpeg -hide_banner -y -f image2 -framerate 30 -pattern_type glob -i '{framegen_dir["PNG"]}/frame*.png' '{workdir/output_name}.mp4'"
    # '-y' overwrites output without asking
    # '-pattern_type glob' is 'image2'-specific. ffmpeg filename format (both in/out) is normally like: 'asdf-%03d.jpeg'
    
    return (cmdlist, batch_cmd, (createGIF, createMP4))


# TODO: generate colormap without 'remap'
# TODO: handle GIF inputs (divide into frames and interpolate between them)
# TODO: hwaccel with ffmpeg


def convertCMD(srcimg:pathlib.Path, cmd_mid:str, out_name:str, fmt_in='png', fmt_out='png'):
    outpath = Globals.WORKING_DIR / f"{out_name}.{fmt_out.lower()}"
    convert = f"convert '{fmt_in.upper()}:{srcimg}' {cmd_mid} '{fmt_out.upper()}:{outpath}'"
    return (convert, outpath)

# 0x00FF00AA -> "'#00FF00AA'"
def HexString(num:int): return "'#{:08X}'".format(num);

# input hex-strings must be length 8, or the value will be shifted due to padding in HexString
def RecolorStr(old:str, new:int|str):
    new = (HexString(new) if isinstance(new, int) else HexString(int(new,16)) if new.startswith('0x') else new.title())
    return f"-fill {new} -opaque {old.title()}"

def EdgeHighlight(srcimg:pathlib.Path, edge_color:int|str, edge_radius) -> tuple[str, pathlib.Path]:
    """returns recolor-command and output path"""
    recolor_str = f"{RecolorStr('Black', 'Transparent')} {RecolorStr('White', edge_color)}"
    if (Globals.MAGICKLIBRARY == "IM"): # for some reason IM needs rgba specified, and fuzz cannot be 100%
        recolor_mid = f"-threshold 25% -channel rgba -modulate 100,0 -edge {edge_radius} -fuzz 99% {recolor_str}"
        # also, '-threshold' is required, otherwise the edge-detection goes insane and traces just about every pixel. Order matters; the outcome is slightly different if you move 'threshold' later.
    else: # saturation 0% and fuzz 100% to isolate all the non-white pixels
        recolor_mid = f"-modulate 100,0 -edge {edge_radius} -fuzz 100% {recolor_str}"
    return convertCMD(srcimg, recolor_mid, "srcimg_edge")


def EdgeHighlightCMD(edge_color:int|str, edge_radius) -> str:
    """returns partially-constructed command - format-string with an unfilled input-path and no output"""
    recolor_str = f"{RecolorStr('Black', 'Transparent')} {RecolorStr('White', edge_color)}"
    if (Globals.MAGICKLIBRARY == "IM"): # for some reason IM needs rgba specified, and fuzz cannot be 100%
        recolor_mid = f"-threshold 25% -channel rgba -modulate 100,0 -edge {edge_radius} -fuzz 99% {recolor_str}"
        # also, '-threshold' is required, otherwise the edge-detection goes insane and traces just about every pixel. Order matters; the outcome is slightly different if you move 'threshold' later.
    else: # saturation 0% and fuzz 100% to isolate all the non-white pixels
        # recolor_mid = f"-operator all Threshold-Black 25% -operator all Threshold-White 75% -modulate 100,0 -edge {edge_radius} -fuzz 100% {recolor_str}"
        recolor_mid = f"-modulate 10,0 -edge {edge_radius} -fuzz 100% {recolor_str}"
    return "convert {0} -contrast -contrast " + recolor_mid  # doesn't contain output; needs to be appended manually


def argstr_GIF(numRotations:int|None = None):
    # frames generated for GIF output need preprocessing to reduced (255) color-palette
    # 'fuzz' and 'treedepth' options have no effect (IM and GM), regardless of value and remap/morph options. (output has identical checksum)
    remap_arg = ("+remap" if (Globals.MAGICKLIBRARY == "IM") else ' ') # IM-only; GM does not recognize 'remap'
    use_morph = False; morph_arg = ("-morph 10" if use_morph else ' ')
    #use_delay = (Globals.MAGICKLIBRARY == "IM") and (numRotations is not None) and (numRotations > 0) # TODO: for some reason, specifying '-delay' with GraphicsMagick INCREASES speed??!
    use_delay = False
    delay_arg = (f"-delay {max(int(4*(200/numRotations)), 1)}" if use_delay else ' ')
    disposing = "-dispose None" # {None | Undefined | Background | Previous} (default: 'Undefined')
    useDither = False; dithering = ' ' if useDither else "+dither" # '+dither' disables dithering
    GIFargstr = f"{dithering} {morph_arg} {remap_arg} {disposing} {delay_arg}".replace('  ','').strip()
    # dithering prevents color-banding but causes visual static, increases filesize by 50%, and cripples '+remap' operation
    return GIFargstr
