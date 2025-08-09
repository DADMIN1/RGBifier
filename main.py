import pathlib
import tempfile
import subprocess
import os
import json

from collections import Counter
from datetime import datetime

from CLI import (FilterText, PrintDict, ParseCmdline, ResolveOutputPath)
from CLI import CalcDeltas as CalcStepDeltas
import Globals
import Config
import Task
import RGB
import RenderText


def SetupENV(alt_defaults:dict) -> dict:
    """ Sets config/log path, and some resource limits (mostly higher than builtin defaults). \n
    Checks environment and imports any defined ImageMagick/GraphicsMagick variables. \n
    Performs validation for 'MAGICK_DEBUG' if defined externally, otherwise defaults to 'All'. \n 
    Final values are applied and exported to both ImageMagick/GraphicsMagick-style variables """
    def VarNames(S:str): # lambda generating ImageMagick/GraphicsMagick-style environment-variables
        if (S.upper() == "THREADS"): return ("MAGICK_THREAD_LIMIT", "OMP_NUM_THREADS");
        if (S.upper() == "FILES"): return ("MAGICK_FILE_LIMIT", "MAGICK_LIMIT_FILES"); # non-plural in IM-style
        return (f"MAGICK_{S.upper()}_LIMIT", f"MAGICK_LIMIT_{S.upper()}")
        # "memory" -> [MAGICK_MEMORY_LIMIT, MAGICK_LIMIT_MEMORY]
    
    # values specified here will be exported to env if not already defined, unless the value is 'None'
    env_defaults = {
        # resources
          "FILES": 8192, # IM/GM will automatically increase soft-ulimit if necessary (ulimit -S -n)
        "THREADS": (os.cpu_count() // 2), # 'cpu_count()' reports 2 cpus per physical core (hyperthreading)
         "MEMORY": "64GB", # TODO: should match tmpfs size
            "MAP": "64GB", # normally 2x Memory-limit, for some reason
           "DISK": "64GB", # setting this equal to 'Memory' is necessary for tmpfs: imagemagick seems to count loading '.mpc' files as disk usage
          "WIDTH": "32KP", # width/height are hard limits (throws exception if exceeded)
         "HEIGHT": "32KP",
         "PIXELS": None, # GM-only?
           "AREA": None, # IM-only? width*height; suffix is 'KP/MP/GP'. soft limit (unlike height/width); caches to disk if exceeded.
           "READ": None,
          "WRITE": None,
    }
    
    print("reading environment...")
    # if both IM/GM-style variables are set for an entry, the last one (GM-style) will take precedence
    final_env = {
        EK: EV
        for (K,V) in env_defaults.items()
        for EV in [V, *[os.getenv(N) for N in VarNames(K)]]
        for EK in VarNames(K)
        if (EV is not None)
    }
    
    # MAGICK_DBG_SETTING: "None", "All", or comma-seperated domain list
    MAGICK_DBG_SETTING = os.getenv("MAGICK_DEBUG", alt_defaults.get("MAGICK_DEBUG", "None")).replace(" ", "")
    MAGICK_DBG_DOMAINS = ([
        'annotate','blob','cache','coder','configure',
        'deprecate','error','exception','fatalerror',
        'information','locale','option','render','resource',
        'temporaryfile','transform','user','warning','x11',
      ] if (Globals.MAGICKLIBRARY == "GM") else [
        'accelerate','annotate','blob','cache','coder',
        'deprecate','configure','command','exception',
        'locale','module','pixel','policy','resource',
        'draw','trace','transform','user','wand','x11',
    ])
    
    # GraphicsMagick simply ignores any invalid domains, without any warnings/errors
    print(f"parsing MAGICK_DEBUG[env]: '{MAGICK_DBG_SETTING}'")
    warnings = []; shouldPrintDomains = False; dbg_setting_isvalid = (len(MAGICK_DBG_SETTING) >= 3) # shortest valid strings are 'all'/'X11'
    if (len(MAGICK_DBG_SETTING) == 0): warnings.append("MAGICK_DEBUG[env] set to empty string!!");
    elif not dbg_setting_isvalid: warnings.append(f"[WARNING] MAGICK_DEBUG[env] is invalid: '{MAGICK_DBG_SETTING}'"); shouldPrintDomains=True;
    elif ((stripped := MAGICK_DBG_SETTING.replace(',','').lower()) in ['all','none']): MAGICK_DBG_SETTING = stripped;
    else: # must be comma-seperated list of debug-domains
        checked_domains = {
            W.lower(): (W.lower() in ['all', 'none', *MAGICK_DBG_DOMAINS])
            for W in MAGICK_DBG_SETTING.split(',') if (len(W) > 0)
        }
        # GraphicsMagick seems to ignore 'none' when any other flags are present, and 'all' takes precedence. Order doesn't seem to matter.
        exclusive_domains = [EXD for EXD in ['all','none'] if (EXD in checked_domains.keys())]
        invalid_domains = [K for (K,V) in checked_domains.items() if (not V)]
        normal_domains = [K for (K,V) in checked_domains.items() if (V and (K not in exclusive_domains))]
        assert((len(exclusive_domains) + len(invalid_domains) + len(normal_domains)) > 0), "domains should not be empty here";
        
        # normally, the exclusive-domains would be omitted; but the first one should be kept if there are no other valid domains
        if (len(normal_domains) == 0): normal_domains = exclusive_domains[:1];
        MAGICK_DBG_SETTING = ','.join(normal_domains)
        
        warnings.extend([f"[WARNING] MAGICK_DEBUG[env]: unrecognized domain: '{K}'" for K in invalid_domains])
        warnings.extend([f"[WARNING] MAGICK_DEBUG[env]: exclusive domain '{EXD}' should not be specified with other domains!" for EXD in exclusive_domains])
        shouldPrintDomains = (len(invalid_domains) > 0)
        dbg_setting_isvalid = (
            ((len(normal_domains) > 0) or (len(exclusive_domains) == 1)) and
            ((len(exclusive_domains) < len(normal_domains)) or (len(exclusive_domains) == 1))
        ) # WTF am I doing (works perfectly LMAO)
    
    if (len(warnings) > 0):
        for warning in warnings: print(f" {warning}");
        if ((not dbg_setting_isvalid) and (len(MAGICK_DBG_SETTING) <= 3)): MAGICK_DBG_SETTING="none";
        if shouldPrintDomains:
            print("[WARNING] invalid domain in MAGICK_DEBUG[env]!\nAvailable (unused) domains are: ")
            print('\n'.join(f" {D.title()}" for D in MAGICK_DBG_DOMAINS if D not in MAGICK_DBG_SETTING),end="\n\n")
    
    print(f"using MAGICK_DEBUG:'{MAGICK_DBG_SETTING}'")
    final_env["MAGICK_DEBUG"] = (MAGICK_DBG_SETTING)
    
    config_dir = pathlib.Path(os.getenv("MAGICK_CONFIGURE_PATH", (Globals.PROGRAM_DIR / "magick_configs/").absolute()))
    if (config_dir.exists() and config_dir.is_dir()): final_env["MAGICK_CONFIGURE_PATH"] = str(config_dir);
    else: print(f"[WARNING] bad path for 'MAGICK_CONFIGURE_PATH': {config_dir}");
    
    # "MAGICK_TMPDIR" might be GM-only?
    magick_tmp = pathlib.Path(os.getenv("MAGICK_TMPDIR", (Globals.WORKING_DIR.parent / f"TEMP_{Globals.MAGICKLIBRARY}/").absolute()))
    if (magick_tmp.is_dir()): final_env["MAGICK_TMPDIR"] = str(magick_tmp);
    else: print(f"[WARNING] invalid env 'MAGICK_TMPDIR': {magick_tmp}");
    
    # adds info about file-access to '-monitor' output (including temporary files); "TRUE"/"FALSE"
    final_env["MAGICK_ACCESS_MONITOR"] = str(os.getenv("MAGICK_ACCESS_MONITOR", alt_defaults.get("MAGICK_ACCESS_MONITOR", False))).upper()
    
    print("updating magick environment variables...\n")
    PrintDict(env_defaults, name="defaults")
    PrintDict(final_env, name="environment")
    for (K,V) in final_env.items():
        os.putenv(K,str(V))  # doesn't update 'os.environ'
        os.environ[K] = str(V) # modifying this automatically calls 'putenv', supposedly
    
    return final_env



def CreateTempdir(checksum:str, autodelete=True, use_tmpfs=False) -> tuple[pathlib.Path|None,bool]:
    """ 
    :param checksum: hash of input file; used as prefix for temporary subdirectory
    :param autodelete: the new temporary-directory will be deleted when program exits (has no effect if pre-existing temporary is reused)
    :param use_tmpfs: toplevel is located on tmpfs instead of under program-directory (attempts to mount tmpfs if mountpoint doesn't exist)
    :return: new temp directory and flag indicating that a pre-existing directory was found. (path is 'None' if tmpfs-mount failed)
    """
    tempdir_toplevel = Globals.PROGRAM_DIR / f"{Globals.TOPLEVEL_NAME}" # parent of all per-process tempdirs
    if use_tmpfs: tempdir_toplevel = pathlib.Path(f"/tmp/{Globals.TOPLEVEL_NAME}");
    if (isNewlyCreated := (not tempdir_toplevel.exists())):
        tempdir_toplevel.mkdir(); print(f"created toplevel directory: '{tempdir_toplevel}'")
    
    # attempt to mount tmpfs
    if (use_tmpfs and isNewlyCreated):
        print("mounting tmpfs...")
        # mounting tmpfs only seems to work properly when the mountpoint has been created manually?? ('mkdir' above apparently not good enough)
        #retval = os.system(f"mount --types tmpfs -o user,uid=1000,gid=1000,size=0,X-mount.mkdir tmpfs /tmp/{Globals.TOPLEVEL_NAME}")
        retval = os.system(f"mount /tmp/{Globals.TOPLEVEL_NAME}") # this command is more reliable, but requires an entry in '/etc/fstab'
        if not (retval == 0):
            print("Failed to mount tmpfs! Add an entry to '/etc/fstab' or mount it manually.")
            tempdir_toplevel.rmdir() # removing to ensure 'isNewlyCreated' will be 'True' again on next run
            return (None, False)
        print("mounted tmpfs!")
        # TODO: should verify that new or pre-existing tempdir_toplevel is actually tmpfs
    
    tmpdir_prefix=f"{checksum}_"
    tmpdir_suffix=f"_{Globals.MAGICKLIBRARY}"
    
    matching_dirs = [*tempdir_toplevel.glob(f"{tmpdir_prefix}*{tmpdir_suffix}/")]
    assert(len(matching_dirs) <= 1), "[ERROR]: multiple pre-existing subdirectory matches!!! (this is a bug)"
    
    # see 'temporary-path' in 'policy.xml' and "${MAGICK_TMPDIR}"
    for MK in ("IM", "GM"):
        magick_tmpdir = tempdir_toplevel / f"TEMP_{MK}"
        if not magick_tmpdir.exists(): magick_tmpdir.mkdir(); 
    
    if (isReusingSubdir := (len(matching_dirs) > 0)):
        if autodelete: print("[WARNING] 'autodelete' parameter will be ignored (directory already exists)");
        tempdir = matching_dirs[0] # per-process tempdir - optionally autodeleted when the program exits
        print(f"reusing work directory: {tempdir}")
        assert(tempdir.is_dir()), "location on matching path was not actually a directory!?";
        iter_counts = Counter([F.is_file() for F in tempdir.iterdir()])
        (filecount, dircount) = (iter_counts.get(B,0) for B in (True,False))
        tmpdir_mtime = datetime.fromtimestamp(tempdir.stat().st_mtime)
        
        # for debug/testing; ensuring mtime has nonzero 'day'
        # mtime_delta_tomorrow = (datetime.today().replace(day=(datetime.today().day+1)) - tmpdir_mtime)
        
        mtime_delta = (datetime.now() - tmpdir_mtime)
        (days, sec) = (mtime_delta.days, mtime_delta.seconds)
        (hrs, mins) = ( (sec // 3600), ((sec % 3600) // 60) )
        sec = (sec % 60)
        # ignore any 'unused' warnings related to these variables; 
        # they're referenced by 'eval' in 'MaybePlural()' below
        
        def MaybePlural(S:str,localz=locals()) -> str:
            if ((N := eval(S, localz)) == 0): return "";
            return f"{N} {S if (N>1) else S.removesuffix('s')}"
        
        # 'num_time_segments': limits the granularity of the reported mtime-delta to 'N' nonzero segments, ordered largest-first
        # for example, with 'N=2', the mtime-delta will report 'days'/'hrs' if both are nonzero, otherwise 'hrs'/'min', 'min'/'sec', or just 'sec'
        num_time_segments = 2; assert((num_time_segments > 0) and (num_time_segments <= 4));
        relative_time_str = " ".join([*filter(lambda S:(len(S)>0), 
            [MaybePlural(varname) for varname in ['days','hrs','mins','sec']]
        )][:num_time_segments])
        
        if (len(relative_time_str) == 0): 
            print("[WARNING]: pre-existing work-directory's relative-mtime is apparently zero. (this is probably a bug)")
            relative_time_str = '(now)'
        else: relative_time_str = f"{relative_time_str} ago";
        
        mtime_str = f"Last-Modified: {tmpdir_mtime.date().isoformat()} ({relative_time_str})"
        print(f"{tempdir.name}: [ {filecount} files | {dircount} folders ][ {mtime_str} ]")
        Globals.TEMPDIR_REF = tempdir
        return (tempdir, isReusingSubdir)
    
    # per-process tempdir - optionally autodeleted when the program exits
    tempdir = Globals.TEMPDIR_REF = tempfile.TemporaryDirectory(
        prefix=tmpdir_prefix, suffix=tmpdir_suffix, dir=tempdir_toplevel,
        delete=autodelete, ignore_cleanup_errors=False
    )
    print(f"created temp directory: '{tempdir.name}' [{'AUTO-DELETE' if autodelete else 'PRESERVE'}]")
    # must construct and return a 'pathlib.Path' because the behavior of '.name' is incompatible between the two classes
    # 'tempfile.TemporaryDirectory' returns the whole path, whereas 'pathlib.Path' would only return the last segment.
    # and the other branch (reusing work-directory) cannot return a Tempdir.
    return (pathlib.Path(tempdir.name), isReusingSubdir)



# GraphicsMagick does not provide any mechanism for specifying a relative-path for logfile, except for subdirectories under CWD.
# variable-expansion / substitution does not appear to be possible. Changing the path at runtime does not seem (reasonably) possible.
# If the path contains a directory, that directory must already exist, otherwise the logfile will simply not be written (silent failure; no warnings, of course)
# also, the mechanisms for writing numbered logfiles are only triggered by the event-limit (see log.mgk);
# otherwise, GraphicsMagick just overwrites the same logfile on every single run.
def RotateMagickLogs(toplevel:pathlib.Path, keep_limit:int, verbose=False) -> pathlib.Path:
    """ Create logging directory and rename existing logs.\n
    Logs prefixed with 'magickrgb' will be rotated. \n Logs' filenames should end with digits. \n
    Assumes that GraphicsMagick's logging-config (log.mgk) has 'filename' is set to: \n "/tmp/RGB_TOPLEVEL/magicklogs/magickrgb_%d.log" \n
    :param toplevel: see 'Globals.TOPLEVEL_NAME'
    :param keep_limit: rotations until deletion
    :param verbose: prints detailed information
    :return: path to log-directory """
    assert(toplevel.name == Globals.TOPLEVEL_NAME), "expected log-directory to be under toplevel"
    #assert(toplevel.is_relative_to("/tmp/")), "reminder to change paths in 'log.mgk' and 'log.xml'";
    # the configs' filepaths shouldn't matter as long as the 'output' option is not set to 'file'
    # TODO: come up with some workaround to switch paths in the configs between tmpfs/cwd. maintain a symlink under cwd?
    
    new_logdir = toplevel / "magicklogs"
    if new_logdir.exists(): assert(new_logdir.is_dir()), "existing log-directory was not actually a directory!?"
    else: new_logdir.mkdir(); print(f"created log-directory: '{new_logdir}'");
    
    stale_logs:list[pathlib.Path] = [F for F in new_logdir.glob("magickrgb_*.old.log") if (F.is_file())]
    fresh_logs:list[pathlib.Path] = [F for F in new_logdir.glob("magickrgb_*.log") if (F.is_file() and (F not in stale_logs))]
    moved_logs:list[pathlib.Path] = []
    logDeleted:list[pathlib.Path] = []
    
    def PrintLognames(name, loglist:list[pathlib.Path]):
        if((length := len(loglist)) > 0): print(f"{name} ({str(length).zfill(2)}): [" + ", ".join([L.name for L in loglist]) + "]");
    
    if(len(fresh_logs) == 0): return new_logdir;
    print(f"\nrotating logs under: '{new_logdir}'...")
    PrintLognames("fresh", fresh_logs)
    PrintLognames("stale", stale_logs)
    
    for log in [*stale_logs, *fresh_logs]:
        if (keep_limit <= 0): logDeleted.append(log); log.unlink(); continue;
        if (not (hitlimit := False) and (is_old := ('.old' in log.suffixes)) and (log in logDeleted)): continue;
        middle_name = (current_name := log.name).removesuffix(''.join(log.suffixes)).removeprefix("magickrgb_");
        if ((n_len := len(log_num := ''.join(C for C in middle_name[-3:] if C.isdigit()))) == 0): log_num = '1';
        middle_name = f"_{(middle_name[:-n_len] if (n_len > 0) else middle_name.strip('_'))}".removesuffix('_');
        if not log_num.isdigit(): print(f"[ERROR] failed parsing log-number! ({log_num}): '{log}'"); continue;
        while ((new_path := new_logdir / f"magickrgb{middle_name}_{str(log_num).zfill(3)}.old.log").exists()):
            if (hitlimit := ((log_num := int(log_num) + 1) > keep_limit)): logDeleted.append(new_path); break;
        if (hitlimit and is_old): log.unlink(); continue;
        print(f" rotating:  {current_name} -> {new_path.name}")
        moved_logs.append(log); log.rename(new_path.absolute())
    
    logCreated = [F for F in new_logdir.glob("magickrgb_*.old.log") if (F.is_file() and (F not in stale_logs))]
    if verbose:
        PrintLognames("created", logCreated)
        PrintLognames("deleted", logDeleted)
        PrintLognames("renamed", moved_logs)
    print(f"{len(stale_logs)+len(fresh_logs)} logs rotated [{len(logCreated)} created][{len(logDeleted)} deleted][{len(moved_logs)} renamed]\n")
    return new_logdir


# noinspection PyUnresolvedReferences
# ^ every lookup on video_stream/audio_stream (video_stream['nb_frames'])
# triggers this BS warning: "Cannot find reference '[' in 'None'"
def MakeImageSources(workdir:pathlib.Path, input_file:pathlib.Path, max_frames:int|None=None) -> (Task.ImageSourceT, pathlib.Path, dict|None):
    """
    :param workdir: temp subdirectory for image-processing
    :param input_file: image being RGBified; copied to workdir
    :param max_frames: limit number of frames extracted from video source
    :return: ImageSource, baseimage-path, stream_info (for video sources)
    """
    assert(workdir.exists() and workdir.is_dir())
    assert(input_file.exists() and input_file.is_file() and (input_file.parent != workdir))
    
    # 'safe' filename makes it possible to parse output of 'identify'/'file' (otherwise splitting won't work if filename contained spaces)
    safe_filename = FilterText(input_file.name.removesuffix(''.join(input_file.suffixes)))
    print(f"\ninput-path: '{input_file}'")
    print(f"safe-filename: '{safe_filename}'\n")
    
    # TODO: actually verify the filetype/encoding of baseimg
    if (len(input_file.suffixes) == 0): print("[WARNING] no suffix on input-file - assuming PNG");
    og_suffix = (input_file.suffixes[-1].removeprefix('.') if (len(input_file.suffixes) > 0) else 'PNG').lower()
    animatedFormats = ('mp4','gif','mkv','mov','avi') # TODO: figure out how to test gif/webp for animation
    stream_info = None
    
    # baseimg: copy of unmodified original
    # srcimg: transcoded / preprocessed image optimized for target pipelines
    baseimg_path = workdir / f"baseimg_{safe_filename}.{og_suffix}"
    src_path = workdir / f"srcimg_{safe_filename}" # no suffix; could be subdirectory
    source = Task.ImageSourceT(src_path, safe_filename)
    
    if baseimg_path.exists(): print(f"skipping baseimg copy (already exists)")
    else:
        print(f"copying baseimg: '{baseimg_path}'")
        os.system(f"cp --verbose '{input_file}' '{baseimg_path}'")
    
    print("preprocessing baseimg...")
    if (og_suffix in animatedFormats):
        source.multisource = True
        
        print(f"\n{'_'*120}\n")
        print("ffprobing for audio/video streams...")
        ffprobe_path = workdir / "ffprobe_info.json"
        ffprobe_comm = f"ffprobe -hide_banner -loglevel warning -show_streams '{baseimg_path}' -output_format json"
        ffprobe_info = json.loads(subprocess.check_output(ffprobe_comm, shell=True, encoding="utf-8"))
        print(f"{'_'*120}\n")
        
        with ffprobe_path.open(mode='w', encoding='utf-8') as ffprobe_file:
            # noinspection PyTypeChecker
            json.dump(ffprobe_info, ffprobe_file, indent=2)
            # opening files always triggers a BS warning:
            # 'Expected type 'SupportsWrite[str]', got 'TextIO' instead'
        
        stream_info = { stream["codec_type"]:stream for stream in ffprobe_info["streams"] }
        if ((video_stream := stream_info.get('video', None)) is None):
            print("[ERROR] no video stream found!!")
            print(json.dumps(stream_info, indent=2))
            print("exiting...\n"); exit(4)
        
        framecount = (int(video_stream['nb_frames']))
        index_length = 1+int(RGB.log10(framecount-1)) # length of digit-strings in numbered filenames
        # this calculation: ^ assumes incremental numbering starting at ZERO! (indexing from 1 would not subtract)
        
        dimensions = [video_stream[D] for D in ('width', 'height')] # integers
        framerates = [video_stream[R] for R in ("r_frame_rate", "avg_frame_rate")] # "60/1"
        if (framerates[0] != framerates[1]): print("[WARNING] r/avg framerates mismatch!");
        (N,D) = [int(I) for I in framerates[0].split('/',maxsplit=1)]; framerate = int(N/D)
        # note that "duration" might be slightly different between the video/audio streams,
        # due to differences in the ratios used as the 'time_base' between the two streams;
        # "time_base" for a video might be ~'1/15000', audio is likely '1/44100' (44100Hz).
        # formula: duration = "time_base" x "duration_ts"
        duration = (float(video_stream["duration"]))
        WxH = 'x'.join([str(D) for D in dimensions])
        
        task_info = stream_info["task_info"] = {
            "acodec": None,
            "vcodec": video_stream['codec_name'],
            "extracted_audio_path": None,
            "index_length": index_length,
            "framecount": framecount,
            "frames_max": max_frames,
            "dimensions": dimensions,
            "framerate": framerate,
            "duration": duration,
        }
        
        # sometimes it doesn't create an entry for 'color_space' and lookups fail
        for dkey in ('color_space','display_aspect_ratio','bits_per_raw_sample'):
            if (dkey not in video_stream.keys()): video_stream[dkey] = 'unknown';
        
        print(f"[VIDEO INFO] {safe_filename}.{og_suffix} [{video_stream['codec_name']}]")
        (aspect_ratio, bpp) = (video_stream['display_aspect_ratio'], str(video_stream['bits_per_raw_sample']))
        print(info_string := "{} ({}) @{}fps - {:.3f}s".format(WxH, aspect_ratio, framerate, float(duration)))
        print("{}/{} [{}]".format(*[video_stream[f"codec_{K}"] for K in ('name', 'tag_string', 'long_name')]))
        print(' '.join([f"depth:{bpp}-bit", *[f"{K}:{video_stream[K]}" for K in ('pix_fmt', 'color_space')]]))
        if ((max_frames is not None) and ((max_frames >= framecount) or (max_frames < 0))): max_frames = None;
        print(f"frame-count: {framecount} {f'(limited to {max_frames})' if (max_frames is not None) else ''}")
        
        if ((audio_stream := stream_info.get('audio', None)) is not None):
            print(f"\n[AUDIO INFO] {safe_filename}.{og_suffix} [{(acodec_suffix := audio_stream['codec_name']).upper()}]")
            print("acodec: {}/{} [{}]".format(*[audio_stream[f"codec_{K}"] for K in ('name', 'tag_string', 'long_name')]))
            print(f"{audio_stream['channels']}-channel {audio_stream['channel_layout']} @{audio_stream['sample_rate']}Hz")
            extracted_audio_path = workdir / f"baseimg_extracted_audio.{acodec_suffix}" # ffmpeg mandates that a matching file-extension is provided
            audio_extraction_cmd = f"ffmpeg -hide_banner -loglevel warning -nostdin -n -vn -i '{baseimg_path}' -codec:a copy '{extracted_audio_path}'"
            if not extracted_audio_path.exists(): subprocess.check_output(audio_extraction_cmd, shell=True, encoding="utf-8");
            task_info["acodec"] = acodec_suffix; task_info["extracted_audio_path"] = extracted_audio_path;
        print(f"{'_'*120}\n")
        # TODO: AAC audio should use '.m4a' extension? # https://trac.ffmpeg.org/wiki/Encode/AAC
        # using '.aac' causes ffmpeg to complain when recombining the audio/video - "[aac] Estimating duration from bitrate, this may be inaccurate"
        
        prefix = 'frame'; suffix = '.png'
        if src_path.exists(): print(f"skipping srcimg frame-extraction (already exists)");
        else:
            print("extracting frames from baseimg...")
            os.system(f"mkdir --verbose '{src_path}'")
            
            frame_path = src_path / f"{prefix}%0{index_length}d{suffix}"
            # "-start_number 0": ffmpeg numbers the extracted frames from index '1' by default, not '0'
            status = os.system(f"ffmpeg -hide_banner -loglevel warning -nostdin -n -an -i '{baseimg_path}' -f image2 -start_number 0 '{frame_path}'")
            if (status != 0): print(f"ffmpeg frame-extraction exited with nonzero status: {status}; exiting..."); exit(4);
        
        framelist = sorted([*src_path.glob(f"{prefix}{'[0-9]'*index_length}{suffix}")]) # 'frame[0-9][0-9][0-9].png'
        assert(len(framelist) == framecount), "unexpected number of extracted frames!";
        source.frame_count = FC = (framecount if (max_frames is None) else max_frames);
        source.source_frames = framelist[:FC]
        source.indexlength = index_length
        task_info['frames_max'] = FC
    else:
        if (og_suffix.lower() != 'png'): # non-PNG images must be converted to PNG
            basepng_path = baseimg_path.with_suffix(".png")
            ft_prefix = ('JPEG' if (og_suffix.lower() == 'jpg') else og_suffix.upper())
            os.system(f"gm convert '{ft_prefix}:{baseimg_path}' 'PNG:{basepng_path}'")
            baseimg_path = basepng_path
        
        os.system(f"cp --verbose '{baseimg_path}' '{src_path}'")
        print(f"preprocessed source created: '{src_path}'")
    
    print("") # newline
    return (source, baseimg_path, stream_info)


def SubCommand(cmdline:list[str]|str, logname:str|None = "main", isCmdSequence:bool = False):
    """ Run a command in subprocess and log output. Logs are appended to or created automatically.
    :param cmdline: string or args-list (including command itself)
    :param logname: identifier used in filename. Skip logging if None.
    :param isCmdSequence: 'cmdline' is a list of commands to execute (rather than a single cmdline split by word)
    """
    if (len(cmdline) == 0): print(f"[WARNING] skipping subcommand: empty cmdline! (logname: {logname})"); return;
    
    if (log_dir := Globals.LOGGING_DIR) is None: print(f"[ERROR] no valid 'log_dir'"); return; 
    if not log_dir.exists(): print(f"creating log_dir: '{log_dir}'"); log_dir.mkdir();
    
    def RenameCommandIM(cmd):
        (cmd_name, command_str) = cmd.split(' ', maxsplit=1)
        if cmd_name not in ('convert','composite','mogrify'): return cmd;
        return f'{cmd_name}-im6.q16 {command_str}'
    
    cmd_seq = (
        (cmdline if isCmdSequence else [cmdline])
        if (Globals.MAGICKLIBRARY == "GM") else [
        RenameCommandIM(command) for command in (
        cmdline if isCmdSequence else [cmdline])]
    )
    
    print('_'*120); print(); L = "\n  "; cmd_rep = cmd_seq;
    if (len(cmd_seq) == 1): cmd_rep = cmd_seq[0]; isCmdSequence = False;
    subcmd_str = ('commandseq: [{1}{0}\n]' if isCmdSequence else 'subcommand: "{0}"')
    print(subcmd_str.format((f",{L}".join(cmd_rep) if isCmdSequence else cmd_rep),L))
    
    # TODO: Skip logging if None
    skiplog = (logname is None)
    log_filepath = log_dir / f"magickrgb_{logname}.log"
    if logname is None: log_filepath = log_dir/"magickrgb_main.log"; # still logs command, but not output
    else:  print(f"logging to: '{log_filepath}'");
    print('_'*120); print()
    
    # shell=True if cmdline is a single string
    # cwd=... <- could be useful
    # text=True: output is captured as string instead of bytes. implied by specifying 'encoding'
    # check=True: raises 'CalledProcessError' on nonzero return-status
    #completed = subprocess.run(cmdline, check=True, capture_output=True, encoding="utf-8")
    #completed = subprocess.run(cmdline, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
    #completed = subprocess.run(cmdline, check=True, stdout=None, stderr=subprocess.PIPE, encoding="utf-8")
    # 'capturing' either stream means it won't get printed; set them to 'None' if you want them printed.
    
    # mode='a' - append to existing file, or create new
    with (log_filepath.open(mode='a', encoding="utf-8") as logfile):
        cmdline_str = (cmd_seq[0] if isinstance(cmdline,str) 
                       else ("\n" if isCmdSequence else " ").join(cmd_seq))
        logfile.write(cmdline_str); logfile.write("\n\n"); logfile.flush()
        stderr_dest = (logfile if not skiplog else None)
        use_shell = (isinstance(cmd_seq[0],str))
        for cmd in cmd_seq: # prints stdout, logs stderr
            completed = subprocess.run(cmd, check=True, stdout=None, stderr=stderr_dest, encoding="utf-8", shell=use_shell)
            if (completed.returncode != 0): print(f"[ERROR] nonzero exit-status: {completed.returncode}\n"); break;
        logfile.write('_'*120); logfile.write("\n\n")
    
    print("\n")
    return


def SavePreprocessingCommands(workdir:pathlib.Path, expanded_commands:dict):
    better_names = {
        "baseimg_primary_format": expanded_commands.get("$$baseimg_primary_format$$", None),
        "recolor_white": expanded_commands.get("$$srcimg_recolor_white$$", None),
        "recolor_black": expanded_commands.get("$$srcimg_recolor_black$$", None),
        "recolor_composite": expanded_commands.get("$$recolor_composite$$",None),
        "edge": expanded_commands.get("$$srcimg_edge$$", None),
        "preprocessed": expanded_commands.get("$$srcimg_preprocessed$$", None),
        "final": expanded_commands.get("$$srcimg$$", None),
    }
    print(f"keys: {expanded_commands.keys()}")
    
    # searching for scaled entries
    for magic in expanded_commands.keys():
        if 'srcimg_scale' in magic:
            scaletxt = magic.strip('$').removeprefix('srcimg_')
            better_names[scaletxt] = expanded_commands[magic]
        elif '_modulation' in magic:
            base_txt = magic.strip('$').removesuffix('_modulation').removeprefix('srcimg_')
            better_names[base_txt].extend(expanded_commands[magic])
            # very important to extend the pre-existing entry; to preserve overall correct order
        else: continue;
    
    batchdir = workdir/"batchfile"
    batchdir.mkdir(exist_ok=True)
    batch_files = []
    for (title, commandlist) in better_names.items():
        if commandlist is None: continue;
        filepath = batchdir/title
        print(f"writing commands to: batchfile/{filepath.name}")
        with filepath.open(mode='w', encoding='utf-8') as newfile:
            newfile.write('\n'.join(commandlist)); newfile.write('\n\n')
        batch_files.append(filepath)
    print(f"finished writing all batchfiles!\n")
    batch_commands = [f"gm batch -echo on -stop-on-error on '{batchfile}'" for batchfile in batch_files]
    print('\n'.join(batch_commands)); print('\n')
    return batch_commands


def Main(identify_srcimg=False):
    (conf_env_defaults, conf_cmdline_args, main_config) = Config.Init()
    args = ParseCmdline(conf_cmdline_args); Globals.Break("PARSE_ONLY")
    if args is None: exit(0); # debug mode or arglist contained '--help'
    
    # RenderText being used as input-image - which doesn't actually exist yet
    if (hasattr(args, "RenderTextInput")): # hash the filepath itself instead
        image_md5sum = subprocess.check_output(["md5sum", '-'], input=bytes(args.image_path))
    else: image_md5sum = subprocess.check_output(["md5sum", str(args.image_path)]);
    checksum = str(image_md5sum, encoding="utf-8").split()[0]
    assert(len(checksum) == 32), "MD5-hash did not match expected length"
    
    (workdir, wasNewlyCreated) = CreateTempdir(checksum, autodelete=args.autodelete, use_tmpfs=args.use_tmpfs)
    if (workdir is None): print(f"no workdir. exiting"); exit(2); # tmpfs mount attempted and failed
    assert(Globals.TEMPDIR_REF is not None); assert(workdir.exists());
    
    output_directory = ResolveOutputPath(args, workdir.parent)
    print(f"output_directory resolved to: {output_directory}")
    Globals.Break("PARSE_ONLY") # select with '--parse-only 2'
    
    # RenderText being used as input-image; need to generate it now
    if (hasattr(args, "RenderTextInput")):
        RenderTextCmd = args.RenderTextCmd
        assert('default_image_path' not in args.image_path.name), "image_path was not updated to match RenderText output";
        # cannot call SubCommand before log_dir is set by UpdateGlobals (also, Globals have not been updated yet)
        print(f"\n{'_'*120}\n{' '*53}TEXT RENDERING\n{'_'*120}")
        subprocess.run(RenderTextCmd, shell=True, check=True, encoding="utf-8")
        assert(args.image_path.exists()), f"expected RenderText output at: '{args.image_path}'";
        args.rendertext = None # avoiding another 'rendertext' subcommand later
    
    frames_max = (args.duration if (isD := (args.duration is not None)) else args.framecap)
    (source, baseimg, stream_info) = MakeImageSources(workdir, args.image_path, frames_max)
    srcimg = source.srcpath
    
    if (stream_info is not None):
        task_info = stream_info['task_info']
        frames_max = task_info['frames_max']
        PrintDict(task_info, "ffprobe_info")
    else:
        task_info = None;
        (framecount, index_length) = RGB.EstimateSteps(args.stepsize)
        if(frames_max is not None):
            if isD: framecount = frames_max; # duration forces framecount
            elif (frames_max >= framecount): frames_max = 0; # framecap above count gets disabled
            else: framecount = frames_max; # framecap set below framecount reduces it to capacity
            index_length = 1+int(RGB.log10(framecount-1));
        source.frame_count  = framecount
        source.indexlength = index_length
    if (frames_max is None): frames_max = 0;
    
    log_directory = RotateMagickLogs(workdir.parent, main_config["log_limit"])
    Globals.UpdateGlobals(workdir, srcimg, log_directory) # dbgprint=True
    RGB.PrintGlobals() # no-op unless DEBUG_PRINT_GLOBALS / dbgprint
    
    # must be called after UpdateGlobals (needs Globals.WORKING_DIR)
    env_vars = SetupENV(conf_env_defaults)
    
    if identify_srcimg:
        print(baseimg); print(srcimg); print(f"\n{'_'*120}\n")
        SubCommand(f"{('gm convert -list resources' if (Globals.MAGICKLIBRARY=="GM") else 'identify -list resource')}", logname=None)
        SubCommand(f"{('gm ' if (Globals.MAGICKLIBRARY=="GM") else '')}identify -verbose {str(srcimg)}", logname=None)
    
    # text-rendering performed here if an image was given as input. otherwise,
    # if rendered-text is being used as input, it has already been generated
    if (args.rendertext is not None): # reset if RenderTextInput
        print(f"\n{'_'*120}\n{' '*50}TEXT RENDERING\n{'_'*120}")
        (renderTextCmd, rtoutput) = RenderText.BuildCommandline(args.rendertext, workdir)
        SubCommand(renderTextCmd, "text_rendering")
        rtoutput.rename(workdir/'renderedtext.png')
    # TODO: integrate rendered-text into the processing pipeline when source-image is also present
    
    output_filename = f"{source.safe_filename}_RGB"
    print(f"output_filename: {output_filename}")
    print(f"original location: {args.image_path.parent.absolute()}")
    print(f"final: {(output_directory/output_filename).absolute()}")
    
    primary_format = (args.tempformat if (args.tempformat is not None)
                      else ('MPC' if(stream_info is None) else 'MIFF')) # usually OOM with video inputs
    
    color_opts = Task.ColorRemapT(
        (args.white, args.black) if args.remap else None,
        args.fuzz, args.threshold, args.edge, args.edge_radius,
    )
    
    task = Task.TaskT(
        workdir,
        source,
        task_info,
        args.crop,
        args.gravity,
        args.scales,
        color_opts,
        primary_format,
        output_filename,
        output_directory,
        args.output_formats,
    )
    
    expected_outputs = Task.FillExpectedOutputs(task)
    print('\n'); assert(len(expected_outputs) > 0), "no expected outputs"
    
    enumrotations = RGB.EnumRotations(args.stepsize, frames_max)
    if (args.stepwhite or args.stepblack or args.stepedge):
        stepsize_deltas = CalcStepDeltas(args)
        task.stepsize_deltas = stepsize_deltas
        PrintDict(stepsize_deltas, "altsteps")
        print('\n')
    
    # not necessary, but it's nice to seperate each preprocessing step
    if (Globals.MAGICKLIBRARY == "GM"):
        print("INITIAL PREPROCESSING")
        expanded_commands = Task.ImagePreprocess(task)
        preprocess_batch_commands = SavePreprocessingCommands(workdir, expanded_commands); Globals.Break("PRINT_ONLY")
        SubCommand(preprocess_batch_commands, "manual_preprocessing", isCmdSequence=True); print(f"{'_'*120}\n")
    
    print("PREPARING FRAME GENERATION")
    # command_names = ("preprocessing", "frame_generation", "rendering")
    commands = Task.GenerateFrames(task, enumrotations)
    (webp_rendercmds, ffmpeg_commands) = commands[-2:]; commands = commands[:3]
    
    cmd_names = ("preprocessing", "frame_generation", "rendering", "rendering_webp", "rendering_ffmpeg")
    batch_files = [RGB.SaveCommand(name, cmd) for (name, cmd) in zip(cmd_names[:3], commands[:3])][0::1]
    batch_commands = [f"gm batch -echo on -stop-on-error on '{batchfile}'" for batchfile in batch_files]
    
    if Globals.DEBUG_PRINT_CMDS:
        print(f"\n{'_'*120}\n\nDEBUG_PRINT_CMDS!\n{'_'*120}")
        all_command_lists=[*commands,webp_rendercmds,ffmpeg_commands]
        for (cmd_name, cmdlist) in zip(cmd_names, all_command_lists):
            print(f"\n{cmd_name}:\n  {'\n  '.join(cmdlist)}")
        print(f"\nbatch_commands:\n  {'\n  '.join(batch_commands)}")
        print(f"\n{'_'*120}\n")
    Globals.Break("PRINT_ONLY")
    
    if (use_IM := (Globals.MAGICKLIBRARY == "IM")): batch_commands = []; # prevents GM-only cmds
    batch_zip = zip(cmd_names, (batch_commands if (Globals.MAGICKLIBRARY == "GM") else commands))
    for (cmds_name, commands) in batch_zip: SubCommand(commands, cmds_name, isCmdSequence=use_IM)
    if  (len(webp_rendercmds) > 0): SubCommand(webp_rendercmds, cmd_names[3], isCmdSequence=True)
    if  (len(ffmpeg_commands) > 0): SubCommand(ffmpeg_commands, cmd_names[4], isCmdSequence=True)
    print(f"{'_'*120}\n")
    
    if args.nowrite: print('skipping final writes!!'); return;
    print(f"moving outputs to final destinations...")
    checked_outputs = Task.CheckExpectedOutputs(task)
    move_output_cmd = [
        f"cp --verbose --backup=numbered '{work_file}' '{final_dest}'"
        for (work_file, final_dest) in checked_outputs
    ]
    SubCommand(move_output_cmd, logname=None, isCmdSequence=True)
    
    return


if __name__ == "__main__":
    print(f"program path: {Globals.PROGRAM_DIR}")
    print(f"this file: {pathlib.Path(__file__)}")
    Main()
    print("\ndone\n")
