import pathlib
import subprocess

from Typesetting.Subparser import (TextRenderParams, ParseCmdline)

# ImageMagick command - required for 'CheckFontMetrics' (GraphicsMagick doesn't report them) 
IM_CONVERTCMD = "convert-im6.q16"


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


def CheckFontMetrics(text:str, fontpath:pathlib.Path, pointsize:int, kerning:int|None):
    filtered_text = f'"{FilterText(text, allow_symbols=True)}"' # TODO: should exclude quotations
    kerning_string = ("" if (kerning is None) else f"-kerning {kerning}")
    command = f"{IM_CONVERTCMD} -debug annotate xc:none -font '{fontpath}' -pointsize {pointsize} {kerning_string} -draw 'text 0,0 {filtered_text}' null:"
    # 'null:' specifies empty output (while avoiding the usual error)
    # ImageMagick is required; GraphicsMagick cannot report font metrics
    
    completed = subprocess.run(command, shell=True, text=True, encoding="utf-8", capture_output=True)
    if (completed.returncode != 0): print(f"[ERROR] nonzero exit-status: {completed.returncode}\n");
    print(completed.stderr); print('\n');
    
    lines = [line.strip() for line in completed.stderr.splitlines()]; assert(len(lines) > 0);
    metrics_line = [line for line in lines if ('Metrics: ' in line)][-1] # debug info is always repeated 2-3x, for unknown reasons
    metrics = metrics_line.split('Metrics: ', maxsplit=1)[-1]
    metrics_dict = {
        K:V for (K,V) in [
            (pair.split(': ', maxsplit=1))
            for pair in metrics.split('; ')
        ]
    }
    # keys: [text width height ascent descent max advance bounds origin pixels-per-em underline position underline thickness]
    return metrics_dict


def BuildCommandline(P: TextRenderParams, output_directory=pathlib.Path("/tmp/RGB_TOPLEVEL/")):
    text      = P.m_string
    fontpath  = P.fontname # TODO: resolving font-paths should be done here instead of in parser?
    pointsize = P.fontsize
    kerning   = P.spacingK
    fg_color  = P.color_fg
    bg_color  = P.color_bg
    output_filename = P.basename
    
    filtered_text = FilterText(text, allow_symbols=True)
    metrics_dict = CheckFontMetrics(filtered_text, fontpath, pointsize, kerning)
    (width, height, Yoffset) = (metrics_dict["width"], metrics_dict["height"], metrics_dict["ascent"])
    # TODO: need to get adjusted image dimensions after "-trim +repage" (which don't affect 'CheckFontMetrics' output)
    
    def AbbrevColor(color:str):
        match color.upper():
            case 'BLUE': return 'U'; # 'B' is reserved for black
            case 'NONE': return '_'; # transparent
        return color.upper()[0]
    
    if (fg_color is None): fg_color = "white";
    if (bg_color is None): bg_color = "none"; # transparent background
    abbreviated_color_suffix = f"{AbbrevColor(fg_color)}{AbbrevColor(bg_color)}"
    
    spacings_str = (f"" if (kerning is None) else f"_{kerning}K")
    if not output_filename: output_filename = FilterText(text, False)[:32]; # limit automatic filename length to 32 chars
    else: output_filename = FilterText(output_filename); # allow whitespace in filename only when specified
    appending_string = f"-{fontpath.stem}_{pointsize}{spacings_str}_{width}x{height}+{Yoffset}_{abbreviated_color_suffix}.png"
    output_filename += appending_string
    # TODO: configuration of filename template
    
    quoted_text_str = f'text 0,{Yoffset} "{filtered_text}"'
    # the order of nested quotations here is critical: double-quote INNER text, single-quotes OUTSIDE!
    # using the incorrect quotation-order makes it impossible to write text containing punctuation (!)
    
    assert(output_directory.exists() and output_directory.is_dir());
    output_filepath = output_directory / output_filename
    
    # 'gm convert' also works here
    command = f"{IM_CONVERTCMD} -size {width}x{height} "
    command += f"xc:{bg_color} "
    command += f"-font '{fontpath}' -pointsize {pointsize} "
    command += ("" if (kerning is None) else f"-kerning {kerning} ")
    command += f"-fill {fg_color} -draw '{quoted_text_str}' " # reminder that single-quotes, not-double, are mandatory here
    command += "-trim +repage " # aggressively crop to text, remove old virtual-canvas size
    command += f"'{output_filepath}'"
    return (command, output_filepath)


def DoEverything():
    (RTparameters, (parsed_args, unparsed)) = ParseCmdline(positional_syntax=True)
    (text_command, output_filepath) = BuildCommandline(RTparameters)
    print(text_command); print('\n');
    subprocess.run(text_command, shell=True, text=True, encoding="utf-8")
    print(f"\n{output_filepath}");
    return output_filepath


if __name__ == "__main__":
    DoEverything()
    print("\ndone\n")
    
