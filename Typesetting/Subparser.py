import argparse
from dataclasses import dataclass

try: import Typesetting.FontManager as FontManager;
except ModuleNotFoundError: import FontManager;

from MagickColors import (LoadMagickColors, FormatColorList)
from ParserTypes import *


@dataclass
class TextRenderParams:
    m_string: str|None;
    fontname: str|None;
    fontsize: int|None; # pointsize
    autosize: bool
    imgWidth: int|None; # TODO: implement imgWidth option. alternatively specified as fraction/percent of overlaid image-width
    color_fg: str|None;
    color_bg: str|None;
    basename: str|None; # base-name for output; actual filename has metadata inserted (font, pointsize, image-dimensions, etc)
    spacingK: int|None; # kerning (spacing between letters)
    spacingW: int|None; # word spacing
    spacingL: int|None; # line spacing



def CreateParser(positional_syntax: bool, dump_colors=True) -> argparse.ArgumentParser:
    textparser = argparse.ArgumentParser(prog="RenderText", allow_abbrev=False, formatter_class=CustomFormatter)
    if (positional_syntax): textparser.add_argument("text",help="(should be single-quoted)");
    else: textparser.add_argument('--text', required=True, help="(should be single-quoted)");
    
    availfonts = { font.stem for font in FontManager.FONTFILES }
    textparser.add_argument('--font', type=FontManager.FindFont, default=FontManager.DEFAULT_FONT, help=f"available fonts: {availfonts}")
    
    group_sizing = textparser.add_argument_group("sizing options")
    sizing_group = group_sizing.add_mutually_exclusive_group()
    sizing_group.add_argument('--fontsize', type=int, default=144, metavar='--pointsize <int>', help="pointsize")
    sizing_group.add_argument('--pointsize', dest="fontsize", metavar='<int>', help=argparse.SUPPRESS)
    #sizing_group.add_argument('--fontsize', '--pointsize', type=int, default=144, metavar='<int>', help="pointsize")
    sizing_group.add_argument('--autosize', action="store_true", help="scale text to always match base image width")
    sizing_group.add_argument('--imgWidth', type=int, help=argparse.SUPPRESS) # help="adjust the text to fit this width"
    
    spacing_args = textparser.add_argument_group("spacing options")
    spacing_args.description = "all arguments accept positive and negative integers (negative values condense text instead)"
    # spacing_args.add_argument('--letter-spacing', '--kerning', dest='kerning', metavar='<int>', help="spacing between letters")
    spacing_args.add_argument('--kerning', type=int, metavar='<int>', help=argparse.SUPPRESS)
    spacing_args.add_argument('--letter-spacing', dest='kerning', metavar='--kerning <int>', help="spacing between letters")
    spacing_args.add_argument('--word-spacing', type=int, metavar='<int>', help="spacing between words")
    spacing_args.add_argument('--line-spacing', type=int, metavar='<int>', help="spacing between lines")
    
    # IM includes both spellings for gray/grey
    MAGICK_COLORMAP = LoadMagickColors()["IM"]
    knownColorNames = FormatList(*MAGICK_COLORMAP.keys())
    def ColorLookup(color):
        if color in knownColorNames: return color; # no translation necessary
        return f"'#{StrHex(color)[0].removeprefix('0x')}'" # always IM syntax
    
    grp_colors = textparser.add_argument_group("coloring options") # StrHex | colorname
    if positional_syntax:
        grp_colors.add_argument('--fg', metavar='<color>', type=ColorLookup) # help="text-color"
        grp_colors.add_argument('--bg', metavar='<color>', type=ColorLookup) # help="background"
    else:
        # default 'red' value when called from main CLI (black / white would not change otherwise)
        grp_colors.add_argument('--textcolor', metavar='<color>', type=ColorLookup, default='RED')
        # if 'recognized-colors' is going to be listed, this info will be put in that description instead
        grp_colors.description = "colors are specified by name ('Red', 'AliceBlue') or hex-value: RRGGBB[AA]"
    
    if (positional_syntax and dump_colors):
        color_desc = textparser.add_argument_group(None) # exists to display color-info below grp_colors
        #color_desc_header = "colors are specified by name ('Red', 'AliceBlue') or hex-value: RRGGBB[AA]"
        from textwrap import dedent as textwrap_dedent
        color_desc.description = textwrap_dedent("""\
          <color> may be specified as hex-value (RRGGBB[AA])
                   or by name: ('Red', 'Green', 'AliceBlue')
         ____________________________________________________
        | colormap entries (builtin names)                   |
        |____________________________________________________|
        |_<name>________________________________<RRGGBB[AA]>_|
        |____________________________________________________|"""
        ) + (colorlist_linesep := ' \n| ');
        color_desc.description += FormatColorList(MAGICK_COLORMAP,
          linesep=colorlist_linesep, ends=(' #', f"[FF]  |"), extra_width=16
        ) + "\n|____________________________________________________|\n"
    
    # "default=SUPPRESS" is necessary when both positional/keyword forms exist; otherwise the positional forces its value to None
    if (positional_syntax):
        textparser.add_argument('basename', default=argparse.SUPPRESS, metavar='output_name', nargs='?');
        textparser.add_argument('--filename', dest="basename", metavar='<output_name>')
    
    # reformatting the usage (compensating for the formatting-manipulation performed earlier (metavar value))
    textparser.usage = textparser.format_usage().removeprefix('usage: ').replace(
        "--fontsize --pointsize", "--fontsize <int> | --pointsize", 1).replace(
        "--letter-spacing --kerning", "--kerning <int> | --letter-spacing", 1
    ) + '\n';
    return textparser


# description of indirect RenderText invocations (invoked as subcommand, rather than primary module)
SubparserInvocationSyntaxDescription = """\
 _________________________________________________________________________________________________________________________
|                                                                                                                         |
| RenderText-specific arguments (passed to subparser)                                                                     |
|_________________________________________________________________________________________________________________________|
|                                                                                                                         |
| RenderText has slightly different syntax when invoked as a subcommand (as it is here), opposed to a direct invocation   |
| these arguments may only be specified in conjunction with '--rendertext', and are entirely optional                     |
|_________________________________________________________________________________________________________________________|
|-------------------------------------------------------------------------------------------------------------------------|
| [--font FONT] [--fontsize <int> | --pointsize <int> | --autosize]                                                       |
|-------------------------------------------------------------------------------------------------------------------------|
|  --font FONT                      available fonts: 'DejaVuSans', 'DejaVuSansMono', 'DejaVuSerif' (default: DejaVuSerif) |
|  --fontsize --pointsize <int>     pointsize (default: 144)                                                              |
|  --autosize                       scale text to match the source-image width (default: False)                           |
|                                                                                                                         |
| When '--autosize' is specified, the 'fontsize' and 'pointsize' arguments will have no effect;                           |
|   dimensions will be determined by the longest line's width - scaled proportionally to fit the image-width              |
| By default, the dimensions are set according to pointsize, and lines exceeding the image-width are clipped              |
|                                                                                                                         |
|-------------------------------------------------------------------------------------------------------------------------|
| [--letter-spacing <int> ] [--word-spacing <int>] [--line-spacing <int>]                                                 |
|-------------------------------------------------------------------------------------------------------------------------|
| spacing arguments accept positive and negative integers (negative values condense text instead)                         |
|  --letter-spacing --kerning <int>  spacing between letters                                                              |
|  --word-spacing <int>              spacing between words                                                                |
|  --line-spacing <int>              spacing between lines                                                                |
|                                                                                                                         |
|-------------------------------------------------------------------------------------------------------------------------|
| [--textcolor <color>]                                                                                                   |
|-------------------------------------------------------------------------------------------------------------------------|
|  --textcolor <color>               specify by name ('Red', 'AliceBlue') or hex-value: RRGGBB[AA] (default: 'RED')       |
|    alpha-channel value is interpreted according to ImageMagick convention: [(transparent) 0x00 --> 0xFF (opaque)]       |
|    RenderText help lists all recognized color-names and their hex-values: 'RenderText.py --help'                        |
|_________________________________________________________________________________________________________________________|
"""



def ParseCmdline(arglist:list[str]|None = None, positional_syntax:bool=False):
    textparser = CreateParser(positional_syntax)
    (parsed_args, unparsed) = textparser.parse_known_intermixed_args(arglist)
    
    RTparameters = TextRenderParams (
        m_string = parsed_args.text,
        fontname = parsed_args.font,
        fontsize = parsed_args.fontsize,
        autosize = parsed_args.autosize,
        imgWidth = parsed_args.imgWidth,
        color_fg = parsed_args.fg if positional_syntax else parsed_args.textcolor,
        color_bg = parsed_args.bg if positional_syntax else None,
        basename = parsed_args.basename if positional_syntax else None,
        spacingK = parsed_args.kerning,
        spacingW = parsed_args.word_spacing,
        spacingL = parsed_args.line_spacing,
    )
    
    # when this script is run as main program, all arguments should be recognized
    if (positional_syntax and (len(unparsed) > 0)):
        raise SyntaxError(f"unrecognized arguments: {unparsed}");
    return (RTparameters, (parsed_args, unparsed));

