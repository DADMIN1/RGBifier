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


# custom formatter_class combining the behavior of two arparse formatters
# allows newlines within help-text and automatically appends info about default value
class CustomFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self, prog): super().__init__(prog, indent_increment=2, max_help_position=32, width=70);

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
