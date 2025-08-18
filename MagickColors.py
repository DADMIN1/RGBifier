import json
import Config
from sys import stderr as STDERR


class BetterJSONDecoder(json.JSONDecoder):
    """ decodes json without unnecessary exception-spamming nonsense """
    debug_mode = False
    def __init__(self): super().__init__();
    def debug(self, index: int, text: str):
        print(f"  [JSON_DEBUG][{index:3d}]: {text}", file=STDERR);
    # enabling debug_mode causes the decoder to report any invalid/incomplete data encountered during parsing
    # normally, those tokens would be silently ignored (likely comment lines or fragments of the file-header)
    
    def decode(self, s, _w = ...):
        # _w is undocumented....
        _loaded_data = None
        _final_index = -1; last_index = 0;
        _ignored_exceptions = []
        
        # when an invalid line/comment contains characters that would be valid json values,
        # the decoder returns those individual values; ignore incomplete data of that sort.
        # for example, decoding this line: //'identify-im6.q16 -list color' returns: "6" "16" (seperate lines)
        # if it was double-quoted instead, the entire line would be returned (single-quotes are invalid json.)
        
        while ((last_index < len(s)) and 
               (last_index > _final_index)):
            try:
                _final_index = last_index
                (decoded_data, last_index) = super().raw_decode(s, last_index)
                if isinstance(decoded_data, dict):
                    _loaded_data = (decoded_data if (_loaded_data is None)
                                    else {**_loaded_data, **decoded_data})
                elif self.debug_mode: self.debug(last_index,decoded_data);
            except json.JSONDecodeError as ERROR:
                last_index = ERROR.pos+1
                if (ERROR.msg.startswith("Expecting value")):
                    _ignored_exceptions.append(ERROR);
                else: raise(ERROR);
        
        if (_loaded_data is None) and (len(_ignored_exceptions) > 0):
            print(f"decoding failed [last_index = {last_index}]: {_ignored_exceptions}", file=STDERR)
        if (self.debug_mode): print('',flush=True, file=STDERR);
        return _loaded_data


def FormatColorList(
        colormap: dict, asHex=True, hexpfx=False, letterpfx=None,
        seperator=None, linesep='\n', ends=('',''), extra_width=1
    ):
    """
    :param colormap: colormap
    :param asHex: display values in hexadecimal
    :param hexpfx: prefix values with '0x' (only if asHex is True)
    :param letterpfx: add 'R/G/B' label to each component if True.
        If letterpfx is a string, it is also appended to the label
    :param seperator: inserted between each component (RGB)
    :param linesep: appended to each line
    :param ends: chars enclosing all displayed values on each line
    :param extra_width: additional space after color-name
    :return: formatted color list
    """
    sample = [*colormap.values()][0];
    assert(isinstance(sample, dict));
    assert('srgb' in sample.keys());
    assert(extra_width >= 0);
    
    longest_key = max([len(K) for K in colormap.keys()]) + extra_width;
    def Kpad(K:str): return ' ' * (longest_key - len(K));
    
    if (seperator is None): seperator = '';
    if (len(seperator)==0):
        if letterpfx: seperator = ' ';
        if not asHex: seperator = ' ';
    
    # suppress per-component hex-prefix when displaying a single (6-digit) hex-value
    one_hex = ((len(seperator) == 0) and (hexpfx is True))
    Z = ('0x' if (asHex and hexpfx and (one_hex is False)) else '')
    L = letterpfx if (letterpfx and isinstance(letterpfx, str)) else ''
    NumFormatter = (
        (lambda n: L+Z+hex(n).removeprefix('0x').upper().zfill(2)) if asHex else
        (lambda n: L + str(n).zfill(3))
    )
    
    def RGB_Formatter(srgb: list):
        _rgb = seperator.join([ NumFormatter(N) if not letterpfx else
            f"{C}:{NumFormatter(N)}" for (C, N) in zip('RGB', srgb)])
        return f"{ends[0]}{(('0x' if one_hex else '')+_rgb)}{ends[1]}"
    
    formatted_color_list = [
        f"{K}{Kpad(K)} {RGB_Formatter(V['srgb'])}"
        for (K,V) in colormap.items()
    ]
    return linesep.join(formatted_color_list)


def LoadMagickColors():
    print("Checking colormap directory...")
    Config.Init(); assert(Config.CONFIG_DIR.exists()), "config-dir expected after init";
    (ColormapDirectory := (Config.CONFIG_DIR / "MagickColorMaps")).mkdir(exist_ok=True);
    colormap_filepaths = [ColormapDirectory /f"colormap_{M}.json" for M in ["IM", "GM"]]
    
    Mstack = ["IM", "GM"]
    MAGICK_COLORMAPS = {}
    for existing_map in [(M if M.exists() else None) for M in colormap_filepaths]:
        if (existing_map is None): MAGICK_COLORMAPS[Mstack.pop(0)]=None; continue;
        print(f"loading {existing_map.relative_to(Config.CONFIG_DIR)}...",end=' ')
        with existing_map.open(mode='r', encoding="utf-8") as existing_file:
            loaded_json = json.load(existing_file, cls=BetterJSONDecoder)
            line_ending = ('\n' if(BetterJSONDecoder.debug_mode) else '')
            print(f"success! [{len(loaded_json)} colors]{line_ending}")
            MAGICK_COLORMAPS[Mstack.pop(0)] = loaded_json
            # json.dumps(loaded_json) # for some reason this can't print the loaded data
            # print(loaded_json) # prints fine
            # print('\n')
    
    success_count = len([V for V in MAGICK_COLORMAPS.values() if V is not None])
    if(success_count == 0): print("failed to load all colormaps"); return None;
    print(f"colormaps loaded: {success_count}\n")
    return MAGICK_COLORMAPS


# custom color names can be added to config files: colors.xml/colors.mgk
def DumpMagickColors(allowed_compliance: str, disallow_numbered = True):
    """ Queries Magick libraries for color names, then parses, filters, and saves the results under 'MagickColorMaps'
    
    compliance:
    'SVG' avoids numbered variants (blue1, blue2, blue3, etc)
    'XPM' is basically a subset of 'X11', and 'X11' includes nearly everything
    
    :parameter allowed_compliance: one of: "SVG" "X11" "XPM" "ALL", or any space-seperated combination thereof
    :parameter disallow_numbered: exclude names suffixed with a number (blue1, blue2, blue3, etc.)
    :return: Magick Colormaps """
    
    import subprocess
    from copy import deepcopy
    from typing import Callable
    
    _valid_compliance = {"SVG", "X11", "XPM", "ALL"}
    # TODO: how is compliance listed for custom definitions?
    
    if ("ALL" in allowed_compliance.upper()): allowed_compliance = ["SVG","X11","XPM"];
    else: allowed_compliance = [S.upper() for S in allowed_compliance.split()];
    if (not all([CPL in _valid_compliance for CPL in allowed_compliance])):
        print("[ERROR] invalid compliance: {}".format(allowed_compliance));
        raise ValueError(f"allowed values are: {_valid_compliance}");
    
    print("Checking colormap directory...")
    Config.Init(); assert(Config.CONFIG_DIR.exists()), "config-dir expected after init";
    (ColormapDirectory := (Config.CONFIG_DIR / "MagickColorMaps")).mkdir(exist_ok=True);
    colormap_filepaths = [ColormapDirectory /f"colormap_{M}.json" for M in ["IM", "GM"]]
    
    # backing up any existing colormap dumps
    for existing_map in [M for M in colormap_filepaths if M.exists()]:
        existing_map.rename(ColormapDirectory / f"{existing_map.stem}.backup.json")
        print(f"created backup of existing colormap: {existing_map}")
    print("\n")
    
    
    def ColorParsingLambda_IM(stdout_lines: list[str]):
        return{ M["name"]: { "srgb": M["srgb"], "comp": M["comp"] }
            for M in [*filter(lambda M:(
                any([comp in M["comp"] for comp in allowed_compliance])
                and((not M["name"][-1].isdigit()) if disallow_numbered else True)),
                [{  "name": C[0],         # reformatting "srgb(1,2,3)" --> [1 2 3]
                    "srgb": [*map(int, C[1].removeprefix('srgb').strip("()").split(','))],
                    "comp": C[2:]} for C in [
                    (line.split()) for line in stdout_lines
                    if (line.split()[1].startswith("srgb"))
                ]] #IM: column2 (color) startswith "srgb" ^
            )]
        };
    
    def ColorParsingLambda_GM(stdout_lines: list[str]):
        return{ M["name"]: { "srgb": M["srgb"], "comp": M["comp"] }
            for M in [*filter(lambda M:(
                any([comp in M["comp"] for comp in allowed_compliance])
                and((not M["name"][-1].isdigit()) if disallow_numbered else True)),
                [{  "name": splitline[0],  # reformatting "1, 2, 3" --> [1 2 3]
                    "srgb": [*map(int,[N.strip(', ') for N in splitline[1:4]])],
                    "comp": splitline[4:], } for splitline in [
                      (line.split()) for line in stdout_lines
                    if(line.split()[1].strip(', ').isdigit()) # column2 should be color's first digit
                ]] # just ignoring any names containing space
            )]
        };
    
    def GetVersion(command_string:str):
        completed = subprocess.run([*command_string.split()], check=True, capture_output=True, encoding="utf-8")
        firstline = completed.stdout.splitlines()[0]
        magickver = firstline.split('http')[0] # <-- link to website immediately after version info
        return magickver.removeprefix("Version:").strip() # prepended by IM, but we also prepend it later (in the header)
    
    def DumpColors(command_string:str, parse_lambda: Callable):
        print(f"\nrunning command: '{command_string}'")
        completed = subprocess.run([*command_string.split()], check=True, capture_output=True, encoding="utf-8")
        stdout_lines = completed.stdout.splitlines()
        
        while (len(stdout_lines) > 0): # skip lines until table-header is found
            if (stdout_lines.pop(0) == ('-' * 79)): break;
        # TODO: is the number of dashes actually constant?
        assert(len(stdout_lines) > 0), "did not find table header in captured stdout";
        
        print(f"parsing {len(stdout_lines)} lines...", end=' ')
        parsed_colormap = parse_lambda(stdout_lines)
        print(f" done! [{len(parsed_colormap)} colors]")
        return parsed_colormap
    
    
    MAGICK_COLORMAPS = {
        "IM": {
            "map_filepath": colormap_filepaths[0],
            "parse_lambda": ColorParsingLambda_IM,
            "list_command": "identify-im6.q16 -list color",
            "versionQuery": "identify-im6.q16 -version",
            "colormapData": None,
        },
        "GM": {
            "map_filepath": colormap_filepaths[1],
            "parse_lambda": ColorParsingLambda_GM,
            "list_command": "gm convert -list color",
            "versionQuery": "gm version",
            "colormapData": None,
        },
    }
    
    for (ML, MAP) in MAGICK_COLORMAPS.items():
        versionString = GetVersion(MAP["versionQuery"])
        colormap_dump = DumpColors(MAP["list_command"], MAP["parse_lambda"])
        MAP["colormapData"] = deepcopy(colormap_dump)
        map_filepath = MAP['map_filepath']
        
        print(f"saving colormap: {map_filepath.relative_to(Config.CONFIG_DIR)}...")
        with map_filepath.open(mode='w', encoding="utf-8") as dumpfile:
            dumpfile.writelines(colormap_header := [
                f'# {("ImageMagick" if(ML == "IM") else "GraphicsMagick")} Color Map\n'
                f'# version: "{versionString}"\n'
                f'# command: "{MAP['list_command']}"\n',
                f'# compliance: {allowed_compliance}\n',
                f"# numbered variants: {'dis' if (disallow_numbered) else ''}allowed\n"
            ]); print(f"{'_'*48}\n{''.join(colormap_header)}{'_'*48}");
            
            spaces = 2
            indentations = [f"{' '*(spaces*lvl)}" for lvl in range(2,4)] # penultimate and last-level indentation
            json_text = json.dumps(colormap_dump, indent=spaces, separators=(',', ': '))
            json_text = json_text.replace(f'\n{indentations[-1]}', '') # removing newlines from last-level values
            json_text = json_text.replace(f'\n{indentations[0]}]',']') # closing braces are left at lower indentation
            dumpfile.write(json_text); #print(json_text);
            print(f"done writing: {map_filepath.relative_to(ColormapDirectory)}\n")
    
    print("finished writing colormap dumps\n")
    return {K:V["colormapData"] for (K,V) in MAGICK_COLORMAPS.items()}


if __name__ == "__main__":
    # BetterJSONDecoder.debug_mode = True
    created_new = False
    loaded_maps = LoadMagickColors()
    if (loaded_maps is None):
        loaded_maps = DumpMagickColors("ALL")
        created_new = True
    
    def PrintMaps():
        spaces = 4
        indentations = [f"{' '*(spaces*lvl)}" for lvl in range(3,5)] # nesting one level deeper (maps are combined)
        json_text = json.dumps(loaded_maps, indent=spaces, separators=(',', ': '))
        json_text = json_text.replace(f'\n{indentations[-1]}', '') # removing newlines from last-level values
        json_text = json_text.replace(f'\n{indentations[0]}]',']') # closing braces are left at lower indentation
        print(json_text)
    if created_new: PrintMaps();
    
    # the main difference between IM/GM colormaps is that IM includes both spellings of 'gray' / 'grey'
    #colorList = FormatColorList(loaded_maps["IM"], linesep='\n  ')
    #print(f"\nbuiltin color names:\n  {colorList}\n")
    
    import textwrap
    formatted_colorlist = textwrap.dedent("""\
       _____________________________________________________
      | colormap entries (builtin names)                    |
      |_____________________________________________________|\
    """) + (colorlist_linesep := '\n| ');
    formatted_colorlist += FormatColorList(loaded_maps["IM"], linesep = colorlist_linesep,
      letterpfx='[', seperator='] ', ends=('','] |'), asHex=True, hexpfx=True, extra_width=4)
    
    print(formatted_colorlist)
    print("|_____________________________________________________|\n")
