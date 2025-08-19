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
    


class TextOverlayT(ImageSourceT):
    def __init__(self, srcpath: pathlib.Path, safe_filename: str):
      super().__init__(srcpath, safe_filename)
      self.offset = None
      self.gravity = None
    
    def ComposeString(self, method="Over"):
      compose_string = f"-compose {method}"
      if (self.gravity is not None): compose_string += f" -gravity {self.gravity}";
      if (self.offset is not None): compose_string += f" -geometry {self.offset[1]}";
      # offset[1] is the formatted string; [0] is the integer-tuple
      return compose_string


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
        rendertext_sources:list[TextOverlayT],
    ):
    self.working_path = workdir
    self.image_source = img_src
    self.ffprobe_info = ffprobe_info
    self.primary_format = primary_format
    self.output_filename = output_filename
    self.output_directory = output_directory
    self.output_fileformats = output_fileformats
    self.rendertext_sources = rendertext_sources
    
    self.crop = BuildCropCommand(crop, grav)
    self.rescales = (rescales if(rescales is not None) else ['100%'])
    
    (
      self.whiteBlack,
      self.wb_fuzzing,
      self.thresholds,
      self.edge_color,
      self.edgeRadius,
    ) = color_options.values()
    
    self.stepsize_deltas = {} # edge, text, white, black
    self.delay = 5 # controlling GIF framerate (see RGB.argstr_GIF)
    # default value for both magick-libraries is (equivalent to) 10
    
    self.frame_formats = [ primary_format, ]
    if (('APNG' in output_fileformats) or ('MP4' in output_fileformats)): self.frame_formats.append('PNG');
    
    self.baseimgformat_override = "MPC" # override format of the first conversion to MPC for better performance
    if ((self.image_source.frame_count > 2000) and (self.primary_format != "MPC")): self.baseimgformat_override = primary_format;
    # except gigantic tasks must prioritize avoiding OOM instead - unless MPC is specified, cancel the override
    
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


def BuildCropCommand(crop:tuple[int|str,int|str,int,int]|None, gravity:str="Center") -> str:
    if (crop is None) or (crop == (0,0,0,0)): return '';
    (W,H,X,Y) = crop
    
    # when only one dimension is specified, set the other to a value that prevents it from being modified
    if (W == 0): W = ('100%' if isinstance(H, str) else 32767);
    if (H == 0): H = ('100%' if isinstance(W, str) else 32767);
    
    # trailing 'x' on width followed by an offset fails when height is missing (this is a bug in the GraphicsMagick parser)
    # because it interprets the first offset as the height, which is problematic with the default '+0' (and in general)
    # as a workaround, try to remove the default offset. otherwise remove the 'x'
    # if ('x+' in fstr): fstr.replace('+0+0','').replace('x+','+');
    # this workaround runs into a second bug: it fails to respect the 'gravity' parameter when no offset is specified
    
    return "+repage -gravity {} -crop '{}x{}{:+d}{:+d}' +repage".format(gravity, W,H,X,Y)
    # '+repage' output to remove virtual-canvas (crop doesn't actually resize the canvas)


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
    
    sink_count : dict[str,int] = {} # counts how many times an object is used as a sink (written to)
    parent_map : dict[str,str] = {} # associates one sink with another - expanded commands will also be added to parent
    
    if intermediate_format is None: intermediate_format = task.primary_format;
    def CreateSink(new_name:str, new_fmt:str=intermediate_format, force_multisource=False, sources:list[ImageSourceT]=None, parent:ImageSourceT=None):
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
        if (parent is not None): parent_map[sink.magic] = parent.magic;
        magic_map[sink.magic] = sink
        return sink
    
    def QueueTransform(command:str, sources:list[ImageSourceT]=None, sink:ImageSourceT=None):
        if sources is None: sources = [current_img];
        if sink is None: sink = newest_sink;
        sink_count[sink.magic] = 1 + sink_count.get(sink.magic, 0)
        transform_queue.append((sink.magic,
            command.replace('  ','').strip(),
            [S.magic for S in sources]))
        return
    
    def ApplyModulation(key, source:ImageSourceT):
        assert(key in ('edge','text','white','black')), f"invalid stepsize-lookup: {key}";
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
    
    
    baseimg = CreateSink("baseimg_primary_format", task.baseimgformat_override)
    QueueTransform(f"convert {current_img.magic} -matte {task.crop}")
    current_img = baseimg
    
    if task.whiteBlack is not None:
        for (new_color, fuzzpcent, thold, colorname) in task.GetRemapWB():
            if (new_color is None):  continue;
            if not thold: color_threshold=' ';
            # checking working_path here is a jank test for MAGICKLIBRARY because I don't want to import Globals
            elif (task.working_path.name.endswith('IM')): color_threshold = f"-{colorname}-threshold '{thold}%'"
            else: color_threshold = f"-operator All Threshold-{colorname.title()} '{thold}%'" # this is how '-threshold-black/white' is done in GM ('All' only affects RGB, not alpha)
            recolor = CreateSink(f"srcimg_recolor_{colorname}", sources=[baseimg]); fuzz = f"-fuzz '{fuzzpcent}%'" if (fuzzpcent>0) else ' ';
            QueueTransform(f"convert {baseimg.magic} {color_threshold} {fuzz} {RGB.RecolorStr(colorname, new_color)}", sources=[baseimg])
            
            if (colorname == 'black'):
                # black needs to discard transparent areas, because the black-recolor (fill/opaque) always fills them
                # for some reason, replacing 'Black' will also fill all transparent regions - replacing white doesn't
                # (the same behavior occurs when hex codes are used instead of name; #000000 / #000000FF / #00000000)
                opacity_mask = CreateSink('opacity_mask', sources=[baseimg], parent=recolor)
                if task.working_path.name.endswith('GM'): QueueTransform(f"convert {baseimg.magic} -operator Opacity Xor '100%'", sources=[baseimg], sink=opacity_mask);
                else: QueueTransform(f"convert -alpha Extract {baseimg.magic} -fuzz '99%' -transparent white", sources=[baseimg], sink=opacity_mask);
                QueueTransform(f"composite {recolor.magic} {opacity_mask.magic} -compose Out", sources=[recolor, opacity_mask], sink=recolor)
            
            recolor_diff = CreateSink(f'recolor_{colorname}_diff', sources=[baseimg, recolor], parent=recolor)
            recolor_mask = CreateSink(f'recolor_{colorname}_mask', sources=[recolor_diff], parent=recolor)
            QueueTransform(f"composite {baseimg.magic} {recolor.magic} -compose Difference", sources=[baseimg, recolor], sink=recolor_diff)
            if task.working_path.name.endswith('IM'): # for some reason IM struggles to replace black here without a threshold/fuzz of ~10%
                QueueTransform(f"convert {recolor_diff.magic} -black-threshold '10%' -transparent black", sources=[recolor_diff], sink=recolor_mask);
            else: QueueTransform(f"convert {recolor_diff.magic} {RGB.RecolorStr('black','transparent')}", sources=[recolor_diff], sink=recolor_mask);
            QueueTransform(f"composite {recolor.magic} {recolor_mask.magic} -compose In", sources=[recolor, recolor_mask], sink=recolor)
            
            recolor = ApplyModulation(colorname, recolor)
            composite = CreateSink("recolor_composite", sources=[current_img, recolor])
            composite_cmd = f"composite {recolor.magic} {current_img.magic} -compose Over"
            QueueTransform(composite_cmd, sources=[recolor, current_img])
            current_img = composite # keep as base for edge-highlight
    
    
    TEXT_LAYERED_ABOVE = True
    for renderedText in task.rendertext_sources:
        magic_map[renderedText.magic] = renderedText # no entry exists because it wasn't created as a sink
        expanded_commands[renderedText.magic]=list() # this also needs to be added manually
        compose_string = renderedText.ComposeString("Over")
        renderedText = ApplyModulation('text',renderedText)
        text_overlay = CreateSink("text_overlay", sources=[renderedText, current_img])
        
        if TEXT_LAYERED_ABOVE:
            QueueTransform(f"composite {renderedText.magic} {current_img.magic} {compose_string}", sources=[renderedText, current_img])
        else: # text is layered beneath the image instead of above (source-image must have transparent background)
            QueueTransform(f"composite {current_img.magic} {renderedText.magic} {compose_string}", sources=[renderedText, current_img])
            QueueTransform(f"composite {text_overlay.magic} {current_img.magic} {compose_string}", sources=[text_overlay, current_img])
        baseimg = text_overlay; current_img = baseimg;
    
    #TODO: steptext
    #TODO: still not avoiding a redundant composite when edge-detection is disabled
    
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
        # for unknown reasons, GraphicsMagick deletes original files after any command that is effectively no-op
        # '-modulate' seems to be one of the few options that forces an 'unoptimized clone'; preventing deletion
        if ((intermediate_format == 'MPC') and (scale_value == 100) and (task.working_path.name.endswith('GM'))):
            scale_text = "-modulate 100"; # ImageMagick does not have any issue; only with GraphicsMagick ^ (and only with MPC, no issues using MIFF)
        # '-scale' also prevents this (obviously), but the fullsize sink can't use it because of another bug: '-scale 100%' writes corrupt image data
        # another workaround is '-write'-ing to the real destination, using the source as input and output (difficult to implement here)
        QueueTransform(f"convert {current_img.magic} {scale_text}")
        task.image_preprocessed.append(scaled_img)
    
    for (sink_magic, command, source_magics) in transform_queue:
        print(f"resolving command: '{command}' -> {sink_magic}")
        command_list = expanded_commands.get(sink_magic, list())
        sink = magic_map[sink_magic]; new_command_list = []
        
        resolved_sources = [*zip(*[
            magic_map[magic_str].QuoteSource((sink.frame_count if sink.multisource else 1))
            for magic_str in source_magics
        ])]
        
        for (output_path, input_path_tuple) in zip(sink.QuoteSource(), resolved_sources, strict=True):
            new_command = command # python is dumb - reassigning 'command' doesn't work and 'nonlocal' isn't allowed
            for (input_magic, input_path) in zip(source_magics, input_path_tuple, strict=True):
                new_command = new_command.replace(input_magic, input_path, 1)
            new_command_list.append(f"{new_command} {output_path}")
        
        sink_count[sink.magic] = current_count = sink_count[sink.magic] - 1
        if (current_count == 0):
            if sink_magic in transform_hooks:
                new_command_list.extend(expanded_commands[transform_hooks[sink_magic]])
        
        if sink_magic in parent_map:
            expanded_commands[parent_map[sink_magic]].extend(new_command_list)
        
        command_list.extend(new_command_list)
        expanded_commands[sink_magic] = command_list
        task.preprocessing_cmds.extend(new_command_list)
    
    # creating ./miff_frames_scale50/, ./png_frames/... etc
    for frame_source in task.image_preprocessed:
        print(f"\nFRAME SOURCE: {frame_source.safe_filename}")
        current_source = frame_source
        for frameformat in task.frame_formats:
            print(f"CURRENT_SOURCE: {current_source.safe_filename} | FRAME_FORMAT: {frameformat}",end='')
            framedir_name = frame_source.safe_filename.replace('srcimg', f'{frameformat.lower()}_frames')
            framedir_dest = CreateSink(framedir_name, frameformat, True, sources=[current_source])
            print(f" | SINK_NAME: {framedir_name}")
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

