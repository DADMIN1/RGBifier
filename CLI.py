import pathlib
import argparse
import textwrap

import Globals
import RenderText
from ParserTypes import *
import Typesetting.Subparser


def ParseCmdline(arglist:list[str]|None = None, *, debug_mode=False, ignore_input_path=None) -> argparse.Namespace|None:
    """ 
    :param arglist: additional args parsed before commandline
    :param debug_mode: disable exit_on_error and most asserts
    :param ignore_input_path: try to ignore argparse nonsense
    :return: parsed-args, unless '--help' or debug_mode
    ignore_input_path will match debug_mode unless specified
    """
    parser = argparse.ArgumentParser(
        prog="RGBifier", allow_abbrev=False,
        formatter_class=CustomFormatter
    )
    #TODO: description and epilog
    
    parser.exit_on_error = (not debug_mode)
    if (ignore_input_path is None): ignore_input_path = debug_mode;
    default_image_path = pathlib.Path('default_image_path.png')
    
    SETDEBUGMODE(debug_mode)
    
    group_system = parser.add_argument_group("system-options")
    primary_args = parser.add_argument_group("main arguments")
    grp_relative = parser.add_argument_group("relative-flags")
    group_output = parser.add_argument_group("output-options")
    group_relopt = grp_relative.add_mutually_exclusive_group()
    # group_relopt = group_output.add_mutually_exclusive_group()
    group_stepszs = parser.add_argument_group("modulation args")
    grp_transform = parser.add_argument_group("transformations")
    group_recolor = parser.add_argument_group("color-remapping")
    rendertextgrp = parser.add_argument_group("rendertext args")
    textargs_help = parser.add_argument_group(None) # exists only to display RenderText-subparser usage
    # group-title = None: instructs CustomFormatter to suppress indentation when formatting description
    textargs_help.description = Typesetting.Subparser.SubparserInvocationSyntaxDescription + '\n'
    
    parser.add_argument("--print-only", nargs='?', metavar="limit", type=int, const=1, help="exit after printing the commands that would have been executed")
    parser.add_argument("--parse-only", nargs='?', metavar="limit", type=int, const=1, help="exit after completing commandline parsing (and loading config)")
    
    group_system.add_argument("--magick", choices=["IM","GM"], default="GM", help="select magick library (ImageMagick / GraphicsMagick)")
    group_system.add_argument("--tmpfs", dest="use_tmpfs", action="store_true", help="use tmpfs (RAM filesystem) for workdir and tempfiles - preventing all disk writes")
    #group_system.add_argument("--autodelete", dest="autodelete", action="store_true", default=True, help="wipe the (temp) working directory after processing")
    group_system.add_argument("--noclean", dest="autodelete", action="store_false", help="preserve temp-files (deleted by default - ignore the following 'default' message)")
    group_system.add_argument('--nowrite', action="store_true", help="disables relocation of outputs to their final destinations")
    # TODO: fix the display of '--noclean'/autodelete's default message
    
    # alternative non-positional form of 'output_dir' (useful when using '--rendertext' without an input-image)
    group_output.add_argument("--output-dir", dest="output_dir", type=ExplicitPath, metavar="OUTPUT_DIR", help="output location - same as input by default (alternative non-positional arg)")
    group_output.add_argument("--mkdir", action="store_true", help="create output-directory if necessary (all parents must already exist)")
    group_output.add_argument("--mkdir-parent", action="store_true", help="mkdir also creates any missing parent-directories (implies '--mkdir')")
    group_relopt.add_argument("--relative-img", action="store_true", help="reinterpret the output-directory relative to location of source-image")
    group_relopt.add_argument("--relative-cwd", action="store_true", help="reinterpret the output-directory relative to CWD (currrent directory)")
    group_relopt.add_argument("--relative-tmp", action="store_true", help="reinterpret the output-directory relative to RGB_TOPLEVEL (tmpfs dir)")
    # TODO: explain interpretation of output-path and behavior of relative flags
    
    # parser.add_argument("--fps", dest="fps", type=int, default=60, help="FPS of RGB-ified video (default 60)")
    # TODO: fps/numloops/reverse
    
    scale_help = textwrap.dedent("""\
        suffix: '%%' denotes percentage-scaling (integer)
        suffix: 'x' denotes multiplier-scaling (float)
        Outputs will be generated at each scale specified, instead of normal size
        include '100%%' or '1x' to also produce full-size output."""
    )
    
    grav = ["north","south","east","west"]; gravities = (*grav, *[''.join((P,S)) for P in grav[:2] for S in grav[2:]])
    grp_transform.add_argument("--crop", metavar="{[W]x[H][%]}[+X][+Y]", help="crop image to 'WxH', at (optional) offset 'X,Y'")
    grp_transform.add_argument("--gravity", choices=("center",*gravities), default="center", help="anchoring of crop operation")
    grp_transform.add_argument("--scale", nargs=1, dest="scales", action="extend", metavar="{int[%]|float[x]}")
    grp_transform.add_argument("--scales", nargs='+', action="extend", default=[], metavar="{int[%]|float[x]}", help=scale_help)
    
    group_recolor.description = textwrap.dedent("""\
        keep in mind that each library interprets Alpha-channel values differently.
        colors passed on the command-line (without alpha specified) will be opaque,
        but no conversion will be performed when the color has a specified alpha.
          Alpha: [opaque -> transparent]
          ImageMagick:    [0xFF -> 0x00]
          GraphicsMagick: [0x00 -> 0xFF]
          
          the '--alpha' option specifies the default transparency of other colors.
          the range follows the GM convention: 0xFF means 'completely transparent'
          interpretation is not influenced by IM/GM. default value (00) is opaque."""
    )
    
    edgecolor_default = "0x00FF00"
    edge_radius_given = False
    def EdgeRadius(R) -> int:
        nonlocal edge_radius_given; edge_radius_given = True
        if ((radius := int(R)) <= 0): raise ValueError(f"invalid edge-radius: {R}");
        return radius
    
    group_recolor.add_argument("--edge", metavar="RRGGBB[AA]", type=StrHex, nargs='?', const=edgecolor_default, help=f"edge-detection (default color: {edgecolor_default})")
    group_recolor.add_argument("--edge-radius", metavar="int", type=EdgeRadius, default=2, help="edge-detection radius")
    
    # the lambda given for 'type' allows lowercase letters to be passed
    group_recolor.add_argument("--remap", choices=['W','B','WB','BW'], type=lambda S:S.upper(), help="recolor white and/or black areas")
    group_recolor.add_argument("--alpha", metavar="[00 -> FF]", type=StrHex, default="0x00", help="default-alpha for edge and remap")
    group_recolor.add_argument("--white", metavar="RRGGBB[AA]", type=StrHex, default="0xFF0000", help="remapped white")
    group_recolor.add_argument("--black", metavar="RRGGBB[AA]", type=StrHex, default="0x0000FF", help="remapped black")
    group_recolor.add_argument("--fuzz", metavar="int[%]", type=MaybePercent, nargs=2, default=(0, 0), help="fuzz-percent for white and black")
    group_recolor.add_argument("--threshold", metavar="int[%]", type=MaybePercent, nargs=2, default=(10, 10), help="during remap, colors within this distance from white/black are forced to white/black")
    
    group_stepszs.add_argument("--stepsize", type=float, default=1.00, metavar='(float)', help="modulation per frame - 1/200th of full cycle")
    group_stepszs.add_argument("--stepedge", type=float, metavar='(float)', help="override stepsize for edge-highlight")
    group_stepszs.add_argument("--stepwhite", type=float, metavar='(float)', help="override stepsize for white-recolor")
    group_stepszs.add_argument("--stepblack", type=float, metavar='(float)', help="override stepsize for black-recolor")
    maxframesargs = group_stepszs.add_mutually_exclusive_group()
    maxframesargs.add_argument("--framecap", type=int, metavar='(int)', help="limit the number of frames in output")
    maxframesargs.add_argument("--duration", type=int, metavar='(int)', help="specifies number of frames in output")
    
    valid_fileformats = FormatList("GIF", "MP4", "APNG", "WEBP", "ALL")
    group_output.add_argument("--format", dest="output_formats", metavar="fmt",
        choices=valid_fileformats, nargs='+', action='append', default=["GIF"],
        help=f"list of output formats: {valid_fileformats}\n"
        +"names can be in lowercase and may have a leading dot ('.gif')\n"
        +"animated WebP specifically requires ImageMagick (--magick=IM)\n"
        +"MP4 and APNG outputs require ffmpeg"
    )
    
    valid_frameformats = FormatList('MPC','MIFF')
    parser.add_argument("--tempformat",
        choices=valid_frameformats,
        type=lambda S:S.upper(),
        help=textwrap.dedent("""\
            frame-format used during intermediate processing.
            'MPC' is the default for images, 'MIFF' for video.
            select 'MIFF' instead if you're running out of memory.
            
            MPC offers significantly better performance, but also extremely high memory-usage.
            MPC cannot be enabled unless tmpfs is also enabled to avoid excessive disk-writes
            for MPC, I recommended allocating at least 32GB RAM for your tmpfs; 24GB minimum!
            \b""") # prevents an annoying space being inserted before (default: )
    )
    
    rendertext_help = textwrap.dedent("""\
        string to render (should be single-quoted)
        When this argument is present on the command-line,
        and no input-image is specified, the rendered text will be RGBified.
        All RenderText-options present on the command-line will be included."""
    )
    
    rendertextgrp.add_argument("--rendertext", metavar="TEXT", help=rendertext_help)
    # only stores the '--text' value; even with 'nargs=*', it only consumes one arg
    # commandline args will get passed back and forth with the RenderText subparser instead
    
    # printing usage would not display these because they haven't been added yet
    patched_usage = f"{parser.format_usage()}\t\tIMAGE [DIRECTORY]\n"
    helpmsg = parser.format_help().removeprefix(parser.format_usage()) # removing incomplete usage from help
    if ((arglist is not None) and ('--help' in arglist)): print(f"{patched_usage}{helpmsg}\n"); return None;
    # TODO: unfortunately, the help section still won't contain entries for these options
    # also, 'ignore_input_path' causes 'IMAGE' to disappear from usage (when using '--help')
    
    parsed_args = None; print("parsing args...")
    if ((arglist is not None) and (len(arglist) > 0)):
        print(f"additional args given: {arglist}")
        parsed_args = parser.parse_args(arglist)
        print(f"[parsed arglist]: {parsed_args}")
    
    # seperating out the rendertext args
    # must do this before any positional-args are added, otherwise it eats args meant for subparser
    (parsed_args, unparsed) = parser.parse_known_args(namespace=parsed_args)
    # Do NOT use 'parse_known_INTERMIXED_args' - causes bizarre errors when called from main:
        # _format_usage: usage = usage % dict(prog=self._prog) <-- internal argparse function
        # ValueError: unsupported format character ']' (0x5d) at index 336
    
    if parsed_args.rendertext is not None:
        rendertext_args = ["--text", parsed_args.rendertext, *unparsed]
        if debug_mode: print(f"rendertext args: {rendertext_args}");
        (RTparameters, (text_args, remainder)) = Typesetting.Subparser.ParseCmdline(rendertext_args)
        if debug_mode:
            print(f"RT_params: {RTparameters}\n")
            print(f"text_args: {text_args}\n")
            print(f"remainder: {remainder}\n")
        parsed_args.rendertext = RTparameters
        unparsed = remainder
        
        # image-path not provided - rendertext output will be used as input instead
        if (len(remainder) == 0): # assuming this means no positionals were given
            print("image_path argument is absent; using rendertext instead\n")
            if (parsed_args.rendertext.basename is None):
                parsed_args.rendertext.basename = "rendered_text"
            basename = RenderText.FilterText(parsed_args.rendertext.basename)
            (RT_cmd, RT_filepath) = RenderText.BuildCommandline(RTparameters)
            parsed_args.__setattr__("RenderTextInput", True)
            parsed_args.__setattr__("RenderTextCmd", RT_cmd)
            default_image_path = RT_filepath
            ignore_input_path = True
    # done with rendertext subparser
    
    # defining this first to provide a default value; defining after doesn't work. BOTH arguments need 'nargs=argparse.SUPPRESS'
    if ignore_input_path: primary_args.add_argument("image_path", help=argparse.SUPPRESS, nargs=argparse.SUPPRESS, type=pathlib.Path, default=default_image_path);
    
    # positional arguments must be added after initial arglist parse, otherwise providing an image-path is absolutely mandatory.
    # argparse forcibly terminates when image-path isn't provided, even if an image-path has already been set in the Namespace.
    # this behavior cannot be avoided by disabling 'exit_on_error', not even for 'parse_known_args' or 'parse_intermixed_args'.
    primary_args.add_argument("image_path", type=pathlib.Path, metavar="IMAGE", help="path of image being RGBified (this argument is mandatory)", nargs=(argparse.SUPPRESS if ignore_input_path else None))
    primary_args.add_argument("output_dir", type=ExplicitPath, metavar="DIRECTORY", help="output location - same as input by default", nargs=(argparse.SUPPRESS if (parsed_args.output_dir is not None) else '?'))
    # "nargs=SUPPRESS" is necessary on output_dir because both positional/keyword forms exist; otherwise the positional always forces its value to None
    
    parsed_args = parser.parse_args(args=unparsed, namespace=parsed_args)
    print(f"[parsed cmdline]: {parsed_args}\n")
    
    parsed_args.image_path = parsed_args.image_path.expanduser().resolve().absolute()
    print(f"(expanded) image_path: '{parsed_args.image_path}'")
    
    if parsed_args.nowrite:
        print("\nrelocation of outputs is disabled (--nowrite)")
        if parsed_args.autodelete: print("[WARNING] --nowrite given with autodelete active; output will not be observable (try --noclean)");
        if (parsed_args.output_dir is not None): print(f"[WARNING] output-directory will be ignored (--nowrite): {parsed_args.output_dir}");
        if any([parsed_args.relative_img, parsed_args.relative_cwd, parsed_args.relative_tmp]): print("warning: '--relative' arg will be ignored (--nowrite)")
        print('')
    
    # any args will be in a list appended to default, so just use that list if it exists 
    if (len(parsed_args.output_formats) > 1): parsed_args.output_formats = parsed_args.output_formats[1];
    parsed_args.output_formats = [*set(fmt.upper().removeprefix('.') for fmt in parsed_args.output_formats)]
    if ("ALL" in parsed_args.output_formats):
        lastindex = (3 if (parsed_args.magick == "GM") else 4) # GM won't include 'WEBP'
        parsed_args.output_formats = [fmt.upper() for fmt in valid_fileformats[:lastindex]]
    print(f"selected output-filetypes: {parsed_args.output_formats}")
    
    if (("WEBP" in (formats := parsed_args.output_formats)) and (parsed_args.magick == "GM")):
        print("\n[WARNING] 'WebP' format is only compatible with ImageMagick - not GraphicsMagick. (use: '--magick=IM')")
        if (len(formats) > 1): parsed_args.output_formats = [F for F in formats if (F != "WEBP")]; print("[WARNING] excluding WebP!");
        else: print("automatically switching to ImageMagick backend"); parsed_args.magick="IM"; # when no other format was selected
    print("")
    
    ASSERT((parsed_args.stepsize != 0), "stepsize must not be zero")
    ASSERT((len(parsed_args.output_formats) > 0), "missing output format")
    ASSERT((all([(fmt in valid_fileformats) for fmt in parsed_args.output_formats])), "invalid format after processing cmdline")
    if not ignore_input_path: ASSERT((parsed_args.image_path.exists()), f"[ERROR] non-existent input_path: [{parsed_args.image_path}]");
    
    Globals.MAGICKLIBRARY = parsed_args.magick; debug_flags = []
    def Extend(S, C): debug_flags.extend([S for _ in range(C)]);
    if (FC := parsed_args.print_only): Extend("PRINT_ONLY", FC);
    if (FC := parsed_args.parse_only): Extend("PARSE_ONLY", FC);
    if (len(debug_flags)): Globals.ApplyDebugFlags(debug_flags);
    
    
    # if white or black were given, set 'remap' accordingly
    remap_str = '' if (parsed_args.remap is None) else parsed_args.remap;
    if any(colors_given := (
        (parsed_args.white != StrHex(parser.get_default('white'))),
        (parsed_args.black != StrHex(parser.get_default('black'))))):
        for (color,given) in zip(('white','black'), (colors_given)):
            if not given: continue;
            if(color[0].upper() in remap_str): continue;
            print(f"remapping-color given: '--{color}'")
            remap_str += color[0].upper()
        parsed_args.remap = remap_str
    
    # if parsed_args.stepwhite: ASSERT(('W' in remap_str), "stepwhite given without remap:W");
    # if parsed_args.stepblack: ASSERT(('B' in remap_str), "stepblack given without remap:B");
    for (color,given) in zip(('white','black'), (parsed_args.stepwhite, parsed_args.stepblack)):
        if given is None: continue;
        if(color[0].upper() in remap_str): continue;
        print(f"alt-stepsize used: '--step{color}'")
        remap_str += color[0].upper()
        parsed_args.remap = remap_str
    
    
    alpha = None; default_alpha = None
    if (parsed_args.alpha == StrHex("0x00")): parsed_args.alpha = None; # defaulted
    else: # alpha value was specified
        parsed_args.alpha = parsed_args.alpha[(0 if (parsed_args.magick == 'IM') else 1)].removeprefix('0x')
        (alpha, default_alpha) = (parsed_args.alpha[:2], parsed_args.alpha[-2:])
        if (default_alpha not in ('00','FF')): print(f"[WARNING]: alpha is not using a default alpha-value: 0x{parsed_args.alpha[:-2]}[{default_alpha}]");
        if ((middle := parsed_args.alpha[2:-2]) != '0000'): print(f"[WARNING]: alpha contains unexpected digits: 0x{alpha}[{middle}]{default_alpha}");
        
        if (parsed_args.magick == 'IM'): alpha = hex(int('0xFF',16) - int(alpha,16)).removeprefix('0x');
        if not (parsed_args.remap or parsed_args.edge or edge_radius_given):
            print("[WARNING] 'alpha' option will have no effect - specified without 'edge' or 'remap' active")
            alpha = None; default_alpha = None;
        parsed_args.alpha = alpha
    
    
    if ((edge_radius_given or parsed_args.stepedge) and (parsed_args.edge is None)):
        print(f"edge-radius given with edge-color unspecified - using default value ({edgecolor_default})")
        parsed_args.edge = StrHex(edgecolor_default)
    
    if (parsed_args.edge):
        parsed_args.edge = parsed_args.edge[0 if (parsed_args.magick == 'IM') else 1]
        ASSERT(((L:=len(H:=(parsed_args.edge.removeprefix('0x')))) == 8), f"edgecolor hex '{H}' has invalid length: {L}")
        if (alpha and parsed_args.edge.endswith(default_alpha)): parsed_args.edge = f"{parsed_args.edge[:-2]}{alpha}";
    
    if (parsed_args.remap):
        parsed_args.white = parsed_args.white[0 if (parsed_args.magick=='IM') else 1]
        parsed_args.black = parsed_args.black[0 if (parsed_args.magick=='IM') else 1]
        for S in (parsed_args.white, parsed_args.black):
            ASSERT((L:=len(S.removeprefix('0x')) == 8), f"color-hexcode '{S}' has invalid length: {L}")
        ASSERT((all([(percent >= 0) and (percent <= 100) for percent in parsed_args.fuzz])), f"invalid fuzz percent! ({parsed_args.fuzz})")
        if not (RW:=('W' in parsed_args.remap)): parsed_args.white = None;
        if not (RB:=('B' in parsed_args.remap)): parsed_args.black = None;
        if alpha:
            if (RW and (W:=parsed_args.white).endswith(default_alpha)): parsed_args.white = f"{W[:-2]}{alpha}";
            if (RB and (B:=parsed_args.black).endswith(default_alpha)): parsed_args.black = f"{B[:-2]}{alpha}";
    
    if (parsed_args.framecap is not None): ASSERT((parsed_args.framecap >= 0), "framecap must be positive");
    if (parsed_args.duration is not None): ASSERT((parsed_args.duration >= 0), "duration must be positive");
    
    if debug_mode: print(""); # spacing after ASSERT-messages
    if (hasattr(parsed_args, "RenderTextInput")): # unsetting 'ignore_input_path' so that parsed_args is returned
        ignore_input_path = False; # set earlier to allow parsing without an input_path
    
    print(parsed_args) # Namespace(...)
    PrintDict(parsed_args.__dict__, "args")
    return (parsed_args if not (debug_mode or ignore_input_path) else None)


# output-directory cannot be resolved during initial parsing because 'relative_tmp' requires knowledge of 'TEMPDIR'
# also, the 'mkdir' calls would be a serious problem if they occurred before tmpfs was actually mounted
def ResolveOutputPath(parsed_args:argparse.Namespace, toplevel:pathlib.Path):
    """resolves output-directory path and handles related args \n
       this function must only be called after 'CreateTempdir()'
       :param parsed_args: namespace returned by 'ParseCmdline()'
       :param toplevel: "RGB_TOPLEVEL" directory (Globals.TOPLEVEL_NAME)
       :returns: output-directory path
    """
    assert(Globals.TEMPDIR_REF is not None), "TEMPDIR has not been initialized";
    assert(toplevel.name == Globals.TOPLEVEL_NAME), f"toplevel name: {toplevel.name}; expected: {Globals.TOPLEVEL_NAME}";
    assert(toplevel.is_dir()), "toplevel-path does not exist or is not a directory!";
    
    print(f"resolving output-path...")
    print(f"toplevel: {toplevel}")
    # print(f"parsed_args:\n{parsed_args}\n")
    # PrintDict(parsed_args.__dict__, "parsed_args")
    if isinstance(parsed_args.output_dir, ExplicitPath):
        dir_repr = "".join(parsed_args.output_dir.argz)
    else: dir_repr = parsed_args.output_dir;
    print(f"(unparsed) output_dir: '{dir_repr}'")
    
    relative_flags = (
        (parsed_args.relative_tmp, toplevel),
        (parsed_args.relative_cwd, pathlib.Path.cwd()),
        (parsed_args.relative_img, parsed_args.image_path.parent),
    )
    
    # when output-path is unspecified, relative flags may control the location 
    outdir_default = parsed_args.image_path.parent
    for (arg, path) in (relative_flags):
        if (arg): outdir_default = path; break;
    
    print(f"relative-flags: {relative_flags}")
    print(f"outdir-default: {outdir_default}")
    
    if ((out_path := parsed_args.output_dir) is None): out_path = ExplicitPath('.');
    parsed_args.output_dir = out_path = (
        outdir_default if (not parsed_args.output_dir) or out_path.is_empty
        else out_path.under(toplevel) if parsed_args.relative_tmp
        else out_path.under(pathlib.Path.cwd()) if parsed_args.relative_cwd or (out_path.explicit and not parsed_args.relative_img)
        else out_path.under(parsed_args.image_path.parent) if parsed_args.relative_img or (out_path.relative and not parsed_args.relative_cwd)
        else out_path
    ).expanduser().resolve().absolute()
    
    print(f"(expanded) output_dir: '{parsed_args.output_dir}/'")
    
    if parsed_args.mkdir_parent: parsed_args.mkdir = True;
    if not (mkdir_success := out_path.exists()):
        if parsed_args.mkdir and (out_path.parent.exists() or parsed_args.mkdir_parent):
            mkdir_success = True
            out_path.mkdir(parents=parsed_args.mkdir_parent)
            print(f"created output directory: '{out_path.name}'")
        elif not out_path.parent.exists():
            missing_parents = [*reversed([(highest := P).name for P in out_path.parents if not P.exists()])]
            above_top = f".../{abv.name}" if ((abv := highest.parent).parent.parts != tuple(out_path.root,)) else ''
            rel_miss = f"'{out_path.parent.name}/{out_path.name}' ({'/'.join([above_top, *missing_parents])}/)"
            top_miss = f"'{highest.name}' ({highest.absolute()}/)"
            print(f"[ERROR] cannot create parent of nested subdirectories: {rel_miss} under non-existent location: {top_miss}")
            print(f"  specify '--mkdir-parent' to auto-create all missing subdirectories: {[*missing_parents, out_path.name]}")
        elif not parsed_args.mkdir:
            print(f"[ERROR] nonexistent output-directory: {out_path}")
            print("  specify '--mkdir' to auto-create this directory")
    if not out_path.exists(): print("  output-directory could not be created."); mkdir_success = False;
    elif not out_path.is_dir(): print("  output-directory is not a directory."); mkdir_success = False;
    if not mkdir_success: print("  exiting...\n"); exit(6)
    
    return out_path


def CalcDeltas(parsed_args:argparse.Namespace):
    stepsize = parsed_args.stepsize
    # noinspection PyUnboundLocalVariable
    # ^ ignore BS warning about reference before assignment on 'delta'
    stepsize_delta = {
        name: delta
        for (name, altstep) in zip(
            ('edge','white','black'),
            (parsed_args.stepedge,
            parsed_args.stepwhite,
            parsed_args.stepblack)
        ) if (altstep is not None)
        and ((delta:=(altstep-stepsize)) != 0)
    }
    return stepsize_delta


if __name__ == "__main__":
    import sys
    # note that default-args from user configs aren't loaded here
    if (len(sys.argv) == 1): # if no args given: sys.argv == ['CLI.py']
        # TODO: --help output changes when passed in arglist (both are slightly broken - see line #158)
        assert(ParseCmdline(["--help"]) is None), "unexpected value returned by '--help' command";
        exit(0)
    
    # got_args = ParseCmdline()
    # stepsize_deltas = CalcDeltas(got_args)
    # PrintDict(stepsize_deltas,"stepsizes")
    ParseCmdline(debug_mode=True)
    # ParseCmdline(debug_mode=False, ignore_input_path=True)
    # ParseCmdline(debug_mode=True, ignore_input_path=False)
    
