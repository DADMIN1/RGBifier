import pathlib
import argparse
import textwrap

import Globals


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str) -> str:
    if text.isalnum(): return text
    ok_chars = {'_'}
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


def PrintDict(D:dict, name=None):
    if name is not None: print(f"{name} = "+"{ ");
    for (k,v) in D.items(): print(f"  {k}: {v},");
    if name is not None: print("}\n");


class ExplicitPath(pathlib.Path):
    """Path which differentiates explicit and implicit relativity, and preserves any single-dots ('.') within input"""
    def __init__(self, *args):
        (self.argzero, self.argz) = tuple(
            (str(args[0]).strip(), ''.join(str(arg).strip() for arg in args))
            if bool(args) else ('','')
        )
        self.is_empty = (not args) or (not self.argz) or (not self.argzero)
        self.is_absol = self.argzero.startswith(('/','~')) or pathlib.Path(self.argz).expanduser().is_absolute()
        self.explicit = self.argzero.startswith(('.','..','./'))
        self.relative = self.explicit or ((not self.is_absol) and (not self.is_empty))
        super().__init__(self.argz)
    
    def __str__(self):  return self.argz;
    def __repr__(self): return f"ExplicitPath('{self.argz}')";
    def PrintDict(self): PrintDict(self.__dict__, repr(self));
    
    def under(self, newparent:pathlib.Path):
        if self.is_empty: return newparent;
        top_parent = (self.parents[-1] if (len(self.parents) > 0) else '/')
        return newparent.joinpath(
            pathlib.Path(self.argz).relative_to(top_parent)
            if (self.is_absol) else pathlib.Path(self.argz)
        )
    
    # division operator: (path / str|path)
    def __truediv__(self, key:str|pathlib.Path) -> pathlib.Path:
        if self.is_empty: return pathlib.Path(key);
        try: return pathlib.Path(self.argz).joinpath(key);
        except TypeError: return NotImplemented;
    
    def __rtruediv__(self, key:str|pathlib.Path):
        if self.is_empty: return pathlib.Path(key);
        try: return self.under(pathlib.Path(key));
        except TypeError: return NotImplemented;


#valid_fileformats
class FormatList():
    """String-list with lenient (caseless) comparisons and inclusion-rules"""
    def __init__(self, *strings:str): self.strings = tuple((S.upper() for S in strings));
    def __contains__(self,other:str): return (other.lstrip('.').upper() in self.strings); # operator 'in'
    def __eq__(self,other:str):       return (other.lstrip('.').upper() in self.strings);
    def __repr__(self): return repr((*self.strings, *(S.lower() for S in self.strings))); # display for debugger/interpreter
    def __str__(self):  return str(self.strings);  # display for print() and str()
    def __iter__(self): return self.strings.__iter__(); # using argparse 'choices'
    def __getitem__(self, at): return self.strings.__getitem__(at); # []-subscript


# custom formatter_class combining the behavior of two arparse formatters
# allows newlines within help-text and automatically appends info about default value
class CustomFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, prog): super().__init__(prog, indent_increment=2, max_help_position=32, width=70);

# argparse.MetavarTypeHelpFormatter (default metavar = type) always fails with this error:
# "AttributeError: 'NoneType' object has no attribute '__name__'. Did you mean: '__ne__'?"
# seemingly triggered by any option without a 'type' specified (like any transform option)


def ParseCmdline(arglist:list[str]|None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="RGBifier", allow_abbrev=False,
        formatter_class=CustomFormatter
    )
    #TODO: description and epilog
    
    group_system = parser.add_argument_group("system-options")
    primary_args = parser.add_argument_group("main arguments")
    grp_relative = parser.add_argument_group("relative-flags")
    group_output = parser.add_argument_group("output-options")
    group_relopt = grp_relative.add_mutually_exclusive_group()
    # group_relopt = group_output.add_mutually_exclusive_group()
    grp_transform = parser.add_argument_group("transformations")
    group_recolor = parser.add_argument_group("color-remapping")
    
    # grp_relative.title = None # prevents title from printing; leaving a single empty line above group
    
    group_system.add_argument("--magick", choices=["IM","GM"], default="GM", help="select magick library (ImageMagick / GraphicsMagick)")
    group_system.add_argument("--tmpfs", dest="use_tmpfs", action="store_true", help="use tmpfs (RAM filesystem) for workdir and tempfiles - preventing all disk writes")
    #group_system.add_argument("--autodelete", dest="autodelete", action="store_true", default=True, help="wipe the (temp) working directory after processing")
    group_system.add_argument("--noclean", dest="autodelete", action="store_false", help="preserve temp-files (deleted by default - ignore the following 'default' message)")
    # TODO: fix the display of '--noclean'/autodelete's default message
    group_system.add_argument("--print-only", nargs='?', metavar="limit", type=int, const=1, help="exit after printing the commands that would have been executed")
    group_system.add_argument("--parse-only", nargs='?', metavar="limit", type=int, const=1, help="exit after completing commandline parsing (and loading config)")
    
    group_output.add_argument("--mkdir", action="store_true", help="create output-directory if necessary (all parents must already exist)")
    group_output.add_argument("--mkdir-parent", action="store_true", help="mkdir also creates any missing parent-directories (implies '--mkdir')")
    group_relopt.add_argument("--relative-img", action="store_true", help="reinterpret the output-directory relative to location of source-image")
    group_relopt.add_argument("--relative-cwd", action="store_true", help="reinterpret the output-directory relative to CWD (currrent directory)")
    group_relopt.add_argument("--relative-tmp", action="store_true", help="reinterpret the output-directory relative to RGB_TOPLEVEL (tmpfs dir)")
    # TODO: explain interpretation of output-path and behavior of relative flags
    
    # parser.add_argument("--fps", dest="fps", type=int, default=60, help="FPS of RGB-ified video (default 60)")
    # TODO: duration/fps/numloops/reverse
    
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
    
    # GraphicsMagick - alpha '00'->opaque, 'FF'->transparent; default alpha is opaque
    def StrHexGM(num:str): return "0x{:08X}".format(int(f"{num}{'0'*(8-len(num.removeprefix('0x')))}",16));
    def StrHexIM(num:str): # ImageMagick - alpha '00'->transparent, 'FF'->opaque
        count = len(num.removeprefix('0x')); alphaLength = max(8-count, 0)
        FL = min(alphaLength, 2); alpha = ('0' * max((alphaLength-FL), 0))+('F' * FL)
        return f"0x{hex(int(num, 16)).removeprefix('0x').upper().zfill(count)}{alpha}"
    
    def StrHex(num:str): return (StrHexIM(num), StrHexGM(num)); # need both until we know which library
    
    def MaybePercent(num:str):
        num = int(float(num)*100) if ('.' in num) else int(num.removesuffix('%'))
        if ((num < 0) or (num > 100)): raise Exception(f"invalid percent: {num}");
        return num
    
    group_recolor.description = textwrap.dedent("""\
        keep in mind that Alpha-channel value is interpreted differently by each library
        colors passed on the command-line (without alpha specified) will be opaque,
        but no conversion will be performed when the color has a specified alpha.
        
        Alpha: [opaque -> transparent] || ImageMagick: [FF -> 00] || GraphicsMagick: [00 -> FF]"""
    )
    
    group_recolor.add_argument("--edge", metavar="RRGGBB[AA]", type=StrHex, nargs='?', const="0x00FF00", help="edge-detection (default color: 0x00FF00)")
    group_recolor.add_argument("--edge-radius", metavar="int", type=int, default=2, help="edge-detection radius")
    # the lambda given for 'type' allows lowercase letters to be passed
    group_recolor.add_argument("--remap", choices=['W','B','WB','BW'], type=lambda S:S.upper(), help="recolor white and/or black areas")
    group_recolor.add_argument("--fuzz", metavar="int[%]", type=MaybePercent, nargs=2, default=(10, 50), help="fuzz-percent for white and black")
    group_recolor.add_argument("--white", metavar="RRGGBB[AA]", type=StrHex, default="0xFF0000", help="remapped white")
    group_recolor.add_argument("--black", metavar="RRGGBB[AA]", type=StrHex, default="0x0000FF", help="remapped black")
    
    if ('--help' in arglist): parser.print_help(); print('\n'); exit(0);
    parsed_args = None; print("\nparsing args...")
    if ((arglist is not None) and (len(arglist) > 0)):
        print(f"additional args given: {arglist}")
        parsed_args = parser.parse_args(arglist)
        print(f"[parsed arglist]: {parsed_args}")
    
    # TODO: use 'parse_known_args' and 'parse_intermixed_args' for this behavior
    # positional arguments must be added after initial arglist parse, otherwise it errors because they're required 
    primary_args.add_argument("image_path", type=pathlib.Path, metavar="IMAGE", help="path of image being RGBified (this argument is mandatory)")
    primary_args.add_argument("output_dir", type=ExplicitPath, metavar="DIRECTORY", nargs='?', help="output location - same as input by default")
    primary_args.add_argument("--stepsize", type=float, default=1.00, metavar='(float)', help="modulation per frame - 1/200th of full cycle")
    
    valid_fileformats = FormatList("GIF", "MP4", "APNG", "WEBP", "ALL")
    group_output.add_argument("--format", dest="output_formats", metavar="fmt",
        choices=valid_fileformats, nargs='+', action='append', default=["GIF"],
        help=f"list of output formats: {valid_fileformats}\n"
        +"names can be in lowercase and may have a leading dot ('.gif')\n"
        +"animated WebP specifically requires ImageMagick (--magick=IM)\n"
        +"MP4 and APNG outputs require ffmpeg"
    )
    
    parsed_args = parser.parse_args(namespace=parsed_args)
    print(f"[parsed cmdline]: {parsed_args}\n")
    
    parsed_args.image_path = parsed_args.image_path.expanduser().resolve().absolute()
    print(f"(expanded) image_path: '{parsed_args.image_path}'")
    
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
    
    # assert(isinstance(parsed_args.fps, int))
    assert(parsed_args.stepsize != 0), "stepsize must not be zero"
    assert(len(parsed_args.output_formats) > 0), "missing output format"
    assert(all([(fmt in valid_fileformats) for fmt in parsed_args.output_formats])), "invalid format after processing cmdline"
    if not parsed_args.image_path.exists(): print(f"[ERROR] non-existent input_path: [{parsed_args.image_path}]"); exit(1);
    
    Globals.MAGICKLIBRARY = parsed_args.magick; debug_flags = []
    def Extend(S, C): debug_flags.extend([S for _ in range(C)]);
    if (FC := parsed_args.print_only): Extend("PRINT_ONLY", FC);
    if (FC := parsed_args.parse_only): Extend("PARSE_ONLY", FC);
    if (len(debug_flags)): Globals.ApplyDebugFlags(debug_flags);
    
    if (parsed_args.edge):
        parsed_args.edge = parsed_args.edge[0 if (parsed_args.magick=='IM') else 1]
        assert(L:=len(H:=(parsed_args.edge.removeprefix('0x')))==8), f"edgecolor hex '{H}' has invalid length: {L}";
    
    if (parsed_args.remap):
        parsed_args.white = parsed_args.white[0 if (parsed_args.magick=='IM') else 1]
        parsed_args.black = parsed_args.black[0 if (parsed_args.magick=='IM') else 1]
        for S in (parsed_args.white, parsed_args.black):
            assert(L:=len(S.removeprefix('0x')) == 8), f"color-hexcode '{S}' has invalid length: {L}";
        assert(all([(percent >= 0) and (percent <= 100) for percent in parsed_args.fuzz])), "invalid fuzz percent!";
        if ('W' not in parsed_args.remap): parsed_args.white = None;
        if ('B' not in parsed_args.remap): parsed_args.black = None;
     
    print(parsed_args) # Namespace(...)
    PrintDict(parsed_args.__dict__, "args")
    return parsed_args


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


if __name__ == "__main__":
    ParseCmdline(["--help"])
