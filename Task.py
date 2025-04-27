import pathlib
import RGB


class ColorRemapT():
    def __init__(self,
        whiteBlack:tuple[str|None,str|None]|None,
        wb_fuzzing:tuple[int,int],
        thresholds:tuple[int,int],
        edge_color:str|None,
        edgeRadius:int):
      self.whiteBlack = whiteBlack
      self.wb_fuzzing = wb_fuzzing
      self.thresholds = thresholds
      self.edge_color = edge_color
      self.edgeRadius = edgeRadius
      if self.whiteBlack is not None:
        assert(all([(percent >= 0) and (percent <= 100) for percent in self.wb_fuzzing]))
        assert(all([(percent >= 0) and (percent <= 100) for percent in self.thresholds]))
        self.thresholds = (
            (100-thresholds[0]) if (thresholds[0] > 0) else None, # white-threshold tests greater-than, so it's inverted 
                (thresholds[1]) if (thresholds[1] > 0) else None)
      return
    
    def values(self):
        return (
            self.whiteBlack,
            self.wb_fuzzing,
            self.thresholds,
            self.edge_color,
            self.edgeRadius,
        );


class ImageSourceT():
    def __init__(self, srcpath:pathlib.Path, safe_filename:str):
        self.srcpath = srcpath # no extension, could be subdirectory
        self.safe_filename = safe_filename
        self.source_frames:list[pathlib.Path] = []
        self.magic = f"$${safe_filename}$$"
        self.image_format = "PNG"
        self.multisource = False
        self.frame_count = 0
        self.indexlength = 0 # digits in frame_count
        return
    
    def GetNames(self):
        contents = (self.source_frames if self.multisource else [self.srcpath])
        return [F.name.removesuffix(''.join(F.suffixes)) for F in contents]
    
    def QuoteSource(self, length:int=1):
        contents = (self.source_frames if self.multisource else [self.srcpath for _ in range(length)])
        return [f"'{self.image_format}:{F}'" for F in contents]
    


class TaskT():
  def __init__(self,
        workdir:pathlib.Path,
        img_src:ImageSourceT,
        ffprobe_info: dict|None,
        crop:str|None, grav:str,
        rescales:list[str]|None,
        color_options:ColorRemapT,
        primary_format:str,
        output_filename:str,
        output_directory:pathlib.Path,
        output_fileformats:list[str],
    ):
    self.working_path = workdir
    self.image_source = img_src
    self.ffprobe_info = ffprobe_info
    self.primary_format = primary_format
    self.output_filename = output_filename
    self.output_directory = output_directory
    self.output_fileformats = output_fileformats
    
    self.crop = ParseCrop(crop, grav)
    self.rescales = (rescales if(rescales is not None) else ['100%'])
    
    (
      self.whiteBlack,
      self.wb_fuzzing,
      self.thresholds,
      self.edge_color,
      self.edgeRadius,
    ) = color_options.values()
    
    self.stepsize_deltas = {} # edge, white, black
    self.delay = 5 # controlling GIF framerate (see RGB.argstr_GIF)
    # default value for both magick-libraries is (equivalent to) 10
    
    self.frame_formats = [ primary_format, ]
    if (('APNG' in output_fileformats) or ('MP4' in output_fileformats)): self.frame_formats.append('PNG');
    
    self.did_preprocess_img = False
    self.image_preprocessed = None # list of ImageSourceT converted to .miff - color-swapped, scaled and/or cropped
    self.preprocessing_cmds = []
    self.expected_outputs = []
    
    self.frame_directories = {
        # miff_frames_scale50: (ImageSourceT, ImageSourceT) (source, dest)
    }
    
    assert(primary_format in ('MPC','MIFF'))
    assert(output_filename.endswith('_RGB'))
    assert(output_directory.exists() and output_directory.is_dir())
    return
  
  def GetRemapWB(self): return zip(self.whiteBlack, self.wb_fuzzing, self.thresholds, ('white','black'));


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
        if not all((N.isdigit() if not B else ((int(N) > 0)) and (int(N) <= 100)) for (B,N) in zip(percentage_check, (W,H))):
            raise Exception(f"percentage values out of range: ({W}x{H}); (valid range: [1-100])")
    
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
    cropstr = "+repage -gravity {} -crop '{}x{}{:+d}{:+d}' +repage".format(gravity,W,H,X,Y)
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


def ImagePreprocess(task:TaskT, intermediate_format=None):
    task.image_preprocessed = []
    task.preprocessing_cmds.clear()
    scales = ParseScales(task.rescales)
    
    current_img = task.image_source
    newest_sink = current_img
    
    magic_map = {
        current_img.magic: current_img,
    }
    
    # tuple contains: (sink, command, [sources]); where 'sink' and 'source' are magic-strings
    transform_queue : list[tuple] = []
    
    # mapping sink-magic to command-list
    expanded_commands = {}
    
    # maps source-magic to sink-magic
    transform_hooks : dict[str,str] = {}
    # alternative to 'transform_queue', when commands don't need resolving
    # commands may be manually added to the 'expanded_commands' dictionary (under their sink)
    # after resolving commands for a source in the transform queue, these hooks will be checked to find associated sink
    # then lookup the sink's pre-generated commands in expanded_commands, and add them to preprocessing_cmds
    
    if intermediate_format is None: intermediate_format = task.primary_format;
    def CreateSink(new_name:str, new_fmt:str=intermediate_format, force_multisource=False, sources:list[ImageSourceT]=None):
        if sources is None: sources = [current_img];
        is_multisource = (force_multisource or any([source_img.multisource for source_img in sources]))
        output_path = task.working_path / (new_name if is_multisource else f"{new_name}.{new_fmt.lower()}")
        sink = ImageSourceT(output_path, new_name)
        sink.multisource = is_multisource
        sink.frame_count = max([source_img.frame_count for source_img in sources])
        sink.indexlength = max([source_img.indexlength for source_img in sources])
        sink.image_format = new_fmt
        
        if sink.multisource:
            output_path.mkdir(exist_ok=True)
            sink.source_frames = [
                output_path / f"frame{str(C).zfill(sink.indexlength)}.{new_fmt.lower()}"
                for C in range(sink.frame_count)
            ]
        
        nonlocal newest_sink; newest_sink = sink
        magic_map[sink.magic] = sink
        return sink
    
    def QueueTransform(command:str, sources:list[ImageSourceT]=None, sink:ImageSourceT=None):
        if sources is None: sources = [current_img];
        if sink is None: sink = newest_sink;
        transform_queue.append((sink.magic,
            command.replace('  ','').strip(),
            [S.magic for S in sources]))
        return
    
    def ApplyModulation(key, source:ImageSourceT):
        assert(key in ('edge','white','black')), f"invalid stepsize-lookup: {key}";
        if (key not in task.stepsize_deltas): return source;
        modulations = RGB.EnumRotations(task.stepsize_deltas[key], task.image_source.frame_count)
        new_filename = f"{source.safe_filename}_modulation"
        output_path = task.working_path / new_filename
        output_path.mkdir(exist_ok=True)
        
        modsink = ImageSourceT(output_path, new_filename)
        modsink.multisource = True
        modsink.image_format = source.image_format
        modsink.frame_count = len(modulations)
        modsink.indexlength = len(modulations[0][0]) # index string
        modsink.source_frames = [output_path/f"frame{M[0]}.{source.image_format.lower()}" for M in modulations]
        modulate_commands = [
            f"convert {QS} -modulate 100,100,{M[1]} {QO}"
            for (QS,QO,M) in zip(
                source.QuoteSource(modsink.frame_count),
                modsink.QuoteSource(), modulations, strict=True
            )
        ]
        
        nonlocal newest_sink; newest_sink = modsink;
        magic_map[modsink.magic] = modsink
        expanded_commands[modsink.magic] = modulate_commands
        transform_hooks[source.magic] = modsink.magic
        return modsink
    
    
    baseimg = CreateSink("baseimg_primary_format", "MPC")
    QueueTransform(f"convert {current_img.magic} -matte {task.crop}")
    current_img = baseimg
    
    if task.whiteBlack is not None:
        for (new_color, fuzzpcent, thold, colorname) in task.GetRemapWB():
            if (new_color is None):  continue;
            if not thold: color_threshold=' ';
            # checking working_path here is a jank test for MAGICKLIBRARY because I don't want to import Globals
            elif (task.working_path.name.endswith('IM')): color_threshold = f"-{colorname}-threshold '{thold}%'"
            else: color_threshold = f"-operator All Threshold-{colorname.title()} '{thold}%'" # this is how '-threshold-black/white' is done in GM ('All' only affects RGB, not alpha)
            recolor = CreateSink(f"srcimg_recolor_{colorname}"); fuzz = f"-fuzz '{fuzzpcent}%'" if (fuzzpcent>0) else ' ';
            QueueTransform(f"convert {current_img.magic} {color_threshold} {fuzz} {RGB.RecolorStr(colorname, new_color)}")
            current_img = recolor # 'recolor_white.png' is used as base for 'recolor_black.png'
            # TODO: stepwhite always breaks recolor_black because of fuzz/thresholds
            ApplyModulation(colorname,recolor) # updates newest_sink, but not current_img
        
        if (current_img.magic != baseimg.magic):
            current_img = newest_sink # recolor_black_modulation
            composite = CreateSink("srcimg_WB_recolor", sources=[current_img, baseimg]) # TODO: misses white-modulation if both alt-stepsizes are enabled
            composite_cmd = f"composite {current_img.magic} {baseimg.magic} -compose Atop"
            QueueTransform(composite_cmd, sources=[current_img, baseimg])
            current_img = composite # keep as base for edge-highlight
        # the last composite only exists to discard the transparency that always gets filled by recolor_black
        # for some reason, replacing 'Black' will also fill all transparent regions - replacing white doesn't
        # (the same behavior occurs when hex codes are used instead of name; #000000 / #000000FF / #00000000)
    
    if task.edge_color is not None:
        edge_image = CreateSink("srcimg_edge", sources=[baseimg])
        recolor_cmd = RGB.EdgeHighlightCMD(task.edge_color, task.edgeRadius)
        QueueTransform(recolor_cmd.format(baseimg.magic), sources=[baseimg]) # edge-detect baseimg, NOT current
        edge_image = ApplyModulation('edge', edge_image)
        baseimg = current_img; current_img = edge_image
        # ^ preserving 'recolor_black.png' in baseimg for final composite
    
    if (current_img.magic != baseimg.magic): # final composite and updating task.image_preprocessed
        final_output = CreateSink("srcimg_preprocessed",sources=[current_img,baseimg])
        compositecmd = f"composite {current_img.magic} {baseimg.magic} -compose Atop"
        QueueTransform(compositecmd, sources=[current_img, baseimg])
        current_img = final_output
    
    for (scale_value, scale_suffix) in scales:
        scale_text = ('' if (scale_value == 100) else f"-scale '{scale_value}%'")
        scaled_img = CreateSink(f"srcimg{scale_suffix}", task.primary_format)
        QueueTransform(f"convert {current_img.magic} {scale_text}")
        task.image_preprocessed.append(scaled_img)
    
    for (sink_magic, command, source_magics) in transform_queue:
        command_list = []; print(f"resolving command: '{command}' -> {sink_magic}")
        sink = magic_map[sink_magic]
        
        resolved_sources = [*zip(*[
            magic_map[magic_str].QuoteSource((sink.frame_count if sink.multisource else 1))
            for magic_str in source_magics
        ])]
        
        for (output_path, input_path_tuple) in zip(sink.QuoteSource(), resolved_sources, strict=True):
            new_command = command # python is dumb - reassigning 'command' doesn't work and 'nonlocal' isn't allowed
            for (input_magic, input_path) in zip(source_magics, input_path_tuple, strict=True):
                new_command = new_command.replace(input_magic, input_path, 1)
            command_list.append(f"{new_command} {output_path}")
        
        expanded_commands[sink_magic] = command_list
        task.preprocessing_cmds.extend(command_list)
        if sink_magic in transform_hooks:
            task.preprocessing_cmds.extend(
                expanded_commands[transform_hooks[sink_magic]]
            )
    
    # creating ./miff_frames_scale50/, ./png_frames/... etc
    for frame_source in task.image_preprocessed:
        print(f"\nFRAME SOURCE: {frame_source.safe_filename}")
        current_source = frame_source
        for frameformat in task.frame_formats:
            print(f"CURRENT_SOURCE: {current_source.safe_filename} | FRAME_FORMAT: {frameformat}")
            framedir_name = frame_source.safe_filename.replace('srcimg', f'{frameformat.lower()}_frames')
            framedir_dest = CreateSink(framedir_name, frameformat, True, sources=[current_source])
            task.frame_directories[framedir_name] = (current_source, framedir_dest)
            if(frameformat == task.primary_format): current_source = framedir_dest;
            # frame_source is updated so that non-primary frame-formats (PNG) can just copy from the primary one
    
    task.did_preprocess_img = True
    return expanded_commands # still None unless edge/WB-recoloring was performed


def GenerateFrames(task:TaskT, enumRotations:list[tuple[str,str]]) -> tuple[list[str],list[str],list[str],list[str],list[str]]:
    assert((srcpath := task.image_source.srcpath).exists() and (srcpath.parent == task.working_path))
    assert(task.working_path.exists() and task.working_path.is_dir())
    assert(len(task.frame_formats) > 0)
    
    if (task.ffprobe_info is None):
        index_len = task.image_source.indexlength # number of digits to use in printf sequence
        framerate = 30
        audio_src = None
    else:
        index_len = task.ffprobe_info['index_length']
        framerate = task.ffprobe_info['framerate']
        audio_src = task.ffprobe_info["extracted_audio_path"]
    
    
    preprocess_commands = []
    if (not task.did_preprocess_img): # don't duplicate preprocessing
        expanded_commands = ImagePreprocess(task) # TODO: need to update global SRCIMG?
        preprocess_commands = task.preprocessing_cmds
    
    framegen_commands = []
    frame_conversions = [] # commands filling derivative directories (png_frames)
    ZL = task.image_source.frame_count
    for (dest_name, (frame_source, frame_output)) in task.frame_directories.items():
        # generating frames (performing modulation) in primary-format (MPC/MIFF)
        if ((dest_fmt := frame_output.image_format) == task.primary_format):
            (src_frames, dest_frames) = (frame_source.QuoteSource(ZL), frame_output.QuoteSource(ZL))
            framegen_commands.extend([
                f"convert {src_frame} -scene {index} -modulate 100,100,{rotation} {dest_frame}"
                for (src_frame, dest_frame, (index, rotation)) in zip(src_frames, dest_frames, enumRotations, strict=True)
            ])
            continue
        
        # derivative frame directory (png_frames); just converting miff_frames to PNG (avoiding duplicate modulation)
        from_glob = f"'{task.primary_format}:{frame_source.srcpath}/frame*.{task.primary_format.lower()}'"
        dest_glob = f"'{dest_fmt}:{frame_output.srcpath}/frame%0{index_len}d.{dest_fmt.lower()}'"
        frame_conversions.append(f"convert {from_glob} +adjoin {dest_glob}")
        
        # additional 'apng_frames' created with matte (alpha) disabled
        if ('APNG' in task.output_fileformats) and (dest_fmt == 'PNG'):
            framedir = frame_output.srcpath
            mirror = framedir.with_name(f"a{framedir.name}"); # apng_frames
            mirror.mkdir(exist_ok=True) # not created yet if input is video
            dest_glob = f"'{dest_fmt}:{mirror}/frame%0{index_len}d.{dest_fmt.lower()}'"
            frame_conversions.append(f"convert {from_glob} +matte +adjoin {dest_glob}")
    
    framegen_commands.extend(frame_conversions)
    
    
    render_commands = []
    webp_rendercmds = []
    ffmpeg_commands = []
    ffmpeg_begin = f"ffmpeg -hide_banner -nostdin -y -thread_queue_size 1024 -f image2 -framerate {framerate} -pattern_type sequence -i"
    webp_options = "-quality 100 -define webp:thread-level=1 -define webp:lossless=true -define webp:method=6 -define webp:use-sharp-yuv=true"
    # with multiple input-sources, ffmpeg will complain: 'Thread message queue blocking; consider raising the thread_queue_size option'
    # until you raise it to at least 1024 (default is 8); "-thread_queue_size 1024"
    
    for (outfmt, (scaleval, scalestr), final_destination) in task.expected_outputs:
        srcfmt = ("PNG" if (use_ffmpeg := (outfmt in ('APNG','MP4'))) else task.primary_format)
        framedir = task.working_path / f"{srcfmt.lower()}_frames{scalestr}"
        work_file = task.working_path / final_destination.name
        
        if use_ffmpeg:
            if (outfmt == 'APNG'): framedir = framedir.with_name(f"a{framedir.name}"); # apng_frames
            apng_opts = f"-ignore_loop false -plays 0 -default_fps {framerate}"  # '-plays 0' enables animation looping
            audio_arg = (f"-i '{audio_src}' -shortest -af apad" if (audio_src is not None) else '') # if video is shorter than audio, audio is truncated to video length
            argstring = (apng_opts if(outfmt == 'APNG') else audio_arg if(outfmt == 'MP4') else '')
            ffmpeg_commands.append(f"{ffmpeg_begin} '{framedir}/frame%0{index_len}d.{srcfmt.lower()}' {argstring} '{work_file}'")
            continue
        
        # webp output is ImageMagick-only; no animation in GraphicsMagick
        (magick_convert, opts) = (("convert-im6.q16", webp_options) if (isWEBP := (outfmt == "WEBP")) else 
                                  ("convert", RGB.argstr_GIF(task.delay) if (outfmt=="GIF") else ""))
        if (outfmt == "GIF"):
            if (opts[0] is None): opts = opts[1];
            else: render_commands.append(f"{magick_convert} {opts[0]} '{srcfmt}:{framedir}/frame*.{srcfmt.lower()}' {opts[1]} -adjoin '{outfmt}:{work_file}'"); continue;
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
