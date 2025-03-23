import pathlib


class TaskT():
  def __init__(self, 
        srcimg:pathlib.Path,
        workdir:pathlib.Path,
        checksum:str,
        crop:str|None,
        rescales:list[str]|None,
        frame_format:str,
        output_filename:str,
        output_directory:pathlib.Path,
        output_fileformats:list[str],
    ):
    self.image_source = srcimg
    self.image_md5sum = checksum
    self.working_path = workdir
    self.primary_format = frame_format
    self.output_filename = output_filename
    self.output_directory = output_directory
    self.output_fileformats = output_fileformats
    
    self.crop = crop
    self.rescales = (rescales if(rescales is not None) else ['100%'])
    
    self.frame_formats = [ frame_format, ]
    if (('APNG' in output_fileformats) or ('MP4' in output_fileformats)): self.frame_formats.append('PNG');
    
    self.image_preprocess = [] # scaled and/or cropped
    self.expected_outputs = []
    
    assert(frame_format in ('MPC', 'MIFF'))
    assert(output_filename.endswith('_RGB'))
    assert(output_directory.exists() and output_directory.is_dir())
    
    return


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
            
            renamelimit = 10; renamecount=1
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
    
    dests = sorted([expected[-1] for expected in task.expected_outputs] )
    print(f"expected outputs: {'\n  '.join(str(x.name) for x in dests)}")
    return task.expected_outputs


def CheckExpectedOutputs(task:TaskT) -> list[tuple[pathlib.Path,pathlib.Path]]:
    results = []
    for (_, _, final_dest) in task.expected_outputs:
        work_file = task.working_path / final_dest.name
        print(f"checking: {work_file}")
        if work_file.exists(): results.append((work_file, final_dest));
        else: print(f"[WARNING] expected output does not exist! ({work_file})");
    return results


def ImagePreprocess(task:TaskT):
    src_img = task.image_source
    workdir = task.working_path
    scales = ParseScales(task.rescales)
    task.image_preprocess.clear()
    
    for (scale_value, scale_suffix) in scales:
        crop_text = '' # TODO: implement cropping
        scale_text = ('' if (scale_value == 100) else f"-scale {scale_value}%")
        new_img = workdir/f"srcimg{scale_suffix}.{task.primary_format.lower()}"
        command = f"convert 'PNG:{src_img}{crop_text}' -strip {scale_text} '{task.primary_format.upper()}:{new_img}'"
        task.image_preprocess.append((new_img, command))
    
    return task.image_preprocess


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
    preprocessing = ImagePreprocess(task)
    
    preprocess_commands = []
    for (src_img, command) in preprocessing:
        if src_img.exists(): print(f"skipping preprocessing (already exists): '{src_img}'"); continue;
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
        if isWEBP: render_commands.append(cmd); 
        else: webp_rendercmds.append(cmd);
    
    return (preprocess_commands, framegen_commands, render_commands, webp_rendercmds, ffmpeg_commands)


