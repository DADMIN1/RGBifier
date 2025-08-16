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



def CreateParser(positional_syntax:bool) -> argparse.ArgumentParser:
    textparser = argparse.ArgumentParser(allow_abbrev=False, formatter_class=CustomFormatter)
    if (positional_syntax): textparser.add_argument('text');
    else: textparser.add_argument('--text', required=True);
    
    availfonts = { font.stem for font in FontManager.FONTFILES }
    textparser.add_argument('--font', type=FontManager.FindFont, default=FontManager.DEFAULT_FONT, help=f"available fonts: {availfonts}")
    
    group_sizing = textparser.add_argument_group("sizing options")
    sizing_group = group_sizing.add_mutually_exclusive_group()
    sizing_group.add_argument('--fontsize', type=int, default=144)
    sizing_group.add_argument('--autosize', action="store_true", help="scale text to always match base image width")
    sizing_group.add_argument('--imgWidth', type=int, help="automatically adjust font-size to fit the text to this width")
    
    spacing_args = textparser.add_argument_group("spacing options")
    spacing_args.description = "all arguments accept positive and negative integers (negative values condense text instead)"
    spacing_args.add_argument('--kerning', type=int, help="alias for letter-spacing")
    spacing_args.add_argument('--letter-spacing', dest='kerning', help="spacing between letters")
    spacing_args.add_argument('--word-spacing', type=int, help="spacing between words")
    spacing_args.add_argument('--line-spacing', type=int, help="spacing between lines")
    
    # IM includes both spellings for gray/grey
    MAGICK_COLORMAP = LoadMagickColors()["IM"]
    knownColorNames = FormatList(*MAGICK_COLORMAP.keys())
    def ColorLookup(color):
        if color in knownColorNames: return color; # no translation necessary
        return f"'#{StrHex(color)[0].removeprefix('0x')}'" # always IM syntax
    
    grp_colors = textparser.add_argument_group("coloring options") # StrHex | colorname
    grp_colors.description = "colors are specified by name ('Red', 'AliceBlue') or hex-value: RRGGBB[AA]"
    if positional_syntax:
        grp_colors.add_argument('--fg', metavar='COLOR', type=ColorLookup)
        grp_colors.add_argument('--bg', metavar='COLOR', type=ColorLookup)
    else:
        grp_colors.add_argument('--textcolor', metavar='COLOR', type=ColorLookup, default='red')
        # default 'red' value when called from main CLI (black/white would not change otherwise)
    
    if positional_syntax:
        color_desc = textparser.add_argument_group("recognized color names") # exists to display color-info below grp_colors
        color_desc.description = FormatColorList(MAGICK_COLORMAP, seperator='|')
    
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
        color_fg = parsed_args.fg if positional_syntax else parsed_args.textcolor,
        color_bg = parsed_args.bg if positional_syntax else None,
        basename = parsed_args.basename,
        spacingK = parsed_args.kerning,
        spacingW = parsed_args.word_spacing,
        spacingL = parsed_args.line_spacing,
    )
    
    # when this script is run as main program, all arguments should be recognized
    if (positional_syntax and (len(unparsed) > 0)):
        raise SyntaxError(f"unrecognized arguments: {unparsed}");
    return (RTparameters, (parsed_args, unparsed));

