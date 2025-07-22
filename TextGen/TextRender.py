# given a string and a font, constructs an imagemagick command that renders the text to a color image
# the constructed command uses 'imagemagick' as a placeholder for the IM-convert program.
# alias imagemagick="convert-im6.q16"

letters = [(chr(C),chr(C).upper()) for C in range(ord('a'),ord('z')+1)]
alphabets = ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
digit_str = ''.join(digits)

punctuation = [ chr(C) for C in [
    *range(0x21, 0x30),
    *range(0x3A, 0x41),
    *range(0x5B, 0x61),
    *range(0x7B, 0x7F),
]]

punctuation_str = ''.join(punctuation)


def CalcFontsizes(pointsize:int, numchars:int):
    img_width = ((pointsize//2)*numchars)
    img_height = int(pointsize/1.125)
    #img_size = f"{img_width}x{img_height}"
    #Yoffset = (pointsize/1.125)
    Yoffset = ((pointsize*3)//4)
    return (img_width, img_height, Yoffset)


def CalcFontsizesFloat(pointsize:int, numchars:int):
    img_width = ((pointsize/2)*numchars)
    img_height = (pointsize/1.125)
    Yoffset = (pointsize*0.75)
    return (img_width, img_height, Yoffset)


def CalcFsz(pointsize:int, numchars=26, precision=3):
    results = [CalcFontsizes(pointsize,numchars), CalcFontsizesFloat(pointsize,numchars)]
    print(f"pointsize: {pointsize}")
    for (w,h,y) in results:
        (w,h,y) = (N if isinstance(N,int) else f"{N:.{precision}f}" for N in (w,h,y))
        print(f" [{w} x {h}] +{y}")
    print("")
    return results


# -------------------------------------------------------------------------------------- #
good_base_sizes = [
    [(2**ex), (2**ex) * 1.125]
    for ex in range(4,9)
]

pszs = [int(B[1]) for B in good_base_sizes]



# better generation for powers of 2
pwrs_of_two = [(2**ex) for ex in range(3,9)]

# takes each base-value power of two, and adds it to each value >= itself
# result is 6 lists, with descending lengths 6,5,4... ; total 21
shifted_additions = [
    [(pwrs_of_two[N]+X) for X in pwrs_of_two[N:]]
    for N in range(len(pwrs_of_two))
]

# adds base-value power of two to every other;
# result is 21 lists; where there are 'N' lists each of length 'N', (for N = 1..6)
# for a total count of 91. This inclues a lot of redundancies; all shorter lists are just shifted/slices of a longer list.
shifted_additions_comp2 = [
    [(2**ex)+X for ex in range(3+N,9)]
    for N in range(len(range(3,9)))
    for X in [(2**ex) for ex in range(3+N,9)]
]

# calculating the combined length of all nested lists
prev = [0,0]
total_lengths = [(prev := [I+prev[0], (I*I)+prev[1]]) for I in range(1,7)]


# 7 lists (including base powers of 2), each length 6
# it has redundant info, unlike 'shifted_additions', but it's cleaner
alt_comp = [
    base := [B for B in [(2**ex) for ex in range(3,9)]],
    *[[B+C for B in base] for C in base] 
]

# --------------------------------------------------------- #
#unique_bases = { I for L in shifted_additions for I in L }
#asdf = sorted([*unique_bases])

unique_bases = sorted([*{ I for L in shifted_additions for I in L }])
#unique_bases2 = sorted([*{ I for L in shifted_additions_comp2 for I in L }])
#assert(unique_bases == unique_bases2)

calcs = [CalcFsz(B) for B in unique_bases]

# finds bases where all calculations have integer results (result[1] is floating-point)
# { base: "[width x height] +offset" }
good_bases = {
    base: "[{} x {}] +{}".format(*result[0])
    for (base, result) in zip(unique_bases, calcs)
    if (result[1] == result[0])
}

# good_bases2 = [
#     [base, *(X := CalcFsz(base), (X[1]==X[0]))]
#     for base in unique_bases
# ]

good_bases_pwr2 = {
  72: "[936 x 64] +54",
  144: "[1872 x 128] +108",
  288: "[3744 x 256] +216"
}

adjusted_bases = [int(base*1.125) for base in unique_bases]
# unique_bases:   [16, 24, 32, 40, 48, 64, 72, 80,  96, 128, 136, 144, 160, 192, 256, 264, 272, 288, 320, 384, 512]
# adjusted_bases: [18, 27, 36, 45, 54, 72, 81, 90, 108, 144, 153, 162, 180, 216, 288, 297, 306, 324, 360, 432, 576]
# all results of adjustment are whole numbers; no decimal

adj_calcs = [CalcFsz(B) for B in adjusted_bases]
good_adj_bases = {
    base: "[{} x {}] +{}".format(*result[0])
    for (base, result) in zip(adjusted_bases, adj_calcs)
    if (result[1] == result[0])
}

# good_adj_bases = {36: "[468 x 32] +27", 72: "[936 x 64] +54", 108: "[1404 x 96] +81", 144: "[1872 x 128] +108", 180: "[2340 x 160] +135", 216: "[2808 x 192] +162", 288: "[3744 x 256] +216", 324: "[4212 x 288] +243", 360: "[4680 x 320] +270", 432: "[5616 x 384] +324", 576: "[7488 x 512] +432"}
# coincidentally, the three entries in 'good_bases_pwr2' also exist here.
# maybe there would be some unique entries if you allow offset to be non-integer
nice_pointsizes = {
   36: "[468 x 32] +27",
   72: "[936 x 64] +54",
  108: "[1404 x 96] +81",
  144: "[1872 x 128] +108",
  180: "[2340 x 160] +135",
  216: "[2808 x 192] +162",
  288: "[3744 x 256] +216",
  324: "[4212 x 288] +243",
  360: "[4680 x 320] +270",
  432: "[5616 x 384] +324",
  576: "[7488 x 512] +432",
}

# width, height, Yoffset
nice_pointsize_calcs = {
   36: ( 468,  32,  27),
   72: ( 936,  64,  54),
  108: (1404,  96,  81),
  144: (1872, 128, 108),
  180: (2340, 160, 135),
  216: (2808, 192, 162),
  288: (3744, 256, 216),
  324: (4212, 288, 243),
  360: (4680, 320, 270),
  432: (5616, 384, 324),
  576: (7488, 512, 432),
}

# ------------------------------------------------ #

import pathlib
#FONTFILE = pathlib.Path("Fonts/dejavu/DejaVuSans.ttf")
FONTFILE = pathlib.Path("Fonts/dejavu/DejaVuSerif.ttf")
outfolder = pathlib.Path("renders/")
assert(FONTFILE.exists()), "missing fontfile";
if not outfolder.exists(): outfolder.mkdir();


# replaces nonbasic characters in text (for filename generation)
def FilterText(text:str, allow_whitespace=True, allow_symbols=False) -> str:
    if text.isalnum(): return text
    ok_chars = ({'_', ' ', '\t', '\n'} if allow_whitespace else {'_'})
    if allow_symbols: ok_chars = { *ok_chars, *punctuation };
    bad_chars = {C for C in text if (C not in ok_chars) and ((not C.isprintable()) or (not C.isalnum()) or C.isspace())}
    for BC in bad_chars: text = text.replace(BC, "");
    return text


def GenerateTextCommand(text:str, pointsize:int, pzs_calcs:tuple[int,int,int] = None, fg_color:str = "white", output_filename:str = None) -> str:
    filtered_text = FilterText(text, allow_symbols=True)
    if pzs_calcs is None: pzs_calcs = CalcFontsizes(pointsize, len(filtered_text));
    (width, height, Yoffset) = pzs_calcs
    
    quoted_text_str = f'text 0,{Yoffset} "{filtered_text}"'
    # the order of nested quotations here is critical: double-quote INNER text, single-quotes OUTSIDE!
    # using the incorrect quotation-order makes it impossible to write text containing punctuation (!)
    # 'text 0,72 "epic text generation example!"' <-- correct
    # "text 0,72 'epic text generation example!'" <-- syntax error. adding any number of backslash-escapes will only insert backslashes into the output (see bottom of file)
    
    bg_color = ("white" if (fg_color == "black") else "black")
    #bg_color = "none" # transparent background
    
    if not output_filename: output_filename = FilterText(text, False)[:16]; # limit automatic filename length to 16 chars
    else: output_filename = FilterText(output_filename); # allow whitespace in filename only when specified
    output_filename += f"-{FONTFILE.stem}_{pointsize}_{width}x{height}+{Yoffset}_{fg_color[0]}{bg_color[0]}.png"
    
    command = f"imagemagick -size {width}x{height} "
    command += f"xc:{bg_color} "
    command += f"-font '{FONTFILE}' -pointsize {pointsize} "
    command += f"-fill {fg_color} -draw '{quoted_text_str}' " # reminder that single-quotes, not-double, are mandatory here
    command += f"'{outfolder}/{output_filename}'"
    return command


# -------------------------------------------------------------------------------------------- #


# imagemagick -size 1152x64 xc:black -font 'Fonts/dejavu/DejaVuSerif.ttf' -pointsize 72 -fill red -draw 'text 0,54 "epic text generation example!!!!"' 'renders/epic filename-DejaVuSerif_72_1152x64+54_rb.jpg'
example_command = GenerateTextCommand("epic text generation example!!!!", pointsize=72, fg_color="red", output_filename="epic filename!!!")
print(example_command)

# TODO: recheck the height/Y-offset calculations. Current calcs are incorrect for dejavu fonts
# DejaVuSerif @pointsize:72
# [ height:64 | offset:54 ]  <-- current; top of 'l' and bottom of 'g' and 'p' are cut off
# [ height:72 | offset:56 ]  <-- tightest possible fit. top of 'l' is possibly clipped?
# [ height:74 | offset:56/57/58 ] <-- offset 58 might barely clip the bottom of 'g'

# DejaVuSans @pointsize:72
# [ height:72 | offset:56 ]  <-- good fit (extra 1-2 pixel margins), good match for Serif
# [ height:70 | offset:55 ]  <-- best fit
# [ height:69 | offset:54 ]  <-- lowest possible size, definitely clips ~0.5 pixels off the top of the 'i'/'l'

# default values for pointsize 72
base_pzs = (1152, 64, 54)
test_pzs = [
    (base_pzs[0], base_pzs[1] + extraHeight, base_pzs[2] + extraOffset)
    for extraHeight in range(2, 17, 2)
    for extraOffset in range(0, 9, 2)
]

for pzs in test_pzs:
    print(GenerateTextCommand("epic text generation example!!!!", 72, pzs, "red", "epic filename!!!"));



# -------------------------------------------------------------------------------------------- #

# Bash cannot handle single-quoted text containing punctuation nested inside double-quotes;
# quoted symbols with backslashes end up in output, but no-backslashes are a (Bash) syntax error
# and a single-backslash raw-string is somehow a python syntax error

# input-text: "epic text generation example!!!"
#  ____________________________________________________________________________________________
# |_string on cmdline________________________________|_result__________________________________|
# |__________________________________________________|_________________________________________|
#  'epic text generation example\\\\\!\\\\\!\\\\\!' -->  epic text generation example\\!\\!\\!
#  'epic text generation example\\\\!\\\\!\\\\!'    -->  epic text generation example\!\!\!
#  'epic text generation example\\!\\!\\!'          -->  epic text generation example\!\!\!
#  'epic text generation example\!\!\!'             -->  epic text generation example\!\!\!
#  'epic text generation example!!!'                -->  syntax error (bash: !': event not found)



