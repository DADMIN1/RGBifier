import argparse
from dataclasses import dataclass


try: import Typesetting.FontManager as FontManager;
except ModuleNotFoundError: import FontManager;


@dataclass
class TextRenderParams:
    m_string: str|None;
    fontname: str|None;
    fontsize: int|None; # pointsize
    autosize: bool
    imgWidth: int|None; # TODO: alternatively specified as fraction/percent of overlaid image-width
    color_fg: str|None; # TODO: StrHex/MaybePercent pseudotypes from CLI. Need to restructure files
    color_bg: str|None;
    basename: str|None; # base-name for output; actual filename has metadata inserted (font, pointsize, image-dimensions, etc)
    spacingK: int|None; # kerning (spacing between letters)
   #spacingW: int|None; # word spacing
   #spacingL: int|None; # line spacing


def CreateParser(positional_syntax:bool) -> argparse.ArgumentParser:
    textparser = argparse.ArgumentParser(allow_abbrev=False)
    if (positional_syntax): textparser.add_argument('text');
    else: textparser.add_argument('--text', required=True);
    
    availfonts = { font.stem for font in FontManager.FONTFILES }
    textparser.add_argument('--font', type=FontManager.FindFont, default=FontManager.DEFAULT_FONT, help=f"available fonts: {availfonts}")
    
    group_size = textparser.add_argument_group("sizing")
    sizingArgs = group_size.add_mutually_exclusive_group()
    sizingArgs.add_argument('--fontsize', type=int, default=144)
    sizingArgs.add_argument('--autosize', action="store_true", help="scale text to always match base image width")
    sizingArgs.add_argument('--imgWidth', type=int, help="automatically adjust font-size to fit the text to this width")
    textparser.add_argument('--kerning', type=int, help="spacing between letters (negative values are allowed)")
    
    grp_colors = textparser.add_argument_group("colors") # StrHex
    # default 'red' when called from main CLI (black/white would not change otherwise)
    grp_colors.add_argument('--fg', default=("RED" if not positional_syntax else None))
    grp_colors.add_argument('--bg')
    
    # "default=SUPPRESS" is necessary when both positional/keyword forms exist; otherwise the positional forces its value to None
    if (positional_syntax): textparser.add_argument('basename', default=argparse.SUPPRESS, metavar='output_name', nargs='?');
    textparser.add_argument('--filename', dest="basename", metavar='output_name')
    
    return textparser


def ParseCmdline(arglist:list[str]|None = None, positional_syntax:bool=False):
    textparser = CreateParser(positional_syntax)
    (parsed_args, unparsed) = textparser.parse_known_intermixed_args(arglist)
    
    RTparameters = TextRenderParams (
        m_string = parsed_args.text,
        fontname = parsed_args.font,
        fontsize = parsed_args.fontsize,
        autosize = parsed_args.autosize,
        imgWidth = parsed_args.imgWidth,
        color_fg = parsed_args.fg,
        color_bg = parsed_args.bg,
        basename = parsed_args.basename,
        spacingK = parsed_args.kerning,
    )
    
    # when this script is run as main program, all arguments should be recognized
    if (positional_syntax and (len(unparsed) > 0)):
        raise SyntaxError(f"unrecognized arguments: {unparsed}");
    return (RTparameters, (parsed_args, unparsed));



# -------------------------------------------------------------------------------------------------------- #

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
