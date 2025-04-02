import pathlib

import Globals
import RGB


class ColorRemapT():
    def __init__(self,
        whiteBlack:tuple[str|None,str|None]|None,
        wb_fuzzing:tuple[int,int],
        edge_color:str|None,
        edgeRadius:int):
      self.whiteBlack = whiteBlack
      self.wb_fuzzing = wb_fuzzing
      self.edge_color = edge_color
      self.edgeRadius = edgeRadius
      if self.whiteBlack is not None:
        assert(Globals.MAGICKLIBRARY == 'GM'), "color-replacement is GraphicsMagick-only"
        assert(all([(percent >= 0) and (percent <= 100) for percent in self.wb_fuzzing]))
      return


class TaskT():
  def __init__(self,
        baseimg:pathlib.Path,
        workdir:pathlib.Path,
        checksum:str,
        crop:str|None, grav:str,
        rescales:list[str]|None,
        color_options:ColorRemapT,
        frame_format:str,
        output_filename:str,
        output_directory:pathlib.Path,
        output_fileformats:list[str],
    ):
    self.image_source = baseimg
    self.image_md5sum = checksum
    self.working_path = workdir
    self.primary_format = frame_format
    self.output_filename = output_filename
    self.output_directory = output_directory
    self.output_fileformats = output_fileformats
    
    self.crop = ParseCrop(crop, grav)
    self.rescales = (rescales if(rescales is not None) else ['100%'])
    
    (
      self.whiteBlack,
      self.wb_fuzzing,
      self.edge_color,
      self.edgeRadius,
    ) = color_options.__dict__.values()
    
    self.frame_formats = [ frame_format, ]
    if (('APNG' in output_fileformats) or ('MP4' in output_fileformats)): self.frame_formats.append('PNG');
    
    self.did_preprocess_img = False
    self.image_preprocessed = None # output-path of ImagePreprocess; if edge-color or whiteBlack-remapping are enabled
    self.preprocessing_list = [] # tuple of (commands, output_path) - outputs are color-swapped, scaled and/or cropped
    self.expected_outputs = []
    
    assert(frame_format in ('MPC', 'MIFF'))
    assert(output_filename.endswith('_RGB'))
    assert(output_directory.exists() and output_directory.is_dir())
    return


def ParseCrop(cropstr:str|None, gravity:str="center") -> str:
    valid_chars = "0123456789%x+-"
    if ((cropstr is None) and (cropstr != '')): return '';
    if not all([char in valid_chars for char in cropstr]):
        print(f"[ERROR] invalid crop value: '{cropstr}'"); return '' 
    
    # plus/minus-signs interfere with 'isdigit/isdecimal' checks
    # need to preserve value before stripping/splitting them out
    index = -1
    signs = {(index, C) for C in ('+','-') for _ in range(2) if ((index := cropstr.find(C, index+1)) != -1)}
    if (len(signs) > 2): raise Exception(f"crop has too many plus/minus-signs: '{cropstr}' ({len(signs)})");
    
    # replacing offset only
    #sign_offsets = [(I if ((I := cropstr.find(sign)) != -1) else None) for sign in '+-']
    
    # divider between size and offsets
    midpoint = (min([I for (I,_) in signs]) if (len(signs) > 0) else len(cropstr))
    size_str = cropstr[:midpoint]
    remaindr = cropstr[midpoint:]
    
    (W,ch,H) = ((S if (S != '') else None) for S in size_str.partition('x'))
    # if only one size was given with an 'x', the other defaults 0 (image-size)
    # if only one size was given, with no 'x', it applies to both
    #    empty: [    +X+Y] -> [size: 0x0] (default size of image)
    #   single: [  96+X+Y] -> [size: 96x96]
    #   suffix: [640x+X+Y] -> [size: 640x0] (set width, default height)
    #   prefix: [x480+X+Y] -> [size: 0x480] (set height, default width)
    if all(((S is None) or (S == 'x')) for S in (W,ch,H)): (W,H) = ('0','0'); # no size specified at all
    elif (ch == 'x'): (W, H) = (('0' if W is None else W), ('0' if H is None else H)); # defaults if 'x' was present
    elif (ch is None): (W, H) = ((H if W is None else W), (W if H is None else H)); # without 'x', set both axes
    
    # both parts should be set by this point
    if ((W is None) or (H is None)): raise Exception(f"failed to parse crop-size: '{size_str}'");
    
    # percentages
    if any(percentage_check := [D.endswith('%') for D in (W, H)]):
        (W, H) = [(N if (N := D.removesuffix('%')).isdigit() else None) for D in (W, H)]
        if (None in (W, H)): raise Exception(f"invalid percentage in crop-size: '{size_str}'");
        if not all((N.isdigit() if not B else ((int(N) > 0)) and (int(N) < 100)) for (B,N) in zip(percentage_check, (W,H))):
            raise Exception(f"percentage values out of range: ({W}x{H}); (valid range: [1-99])")
    
    # TODO: handle tile-cropping ('@' suffix): https://usage.imagemagick.org/crop/#crop_equal
    
    segments = [W, H, *[S for S in remaindr.replace('+',' ',2).replace('-',' ',2).split(' ',maxsplit=2) if (S != '')]]
    if not all([segment.isdigit() for segment in segments]): raise Exception(f"[ERROR] non-digit in crop: {segments}");
    
    # integer conversion and re-applying signs
    crop = [*[int(segment) for segment in segments], *[0 for _ in range(4-len(segments))]]; assert(len(crop) == 4);
    for (I, (_,sign)) in zip(range(4-len(signs), 4), signs): crop[I] *= (-1 if (sign == '-') else 1);
    
    (W, H, X, Y) = crop
    if ((W, H, X, Y) == (0, 0, 0, 0)): return '';
    if not (all((I >= 0) for I in (W,H))): raise Exception(f"[ERROR] crop-size must not be negative: ({W}x{H})");
    (W, H) = [(f"{N}%" if B else N) for (B,N) in zip(percentage_check, (W,H))] # re-applying percents
    
    #cropstr = "[{}x{}{:+d}{:+d}]".format(W,H,X,Y)
    # '+repage' output to remove virtual-canvas (crop doesn't actually resize the canvas)
    cropstr = "+repage -gravity {} -crop {}x{}{:+d}{:+d} +repage".format(gravity,W,H,X,Y)
    return cropstr


def ParseScales(rescales:list[str]) -> list[tuple[int,str]]:
    results = []
    for scale in rescales:
        isPercent = scale.endswith('%')
        isMultiplier = scale.endswith('x')
        scalestr = scale.removesuffix('x').removesuffix('%')
        
        isValid = (isPercent or isMultiplier) and (
            scalestr.isdigit() if isPercent else 
            ((scalestr.count('.') <= 1) and scalestr.replace('.','').isdigit())
        )
        if not isValid: print(f"[ERROR] invalid scale: '{scale}'"); continue;
        
        value = 0
        if isPercent: value = int(scalestr)
        if isMultiplier: value = int(float(scalestr)*100) # percent conversion
        
        if (value <= 0): print(f"[ERROR] invalid scale (bad value): '{scale}' ({value})");
        else: results.append((value, ("" if (value == 100) else f"_scale{value}")))
    return results


def FillExpectedOutputs(task:TaskT) -> list[str]:
    rescales = task.rescales
    filename = task.output_filename
    output_directory = task.output_directory
    output_fileformats = task.output_fileformats
    
    task.expected_outputs.clear()
    for (scaleval, scalestr) in ParseScales(rescales):
        for FMT in output_fileformats:
            new_name = f"{filename}{scalestr}.{(fmt := FMT.lower())}"
            final_destination = output_directory/new_name
            
            renamelimit = 100; renamecount=1
            while(final_destination.exists() and (renamecount < renamelimit)):
                print(f"[WARNING] final destination already exists: '{final_destination.absolute()}'")
                new_name = f"{new_name.removesuffix(f'.{fmt}').removesuffix(f'_{renamecount-1}')}_{renamecount}.{fmt}"
                final_destination = output_directory/new_name
                print(f"    renaming: '{final_destination.absolute()}'")
                renamecount += 1
            if renamecount >= renamelimit: print(f"hit rename limit. exiting."); exit(3);
            assert(final_destination.parent.exists());
            assert(final_destination.parent.absolute() == output_directory.absolute());
            print(f"final destination: '{final_destination.absolute()}'")
            task.expected_outputs.append((FMT, (scaleval,scalestr),final_destination))
    
    NL = '\n  '
    dests = sorted([expected[-1] for expected in task.expected_outputs] )
    print(f"expected outputs: {NL}{NL.join(str(x.name) for x in dests)}")
    return task.expected_outputs


def CheckExpectedOutputs(task:TaskT) -> list[tuple[pathlib.Path,pathlib.Path]]:
    results = []
    for (_, _, final_dest) in task.expected_outputs:
        work_file = task.working_path / final_dest.name
        print(f"checking: {work_file}")
        if work_file.exists(): results.append((work_file, final_dest));
        else: print(f"[WARNING] expected output does not exist! ({work_file})");
    return results


def ImagePreprocess(task:TaskT) -> pathlib.Path | None:
    baseimg = task.image_source
    workdir = task.working_path
    task.image_preprocessed = None
    task.preprocessing_list.clear()
    scales = ParseScales(task.rescales)
    
    current_img = baseimg
    if task.whiteBlack is not None:
        for (new_color, fuzzpcent, colorname) in zip(task.whiteBlack, task.wb_fuzzing, ('white','black')):
            if new_color is None: continue;
            outpath = workdir / f"srcimg_replace_{colorname}.png"
            replace_cmd = f"convert 'PNG:{current_img}' -fuzz {fuzzpcent}% {RGB.RecolorStr(colorname, new_color)} 'PNG:{outpath}'"
            task.preprocessing_list.append((replace_cmd, outpath))
            current_img = outpath # 'replace_white.png' is used as base for 'replace_black.png'
        
        if (current_img != baseimg):
            compositepath = workdir / f"srcimg_WB_recolor.png"
            composite_cmd = f"composite 'PNG:{current_img}' 'PNG:{baseimg}' -compose Atop 'PNG:{compositepath}'"
            task.preprocessing_list.append((composite_cmd, compositepath))
            current_img = compositepath # keep as base for edge-highlight
        # the last composite only exists to discard the transparency that always gets filled by replace_black
        # for some reason, replacing 'Black' will also fill all transparent regions - replacing white doesn't
        # (the same behavior occurs when hex codes are used instead of name; #000000 / #000000FF / #00000000)
    
    if task.edge_color is not None:
        (recolor_cmd, edge_image) = RGB.EdgeHighlight(baseimg, task.edge_color, task.edgeRadius) # edge-detect baseimg, NOT current
        task.preprocessing_list.append((recolor_cmd, edge_image))
        baseimg = current_img; current_img = edge_image
        # ^ preserving 'replace_black.png' in baseimg for final composite
    
    if (current_img != baseimg): # final composite and updating task.image_source
        final_output = workdir / "srcimg_preprocessed.png"
        compositecmd = f"composite 'PNG:{current_img}' 'PNG:{baseimg}' -compose Atop 'PNG:{final_output}'"
        task.preprocessing_list.append((compositecmd, final_output))
        task.image_preprocessed = current_img = final_output
    
    for (scale_value, scale_suffix) in scales:
        scale_text = ('' if (scale_value == 100) else f"-scale {scale_value}%")
        new_img = workdir/f"srcimg{scale_suffix}.{task.primary_format.lower()}"
        command = f"convert 'PNG:{current_img}' {task.crop} -strip {scale_text} '{task.primary_format.upper()}:{new_img}'"
        task.preprocessing_list.append((command, new_img))
    
    task.did_preprocess_img = True
    return task.image_preprocessed # still None unless edge/WB-recoloring was performed


# expects parsed scale-strings (Task.ParseScales)
def SetupFramesDirectories(task:TaskT, scales:list[tuple[int,str]]):
    workdir = task.working_path
    assert(workdir.exists() and workdir.is_dir())
    
    directories = []
    for frameformat in task.frame_formats:
        for (scale,scalesuffix) in scales:
            srcimg = workdir/f"srcimg{scalesuffix}.{task.primary_format.lower()}"
            frames_directory = workdir/f"{frameformat.lower()}_frames{scalesuffix}"
            if frames_directory.exists(): assert(frames_directory.is_dir());
            else: frames_directory.mkdir();
            directories.append({
                "srcimg": srcimg,
                "scale": (scale, scalesuffix),
                "frameformat": frameformat.upper(),
                "source_format": task.primary_format,
                "frames_directory": frames_directory,
            })
    return directories


def GenerateFrames(task:TaskT, enumRotations:list[tuple[str,str]]) -> tuple[list[str],list[str],list[str],list[str],list[str]]:
    assert(task.image_source.exists() and (task.image_source.parent == task.working_path))
    assert(task.working_path.exists() and task.working_path.is_dir())
    assert(len(task.frame_formats) > 0)
    index_len = len(enumRotations[0][0]) # number of digits to use in printf sequence 
    
    scales = ParseScales(task.rescales)
    directories = SetupFramesDirectories(task, scales)
    
    preprocess_commands = (
        [] if (not task.did_preprocess_img) else
        [C for (C,_) in task.preprocessing_list]
    )
    if (not task.did_preprocess_img):
        new_srcimg = ImagePreprocess(task) # TODO: need to update global SRCIMG?
        for (command, out_img) in task.preprocessing_list:
            # if out_img == final_img: preprocess_commands.append(command); continue;
            # if out_img.exists(): print(f"skipping preprocessing (already exists): '{out_img}'"); continue;
            preprocess_commands.append(command)
    
    # PNG frames should just be directly converted from the primary format (MPC/MIFF)
    # only generate frames for primary format; frames in other formats will be converted from these
    source_frame_dirs = [ DIR for DIR in directories if (DIR['frameformat'] == task.primary_format) ]
    
    framelists = [[(
          (index,rotation), (DIR['frames_directory']/f"frame{index}.{DIR['frameformat'].lower()}")
        ) for (index,rotation) in enumRotations
    ] for DIR in source_frame_dirs ]
    
    framegen_commands = [
        f"convert '{DIR['source_format']}:{DIR['srcimg']}' -scene {index} -modulate 100,100,{rotation} '{DIR['frameformat']}:{frame}'"
        for (DIR, framelist) in zip(source_frame_dirs, framelists)
        for ((index, rotation), frame) in framelist
    ]
    
    # PNG-frames are converted from the primary (MPC/MIFF) frames instead of generating them all seperately
    derivative_mapping = [
        (SRC, DER)
        for DER in directories
        for SRC in source_frame_dirs
        if ((DER['frameformat'] != task.primary_format) and 
            (DER['scale'] == SRC['scale']))
    ]
    
    for (SRC, DER) in derivative_mapping:
        from_glob = f"'{task.primary_format}:{SRC['frames_directory']}/frame*.{task.primary_format.lower()}'"
        dest_glob = f"'{DER['frameformat']}:{DER['frames_directory']}/frame%0{index_len}d.{DER['frameformat'].lower()}'"
        matte_arg = ('+matte' if ('APNG' in task.output_fileformats) and (DER['frameformat']=='PNG') else '')
        framegen_commands.append(f"convert {from_glob} {matte_arg} +adjoin {dest_glob}")
        # '+matte' removes alpha channel; ensuring black background for APNG (transparency renders as white in browsers)
    
    
    render_commands = []
    webp_rendercmds = []
    ffmpeg_commands = []
    ffmpeg_begin = "ffmpeg -hide_banner -y -f image2 -framerate 30 -pattern_type sequence -i"
    webp_options = "-quality 100 -define webp:thread-level=1 -define webp:lossless=true -define webp:method=6 -define webp:use-sharp-yuv=true"
    
    for (outfmt, (scaleval, scalestr), final_destination) in task.expected_outputs:
        srcfmt = ("PNG" if (use_ffmpeg := (outfmt in ('APNG','MP4'))) else task.primary_format)
        framedir = task.working_path / f"{srcfmt.lower()}_frames{scalestr}"
        work_file = task.working_path / final_destination.name
        
        if use_ffmpeg:
            apng_opts = ("-ignore_loop false -plays 0 -default_fps 30" if (outfmt == 'APNG') else '') # enables animation looping
            ffmpeg_commands.append(f"{ffmpeg_begin} '{framedir}/frame%0{index_len}d.{srcfmt.lower()}' {apng_opts} '{work_file}'")
            continue
        
        # webp output is ImageMagick-only; no animation in GraphicsMagick
        (magick_convert, opts) = (("convert-im6.q16", webp_options) if (isWEBP := (outfmt == "WEBP")) else ("convert", ""))
        cmd = f"{magick_convert} '{srcfmt}:{framedir}/frame*.{srcfmt.lower()}' {opts} -adjoin '{outfmt}:{work_file}'"
        if isWEBP: webp_rendercmds.append(cmd);
        else: render_commands.append(cmd);
    
    return (preprocess_commands, framegen_commands, render_commands, webp_rendercmds, ffmpeg_commands)



def ParseCropFuzzing():
    """tests 'ParseCrop()' with a bunch of random inputs"""
    croptests = [
        "640x480+64+128",
        "640x480-64-128",
        "640x480+64-128",
        "640x480-64+128",
        "640x480",
        "640x480+64",
        "640x480+0+128",
        "640x480+0-128",
        "640x",
        "x480",
        # percentages
        "50%",
        "360x75%",
        "x25%+3-4",
        "25%x+3-4",
        "15%x240+1+2",
        "50%x75%",
        "75%+120+240",
        # these should all return empty strings
        "0x0+0+0",
        "0","0-0+0",
        "0x0","x0","0x",
        "+0+0","-0-0",
        "", None,
    ]
    # these are expected to throw an exception
    croptests_badstr = [
        "640x480+64+128+123",
        " ", '-',
        "x+-",
        "-+x",
        "-x+",
        "+x-",
        "1 2 3 4",
        "1-2+3-4",
        "1x2x3x4",
        "xx480"
        "-64+128",
        "x-6+1",
        "+111-222+640x480",
        "+640x+480",
        "999%",
        "50%75%",
        "-10%",
        "0x0%+0+0",
        "0%x+0",
        "640x480+10%+10%",
    ]
    
    croptest_results = [(T, ParseCrop(T)) for T in croptests]
    bad_strs_results = []
    for bad_str in croptests_badstr:
        try: bad_strs_results.append((bad_str, ParseCrop(bad_str)));
        except Exception as E: bad_strs_results.append((bad_str, E));
    
    print(croptest_results)
    print(bad_strs_results)
    return (croptest_results, bad_strs_results)
