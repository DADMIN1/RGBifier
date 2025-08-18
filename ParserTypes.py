# utility functions and type definitions refactored out of CLI
import pathlib
import argparse


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str) -> str:
    if text.isalnum(): return text
    ok_chars = {'_'}
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


def PrintDict(D:dict, name = None):
    if name is not None: print("{} = ".format(name)+'{');
    for (k,v) in D.items(): print(f"  {k}: {repr(v)}, ");
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



class CustomFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    """ custom formatter_class inheriting both 'DefaultsHelp-' and 'RawText-' HelpFormatters \n
        allows newlines within help-text and automatically appends info about default values \n
    suppresses indentation for description-text assigned to untitled (None) argument-groups """
    def __init__(self, prog):
      super().__init__(prog, indent_increment=2, max_help_position=32, width=70)
      self._indentation=True
#  ____________________________________________________________________________________________________
# | these overrides manipulate indentation during formatting, targeting 'ArgumentParser.format_help()' |
# | specifically, the function calls within the action-group formatting loop [argparse.py @line: 2622] |
# |____________________________________________________________________________________________________|
    def start_section(self, heading):
        self._indentation = heading is not None
        if (self._indentation): self._indent();
        section = self._Section(self, self._current_section, heading)
        self._add_item(section.format_help, [])
        self._current_section = section
    
    def end_section(self):
        self._current_section = self._current_section.parent
        if (self._indentation): self._dedent();
        self._indentation = True
    
    def _format_text_alt(self, text):
        if('%(prog)' in text): text = (text % dict(prog = self._prog));
        return self._fill_text(text, max(self._width, 11), '') + '\n\n'
    
    def add_text(self, text):
        if (text is argparse.SUPPRESS) or (text is None): return;
        if self._indentation: return self._add_item(self._format_text, [text]);
        self._add_item(self._format_text_alt, [text]);
# |____________________________________________________________________________________________________|

# CustomFormatter cannot inherit 'MetavarType' helpformatter:
# argparse.MetavarTypeHelpFormatter (default metavar = type) always fails with this error:
# "AttributeError: 'NoneType' object has no attribute '__name__'. Did you mean: '__ne__'?"
# seemingly triggered by any option without a 'type' specified (like any transform option)



def ASSERT_(*, debug_mode:bool):
    # TODO: print condition's source-code in debug_mode (especially on failure)
    def _ASSERT(condition:bool, errmsg:str, *, print_status=debug_mode):
        _print = ((lambda S: print(S)) if print_status else (lambda _: None))
        if condition: return lambda: _print("[ASSERTION PASSED]");
        if (not condition) and debug_mode: return lambda: _print(f"[ASSERTION FAILED] {errmsg}");
        raise AssertionError(errmsg)
    return lambda condition, errmsg: _ASSERT(condition, errmsg)()

ASSERT = ASSERT_(debug_mode=False)
def SETDEBUGMODE(debug_mode: bool):
    global ASSERT; ASSERT = ASSERT_(debug_mode=debug_mode);


# GraphicsMagick - alpha '00'->opaque, 'FF'->transparent; default alpha is opaque
def StrHexGM(num:str): return "0x{:08X}".format(int(f"{num}{'0'*(8-len(num.removeprefix('0x')))}",16));
def StrHexIM(num:str): # ImageMagick - alpha '00'->transparent, 'FF'->opaque
    count = len(num.removeprefix('0x')); alphaLength = max(8-count, 0)
    FL = min(alphaLength, 2); alpha = ('0' * max((alphaLength-FL), 0))+('F' * FL)
    return f"0x{hex(int(num, 16)).removeprefix('0x').upper().zfill(count)}{alpha}"

# Alpha: [opaque -> transparent] || ImageMagick: [FF -> 00] || GraphicsMagick: [00 -> FF]
    # IM: [(opaque) 0xFF -> 0x00 (transparent)]
    # GM: [(opaque) 0x00 -> 0xFF (transparent)]
    # IM: [0xFF -> 0x00] | GM: [0x00 -> 0xFF]


def SplitHex(num:str): return '|'.join([num[I:I+2] for I in range(0,len(num),2)]);

def StrHex(num:str):
    IN = num.removeprefix('0x')
    if ((badlen := len(IN)) > 8): # too long
        print(f"[ERROR] Too many digits ({badlen}) in hex-value: {num} ({badlen-8} extra)")
        print(f"\t{IN[:8]}|{IN[8:]}")
        print(f"\tRRGGBBAA|{'^'*(badlen-8)}\n")
    elif ((badlen % 2) != 0): # odd number of digits
        RGB="RRGGBBAA"; padding = ' ' * ((padlen := (8 - badlen)) + (padlen//2));
        print(f"[WARNING] uneven digit total in in hex-value: {num} ({badlen})");
        print(f"\t{SplitHex(IN)}[_]{padding}", end='    '); print(f"[_]{IN[0]}|{SplitHex(IN[1:])}{padding}");
        print(f"\t{SplitHex((RGB[:badlen]))}[{RGB[badlen]}]|{SplitHex(RGB[badlen+1:])}".removesuffix('|'), end='     ')
        print(f"[{RGB[0]}]R{SplitHex(RGB)[2:]}\n")
    values = (StrHexIM(num), StrHexGM(num)); # need both until we know which library
    ASSERT(all([(len(color.removeprefix('0x')) <= 8) for color in values]), "TOO MANY DIGITS!!!");
    return values


def MaybePercent(num:str):
    num = int(float(num) * 100) if ('.' in num) else int(num.removesuffix('%'))
    if ((num < 0) or (num > 100)): raise ValueError(f"invalid percent: {num}%");
    return num


# returns offset values, and the formatted string representation (for use in magick commands)
def ParsedOffset(offset_str: str) -> tuple[tuple[int,int], str]:
    """ returns parsed offset-values and their formatted string representation """
    if (len(offset_str) == 0): return ((0, 0) , "+0+0");
    
    # plus/minus-signs interfere with 'isdigit/isdecimal' checks
    # need to preserve value before stripping/splitting them out
    index = -1
    signs = {(index, C) for C in ('+', '-') for _ in range(2) if ((index := offset_str.find(C, index+1)) != -1)}
    if (len(signs) > 2): raise Exception(f"offset argument has too many plus/minus-signs: '{offset_str}' ({len(signs)})");
    
    XY = [*[N for N in offset_str.replace('+',' ', 2).replace('-',' ', 2).split(' ',maxsplit=2) if (N != '')]]
    if (not all([number.isdigit() for number in XY])): raise Exception(f"[ERROR] non-digit in offsets: {XY}");
    
    # integer conversion and re-applying signs
    XY = [*[int(N) for N in XY], *[0 for _ in range(2-len(XY))]]; assert(len(XY) == 2);
    ordered_signs = [pair[1] for pair in sorted(signs, key=lambda pair: pair[0])] # in order of appearance
    for (I, sign) in zip(range(2-len(ordered_signs), 2), ordered_signs): XY[I] *= (-1 if (sign == '-') else 1);
    # this range statement ^ cannot be replaced with 'enumerate' - when offset_str only contains one sign, it belongs to the last offset
    return (tuple(XY), "{:+d}{:+d}".format(*XY))


# width and height may be returned as strings if they're specified as percents
def ParsedCrop(cropstr: str|None) -> tuple[int|str,int|str,int,int]|None:
    valid_chars = "0123456789%x+-"
    if ((cropstr is None) or (len(cropstr.strip()) == 0)): return None;
    if not all([char in valid_chars for char in cropstr]):
        print(f"[ERROR] invalid crop value: '{cropstr}'"); return None;
    
    # plus/minus-signs interfere with 'isdigit/isdecimal' checks
    # need to preserve value before stripping/splitting them out
    index = -1
    signs = {(index, C) for C in ('+','-') for _ in range(2) if ((index := cropstr.find(C, index+1)) != -1)}
    if (len(signs) > 2): raise Exception(f"crop has too many plus/minus-signs: '{cropstr}' ({len(signs)})");
    
    # replacing offset only
    #sign_offsets = [(I if ((I := cropstr.find(sign)) != -1) else None) for sign in '+-']
    
    # divider between size and offsets
    midpoint = (min([I for (I,_) in signs]) if (len(signs) > 0) else len(cropstr))
    size_str = cropstr[:midpoint]
    remaindr = cropstr[midpoint:]
    
    (W,ch,H) = ((S if (S != '') else None) for S in size_str.partition('x'))
    # if only one size was given with an 'x', the other defaults 0 (image-size)
    # if only one size was given, with no 'x', it applies to both
    #    empty: [    +X+Y] -> [size: 0x0] (default size of image)
    #   single: [  96+X+Y] -> [size: 96x96]
    #   suffix: [640x+X+Y] -> [size: 640x0] (set width, default height)
    #   prefix: [x480+X+Y] -> [size: 0x480] (set height, default width)
    if all(((S is None) or (S == 'x')) for S in (W,ch,H)): (W,H) = ('0','0'); # no size specified at all
    elif (ch == 'x'): (W, H) = (('0' if W is None else W), ('0' if H is None else H)); # defaults if 'x' was present
    elif (ch is None): (W, H) = ((H if W is None else W), (W if H is None else H)); # without 'x', set both axes
    
    # both parts should be set by this point
    if ((W is None) or (H is None)): raise Exception(f"failed to parse crop-size: '{size_str}'");
    
    # percentages
    if any(percentage_check := [D.endswith('%') for D in (W, H)]):
        (W, H) = [(N if (N := D.removesuffix('%')).isdigit() else None) for D in (W, H)]
        if (None in (W, H)): raise Exception(f"invalid percentage in crop-size: '{size_str}'");
        if not all((N.isdigit() if not B else ((int(N) > 0)) and (int(N) <= 100)) for (B,N) in zip(percentage_check, (W,H))):
            raise Exception(f"percentage values out of range: ({W}x{H}); (valid range: [1-100])")
    
    # TODO: handle tile-cropping ('@' suffix): https://usage.imagemagick.org/crop/#crop_equal
    
    segments = [W, H, *[S for S in remaindr.replace('+',' ',2).replace('-',' ',2).split(' ',maxsplit=2) if (S != '')]]
    if not all([segment.isdigit() for segment in segments]): raise Exception(f"[ERROR] non-digit in crop: {segments}");
    
    # integer conversion and re-applying signs
    crop = [*[int(segment) for segment in segments], *[0 for _ in range(4-len(segments))]]; assert(len(crop) == 4);
    ordered_signs = [pair[1] for pair in sorted(signs, key=lambda pair: pair[0])] # in order of appearance
    for (I, sign) in zip(range(4-len(ordered_signs),4), ordered_signs): crop[I] *= (-1 if (sign == '-') else 1);
    
    (W, H, X, Y) = crop
    if ((W, H, X, Y) == (0, 0, 0, 0)): return None;
    if not (all((I >= 0) for I in (W,H))): raise Exception(f"[ERROR] crop-size must not be negative: ({W}x{H})");
    (W, H) = [(f"{N}%" if B else N) for (B,N) in zip(percentage_check, (W,H))] # re-applying percents
    
    return (W,H,X,Y)



def ParseCropFuzzing():
    """tests 'ParseCrop()' with a bunch of random inputs"""
    croptests = [
        "640x480+64+128",
        "640x480-64-128",
        "640x480+64-128",
        "640x480-64+128",
        "640x480",
        "640x480+64",
        "640x480+0+128",
        "640x480+0-128",
        "640x",
        "x480",
        # percentages
        "50%",
        "360x75%",
        "x25%+3-4",
        "25%x+3-4",
        "15%x240+1+2",
        "50%x75%",
        "75%+120+240",
        # these should all return empty strings
        "0x0+0+0",
        "0","0-0+0",
        "0x0","x0","0x",
        "+0+0","-0-0",
        "", None,
    ]
    # these are expected to throw an exception
    croptests_badstr = [
        "640x480+64+128+123",
        " ", '-',
        "x+-",
        "-+x",
        "-x+",
        "+x-",
        "1 2 3 4",
        "1-2+3-4",
        "1x2x3x4",
        "xx480"
        "-64+128",
        "x-6+1",
        "+111-222+640x480",
        "+640x+480",
        "999%",
        "50%75%",
        "-10%",
        "0x0%+0+0",
        "0%x+0",
        "640x480+10%+10%",
    ]
    
    croptest_results = [(T, ParsedCrop(T)) for T in croptests]
    bad_strs_results = []
    for bad_str in croptests_badstr:
        try: bad_strs_results.append((bad_str, ParsedCrop(bad_str)));
        except Exception as E: bad_strs_results.append((bad_str, E));
    
    print(croptest_results)
    print(bad_strs_results)
    return (croptest_results, bad_strs_results)
