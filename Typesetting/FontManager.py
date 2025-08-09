import pathlib


FONTS_DIR = pathlib.Path(__file__).parent/"Fonts"; assert(FONTS_DIR.is_dir()), "missing fonts directory";
FONTFILES = [*FONTS_DIR.glob("*/*")]
DEFAULT_FONT = "DejaVuSerif"


def FindFont(name:str|None) -> pathlib.Path:
    """ matches files under the 'Fonts' directory by name (ignoring file-extension) """
    if(name is None): name = DEFAULT_FONT;
    if ('.' in name): name = name.rsplit('.', maxsplit=1)[0];
    if ('/' in name): name = name.rsplit('/', maxsplit=1)[1]; print("[ERROR] name given to FindFont contains a path-seperator");
    matches = [font for font in FONTFILES if (font.stem.lower() == name.lower())]
    if (len(matches) >= 2): print(f"[FindFont] multiple fonts matching '{name}': {matches}");
    if (len(matches) == 0): raise FileNotFoundError(f"0 fonts matching '{name}'");
    return matches[0];

