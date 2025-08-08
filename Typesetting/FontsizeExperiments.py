# reverse-engineering the relations between font's pointsize and character-dimensions
# for calculating optimal image-dimensions and text placement from a given fontsize,
# or the reverse - calculating optimal fontsize and placement given image dimensions

letters = [(chr(C),chr(C).upper()) for C in range(ord('a'),ord('z')+1)]
zipped = [*zip(*letters)]
alphabets = [''.join(alphabet) for alphabet in zipped]
alphabets = ['abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ']

digits = [str(N) for N in range(10)]
digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
digit_str = ''.join(digits)

punctuation = [ chr(C) for C in [
    *range(0x21, 0x30),
    *range(0x3A, 0x41),
    *range(0x5B, 0x61),
    *range(0x7B, 0x7F),
]]

punctuation_str = ''.join(punctuation)
# punctuation_str = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
# punctuation_str = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"


strings = {
    "alphabets": alphabets,
    "digits": digit_str,
    "punct": punctuation_str,
}

alphanum = '\n'.join([*alphabets, digit_str])
strlines = '\n'.join([*alphabets, digit_str, punctuation_str])




pointsize = 144
# img_width = ((pointsize/2)*26) == 1872
# img_height = (pointsize/1.125) == 128
# img_size = 1872 x 128
# Yoffset = (pointsize*(3/4)) == 108

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
        (w,h,y) = (N if (type(N) is int) else f"{N:.{precision}f}" for N in (w,h,y))
        print(f" [{w} x {h}] +{y}");
    print("")
    return results




good_base_sizes = [
    ((2**ex), (2**ex) * 1.125)
    for ex in range(4,9)
]
# [(16, 18.0), (32, 36.0), (64, 72.0), (128, 144.0), (256, 288.0)]

pszs = [int(B[1]) for B in good_base_sizes]
# [18, 36, 72, 144, 288]

calcs = {psz:CalcFsz(psz) for psz in pszs}
{18: [(234, 16, 13), (234.0, 16.0, 13.5)],
 36: [(468, 32, 27), (468.0, 32.0, 27.0)],
 72: [(936, 64, 54), (936.0, 64.0, 54.0)],
 144: [(1872, 128, 108), (1872.0, 128.0, 108.0)],
 288: [(3744, 256, 216), (3744.0, 256.0, 216.0)]}


[I for I in range(1,10)]
# [1, 2, 3, 4, 5, 6, 7, 8, 9]

arr = [((N := I),(N*2)) for I in range(1,10)]
# [(1, 2), (2, 4), (3, 6), (4, 8), (5, 10), (6, 12), (7, 14), (8, 16), (9, 18)]



# -------------------------------------------
arr = [((N := I),(N*2)) for I in range(1,10)]
X = []; Z = []; flattened = [(Z := [*Z, *X]) for X in arr]

# arr = [(1, 2), (2, 4), (3, 6), (4, 8), (5, 10), (6, 12), (7, 14), (8, 16), (9, 18)]
# flattened =
[[1, 2],
 [1, 2, 2, 4],
 [1, 2, 2, 4, 3, 6],
 [1, 2, 2, 4, 3, 6, 4, 8],
 [1, 2, 2, 4, 3, 6, 4, 8, 5, 10],
 [1, 2, 2, 4, 3, 6, 4, 8, 5, 10, 6, 12],
 [1, 2, 2, 4, 3, 6, 4, 8, 5, 10, 6, 12, 7, 14],
 [1, 2, 2, 4, 3, 6, 4, 8, 5, 10, 6, 12, 7, 14, 8, 16],
 [1, 2, 2, 4, 3, 6, 4, 8, 5, 10, 6, 12, 7, 14, 8, 16, 9, 18]]


unzipped = [*zip(*arr)]
# [(1, 2, 3, 4, 5, 6, 7, 8, 9), (2, 4, 6, 8, 10, 12, 14, 16, 18)]

A = []; flat_unzip = [(A := [*A, *B]) for B in unzipped][-1]
# [1, 2, 3, 4, 5, 6, 7, 8, 9, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# flat_unzip groups each sequence, whereas flattened[-1] interleaves them; maintaining pair ordering
# flat_unzip   : [1, 2, 3, 4, 5, 6, 7, 8, 9, 2, 4, 6, 8, 10, 12, 14, 16, 18]
# flattened[-1]: [1, 2, 2, 4, 3, 6, 4, 8, 5, 10, 6, 12, 7, 14, 8, 16, 9, 18]

# --------------------------------------------------------------------------------------------------



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

results = [CalcFsz(B) for B in unique_bases]

# finds bases where all calculations have integer results (result[1] is floating-point)
# { base: "[width x height] +offset" }
good_bases = {
    base: "[{} x {}] +{}".format(*result[0])
    for (base, result) in zip(unique_bases, results)
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


def PrintDict(D:dict, name = None):
    if name is not None: print("{} = ".format(name)+'{');
    for (k,v) in D.items(): print(f"  {k}: {repr(v)}, ");
    if name is not None: print("}\n");

print("\n"); print("-"*40); print("\n")
PrintDict(good_bases, "good_bases")
PrintDict(good_bases_pwr2, "good_bases_pwr2")



