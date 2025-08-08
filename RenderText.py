import argparse
import pathlib
from dataclasses import dataclass
from typing import Callable


@dataclass
class TextSubcommand:
    m_string: str;
    fontpath: pathlib.Path|None; # should be fontname instead?
    fontsize: int|None; # pointsize
    imgWidth: int|None; # TODO: alternatively specified as fraction/percent of overlaid image-width
    color_fg: str|None; # TODO: StrHex/MaybePercent pseudotypes from CLI. Need to restructure files
    color_bg: str|None;
    filename: str|None; # base-name for output; actual filename has metadata inserted (font, pointsize, image-dimensions, etc)
    validationHook: Callable|None;
# TODO: configuration of filename template
# TODO: subcommand RGBifier args; passed to another RGBifier subprocess operating on the generated (text) image
# the design needs to accommodate plural options (rendering at multiple size/font combinations)


# Validation-Hooks are callbacks returned to the main parser, which operate on the main commandline and the text-subcommand;
# checking that all arguments specified are compatible with the text-related subcommand
# and that any requirements introduced (or lifted) by the text-subcommand are fulfilled
def Validation_Default(parsed_args:argparse.Namespace, textcmd:TextSubcommand):
    return True


from Globals import PROGRAM_DIR 
FONTS_DIR = PROGRAM_DIR/"Typesetting"/"Fonts"; assert(FONTS_DIR.is_dir()), "missing fonts directory";
FONTFILES = [*FONTS_DIR.glob("*/*")]

def FindFont(name:str) -> pathlib.Path:
    """ matches files under the 'Fonts' directory by name (ignoring file-extension) """
    if ('.' in name): name = name.rsplit('.', maxsplit=1)[0];
    if ('/' in name): name = name.rsplit('/', maxsplit=1)[1]; print("[ERROR] name given to FindFont contains a path-seperator");
    matches = [font for font in FONTFILES if (font.stem.lower() == name.lower())]
    if (len(matches) >= 2): print(f"[FindFont] multiple fonts matching '{name}': {matches}");
    if (len(matches) == 0): raise FileNotFoundError(f"0 fonts matching '{name}'");
    return matches[0];


def CreateParser(positional_syntax:bool) -> argparse.ArgumentParser:
    textparser = argparse.ArgumentParser(allow_abbrev=False)
    if (positional_syntax): textparser.add_argument('text');
    else: textparser.add_argument('--text', required=True);
    
    availfonts = { font.stem for font in FONTFILES }
    textparser.add_argument('--font', type=FindFont, help=f"available fonts: {availfonts}")
    
    group_size = textparser.add_argument_group("sizing")
    sizingArgs = group_size.add_mutually_exclusive_group(required=True)
    sizingArgs.add_argument('--fontsize', type=int)
    sizingArgs.add_argument('--imgWidth', type=int, help="automatically adjust font-size to fit the text to this width")
    
    grp_colors = textparser.add_argument_group("colors")
    grp_colors.add_argument('--fg') # StrHex
    grp_colors.add_argument('--bg')
    
    # TODO: support plurals (multiple runs of the same command with combinations of several parameters)
    # e.g. rendering the same string at increasing sizes, or rendering in each of several fonts, etc
    
    if (positional_syntax): textparser.add_argument('filename', metavar='output_filename', nargs='?');
    textparser.add_argument('--filename')
    
    # TODO: if the main parser recieves a '--text' command with '--filename' specified,
    # then no input/output image is required by the main program (text-rendering only)
    
    return textparser


def ParseCmdline(arglist:list[str]|None = None, positional_syntax:bool=False):
    textparser = CreateParser(positional_syntax)
    (parsed_args, unparsed) = textparser.parse_known_intermixed_args(arglist)
    
    text_cmdline = TextSubcommand (
        m_string = parsed_args.text,
        fontpath = parsed_args.font,
        fontsize = parsed_args.fontsize,
        imgWidth = parsed_args.imgWidth,
        color_fg = parsed_args.fg,
        color_bg = parsed_args.bg,
        filename = parsed_args.filename,
        validationHook = Validation_Default
    )
    
    # when this script is run as main program, all arguments should be recognized
    if (positional_syntax and (len(unparsed) > 0)):
        raise SyntaxError(f"unrecognized arguments: {unparsed}");
    return (text_cmdline, (parsed_args, unparsed));


def Fuzzing():
    results = []
    for positional_syntax in [True, False]:
        if (positional_syntax): arglist = ["nonpoz text string" , '--fontsize', '69', 'asdfpoz', 'extra'];
        else: arglist = ['--text', "whatever textarg" , '--fontsize', '99', '--filename', 'asdf'];
        
        try:
            print(arglist)
            results.append( { "cmdline": arglist, "positional": positional_syntax, "result": None } )
            result = ParseCmdline(arglist=arglist, positional_syntax=positional_syntax)
            results[-1]["result"] = result; print(result); print('\n');
        except Exception as EX:
            print(EX); results[-1]["result"] = EX; print('\n');
    
    return results


# -------------------------------------------------------------------------------------------------------- #



# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str, allow_whitespace=True, allow_symbols=False) -> str:
    alphabets = ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
    digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
    digit_str = ''.join(digits)
    
    punctuation = [ chr(C) for C in [
        *range(0x21, 0x30),
        *range(0x3A, 0x41),
        *range(0x5B, 0x61),
        *range(0x7B, 0x7F),
    ]]
    
    if text.isalnum(): return text
    ok_chars = ({'_', ' ', '\t', '\n'} if allow_whitespace else {'_'})
    if allow_symbols: ok_chars = { *ok_chars, *punctuation };
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


import subprocess
def CheckFontMetrics(text:str, fontpath:pathlib.Path, pointsize:int):
    filtered_text = f'"{FilterText(text, allow_symbols=True)}"' # TODO: should exclude quotations
    command = f"convert-im6.q16 -debug annotate xc:none -font '{fontpath}' -pointsize {pointsize} -draw 'text 0,0 {filtered_text}' null:"
    # 'null:' specifies empty output (while avoiding the usual error)
    # ImageMagick is required; GraphicsMagick cannot report font metrics
    
    completed = subprocess.run(command, shell=True, text=True, encoding="utf-8", capture_output=True)
    if (completed.returncode != 0): print(f"[ERROR] nonzero exit-status: {completed.returncode}\n");
    print(completed.stderr); print('\n');
    
    lines = [line.strip() for line in completed.stderr.splitlines()]; assert(len(lines) > 0);
    metrics_line = [line for line in lines if ('Metrics: ' in line)][0] # debug info is always repeated 2-3x, for unknown reasons
    metrics = metrics_line.split('Metrics: ', maxsplit=1)[-1]
    metrics_dict = {
        K:V for (K,V) in [
            (pair.split(': ', maxsplit=1))
            for pair in metrics.split('; ')
        ]
    }
    # keys: [text width height ascent descent max advance bounds origin pixels-per-em underline position underline thickness]
    return metrics_dict


def GenerateTextCommand(text:str, fontpath:pathlib.Path, pointsize:int, fg_color:str|None, bg_color:str=None, output_filename:str=None) -> (str, pathlib.Path):
    filtered_text = FilterText(text, allow_symbols=True)
    metrics_dict = CheckFontMetrics(filtered_text, fontpath, pointsize)
    (width, height, Yoffset) = (metrics_dict["width"], metrics_dict["height"], metrics_dict["ascent"])
    
    def AbbrevColor(color:str):
        match color.upper():
            case 'BLUE': return 'U'; # 'B' is reserved for black
            case 'NONE': return '_'; # transparent
        return color.upper()[0]
    
    if (fg_color is None): fg_color = "white";
    if (bg_color is None): bg_color = "none"; # transparent background
    abbreviated_color_suffix = f"{AbbrevColor(fg_color)}{AbbrevColor(bg_color)}"
    
    if not output_filename: output_filename = FilterText(text, False)[:16]; # limit automatic filename length to 16 chars
    else: output_filename = FilterText(output_filename); # allow whitespace in filename only when specified
    output_filename += f"-{fontpath.stem}_{pointsize}_{width}x{height}+{Yoffset}_{abbreviated_color_suffix}.png"
    
    quoted_text_str = f'text 0,{Yoffset} "{filtered_text}"'
    # the order of nested quotations here is critical: double-quote INNER text, single-quotes OUTSIDE!
    # using the incorrect quotation-order makes it impossible to write text containing punctuation (!)
    
    # 'gm convert' also works here
    command = f"convert-im6.q16 -size {width}x{height} "
    command += f"xc:{bg_color} "
    command += f"-font '{fontpath}' -pointsize {pointsize} "
    command += f"-fill {fg_color} -draw '{quoted_text_str}' " # reminder that single-quotes, not-double, are mandatory here
    command += f"'/tmp/RGB_TOPLEVEL/{output_filename}'"
    return (command, output_filename)


def DoEverything():
    (text_cmdline, (parsed_args, unparsed)) = ParseCmdline()
    (text_command, output_filename) = GenerateTextCommand(text_cmdline.m_string, text_cmdline.fontpath, text_cmdline.fontsize, text_cmdline.color_fg, text_cmdline.color_bg)
    print(text_command); print('\n');
    subprocess.run(text_command, shell=True, text=True, encoding="utf-8")
    print(f"\n/tmp/RGB_TOPLEVEL/{output_filename}");
    return output_filename


if __name__ == "__main__":
    DoEverything()
    print("\ndone\n")
    
    # from pprint import pprint
    # def _main():
    #     (text_cmdline, (parsed_args,unparsed)) = ParseCmdline(positional_syntax=True);
    #     print("Text Command: "); pprint(text_cmdline, indent=4, width=150); print('');
    #     print("parsed args:", end='\n\t'); pprint(parsed_args, indent=4); print('\n');
    #     print("unhandled args:", end='\n\t'); pprint(unparsed, indent=4); print('\n');
    #     # ParseCmdline(arglist=["--help"])
    # _main()
