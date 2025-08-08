import argparse
import pathlib
from dataclasses import dataclass
from typing import Callable


try: import Typesetting.FontManager as FontManager;
except ModuleNotFoundError: import FontManager;


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


def CreateParser(positional_syntax:bool) -> argparse.ArgumentParser:
    textparser = argparse.ArgumentParser(allow_abbrev=False)
    if (positional_syntax): textparser.add_argument('text');
    else: textparser.add_argument('--text', required=True);
    
    availfonts = { font.stem for font in FontManager.FONTFILES }
    textparser.add_argument('--font', type=FontManager.FindFont, help=f"available fonts: {availfonts}")
    
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
