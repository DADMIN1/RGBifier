#!/bin/bash


FONTFILE="Fonts/dejavu/DejaVuSans.ttf"
if [[ ! -f ${FONTFILE} ]] then echo "ERROR: missing font file"; exit(1); fi;
if [[ ! -d "renders" ]] then mkdir "renders"; fi;


alias imagemagick="convert-im6.q16"

function imagemagick-listfonts()
{
    imagemagick -list font | grep "Font: "
    # 'tr' splitting each line on colon; then excluding the 'Font' lines
    imagemagick -list font | grep 'Font:' | tr ':' '\n' | grep --invert-match 'Font'
    # alternatively, use 'cut' to trim the first 8 characters (counting starts at 1 and includes spaces: "__Font:_" -> 8 chars)
    imagemagick -list font | grep 'Font:' | cut --characters=9-
    # another option for 'cut' is to specify colon as delimiter. field-2 is text after the delim; field-1 is before
    imagemagick -list font | grep 'Font:' | cut --delimiter=":" --fields=2
}

imagemagick -size 320x100 xc:black -font ${FONTFILE} -pointsize 72 -fill white -draw "text 28,68 'Test'" renders/testrender.jpg

# base_size = 320x100
# (72/2)px for each char
# 100px for each line of text

# 72*26 == 1872 / 2 == 936
936x72

imagemagick -size 1872x300 xc:black -font ${FONTFILE} -pointsize 72 -fill white -draw "text 0,0 'abcdefghijklmnopqrstuvwxyz\nABCDEFGHIJKLMNOPQRSTUVWXYZ\n0123456789'" renders/testrender.jpg

-pointsize 96
# (96/2)*26 == 1248
-size 1248x86
y-offset 72
# not sure why '86' is correct height and '72' is correct offset


pointsize = 144
# img_width = ((pointsize/2)*26) == 1872
# img_height = (pointsize/1.125) == 128
img_size = 1872 x 128
# Yoffset = (pointsize*(3/4)) == 108

# -size 1872x128 ... -pointsize 144 ... "text 0,108 "
imagemagick -size 1872x128 xc:Navy -font ${FONTFILE} -pointsize 144 -fill white -draw "text 0,108 'abcdefghijklmnopqrstuvwxyz'" renders/testrender_b3.jpg

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
img_size = 1872 x 128
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



-----------------------------------------
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


