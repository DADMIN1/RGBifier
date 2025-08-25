from ctypes import *
import pathlib

library_path = pathlib.Path(__file__).parent / "libRGBmagick.so"
assert (library_path.exists()), "libRGBmagick not found!";

# can be pathlike
rgblib = CDLL(str(library_path.absolute()))
print(f"rgblib:{rgblib}\n{vars(rgblib)}\n")

#from RGBmagick.FFI import *
#import faulthandler

def PythonStrPlz():
    """ void PythonPlz(const wchar_t ezString[]) """
    pythonplz = rgblib["PythonPlz"]
    pythonplz.argtypes = [c_wchar_p]
    pythonplz.restype = None # void
    
    print(f"RGBmagick::PythonPlz: {pythonplz}")
    print(f"  arg_types: {pythonplz.argtypes}")
    print(f"  return_t: {pythonplz.restype}\n")
    
    plz_print = "Wide Hello String From FFI.py!!"
    widestring = create_unicode_buffer(plz_print)
    
    print(f"wstring: '{plz_print}' (len: {len(widestring)})")
    print(f"{repr(widestring)} [size: {sizeof(widestring)}]")
    
    print("invoking: libRGBmagick.so --> PythonPlz")
    pythonplz(widestring)
    print("PythonPlz() function-call has returned!")
    return


def EpicFunction():
    """ int EpicFunction(int argc, const char* argv[]) """
    epicfunction = rgblib["EpicFunction"]
    CharPointerPointer_T = POINTER(POINTER(c_char))
    # char** / char*[]; POINTER(c_char_p) does NOT work!!
    epicfunction.argtypes = [c_int, CharPointerPointer_T]
    
    print(f"RGBmagick::EpicFunction: {epicfunction}")
    print(f"     arg_types: {epicfunction.argtypes}")
    print(f"     return_t: {epicfunction.restype}\n") # c_int (default)
    
    argstring = b"Epic Hello String From FFI.py!!!"
    stringarr = [create_string_buffer(S) for S in argstring.split()]
    arrlength = int(len(stringarr))
    
    # thanks python this syntax is incredible
    stringarr_pointers = (POINTER(c_char)*arrlength)(*[cast(ss, POINTER(c_char)) for ss in stringarr])
    # (POINTER(c_char) * arrlength) <-- constructs an anonymous type-object (cstring-array with size==arrlength)
    #                                   yes you really are required to multiply the pointer-type (thanks python)
    # then the new type's constructor is immediately invoked, obtaining char* by casting string_buffer
    # Holding data in string_buffers and casting is required; c_char_p simply does not work (segfault)
    
    print(f"argstring: '{argstring}' (len: {len(argstring)})")
    print(f"char* arr: (length: {arrlength}) {[type(CT).__name__ for CT in stringarr]}")
    print(f"char** []: [size: {sizeof(stringarr_pointers)}] {repr(stringarr_pointers)}")
    print('')
    
    print("invoking: libRGBmagick.so --> EpicFunction()")
    retval = epicfunction(c_int(arrlength), stringarr_pointers)
    print(f"EpicFunction-call has returned! (value: {retval})")
    return retval


if __name__ == "__main__":
    div = [f"{'_'*150}\n", f"\n{'_'*150}"]
    print(f"{div[0]}PythonStrPlz{div[1]}"); PythonStrPlz();
    print(f"{div[0]}EpicFunction{div[1]}"); EpicFunction();
    print(f"{div[0]}done\n");
