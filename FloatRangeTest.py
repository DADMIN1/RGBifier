# experiments and notes about float-imprecision and 'FloatRange'

# same as normal range, except with floats. Includes both 'start' and 'end' values
def FloatRange(start:float, end:float, interval:float, precision:int=6) -> list[float]:
    return [*((I/(10**precision)) for I in range(*[int(F*(10**precision)) for F in (start, end, interval)])), float(end)]

# the interval between the penultimate number and the end can be awkward if it's not a clean divisor
# should it overshoot the end instead? can the start/end be adjusted to compensate?

# TODO: figure out if there's some workaround for float-imprecision here, or at least some kind of predictable pattern (in relation to 'precision' parameter)
# clean intervals like '0.25' tend to work at all precisions.
# the precision must be at least a high as the length of the decimal, and matching is usually ideal,
# but some intervals need much higher precision, and may only work at specific multiples of that precision-value
# for example, 
# 'interval = 0.255' works at any precision, but
# 'interval = 1.255' only works when the precision is a multiple of 3!

# 'interval = 0.255'
#   FloatRange(0,  2, 0.255, 3) == [0.0, 0.255,   0.51,    0.765,   1.02,    1.275,    1.53,    1.785,    2.0]

# 'interval = 1.255'
#   FloatRange(0, 10, 1.255, 3) == [0.0, 1.255,   2.51,    3.765,   5.02,    6.275,    7.53,    8.785,   10.0]
#   FloatRange(0, 10, 1.255, 4) == [0.0, 1.2549,  2.5098,  3.7647,  5.0196,  6.2745,   7.5294,  8.7843,  10.0]
#   FloatRange(0, 10, 1.255, 5) == [0.0, 1.25499, 2.50998, 3.76497, 5.01996, 6.27495,  7.52994, 8.78493, 10.0]
#   FloatRange(0, 10, 1.255, 6) == [0.0, 1.255,   2.51,    3.765,   5.02,    6.275,    7.53,    8.785,   10.0]

# 'interval = 0.025' works at any precision (>= 3),
# 'interval = 1.025' works only at precisions: (3, 4, 7, 10, 13). Same is true for '-1.025'
# which looks again like multiples of 3, but starting at 4 digits instead of 3, for some reason.
# the odd intervals '1.001' and '1.003' are inaccurate until precision 8, but the even intervals '1.002'/'1.004' work perfectly.
# intervals below one, or well above one, seem to work with any precision, but values between 1 and 2 are inconsistent?


def DecimalCount(F:float, parts:int=1) -> int | tuple[int,int] | tuple[int,int,int]:
    """ Count digits before or after the decimal-point in a float.
    :param parts: segment selection.
      '0/1': whole/decimal, '2': both,
      '-2': overall length, '3': (overall, both)
    :return: length of a single segment, or tuple of both lengths (and maybe total)."""
    (whole, decimal) = str(float(F)).rsplit('.', maxsplit=1)
    lengths = (len(whole),len(decimal))
    overall = (len(whole)+len(decimal))
    if(parts == 2): return  lengths;
    if(parts ==-2): return  overall;
    if(parts == 3): return (overall, *lengths);
    return lengths[parts]


def BruteForce_FloatRanges(interval:float, rangelimit:int|float=0, numRounds:int=10, decimalDisplayLimit:int=6) -> list[int]:
    """ Debug function for investigating float-imprecision in 'FloatRange' 
    :param interval:   passed to FloatRange
    :param rangelimit: endpoint of FloatRange. If unspecified, auto-scales (against interval) such that ranges have lengths of 8-10
    :param numRounds:  number of 'precision' levels tested
    :param decimalDisplayLimit: maximum digits after decimal place
    :return: list of precision-levels with perfect accuracy """
    estPrecision = DecimalCount(interval) # digits after the decimal in stepsize
    if (rangelimit == 0): rangelimit = int((L := (interval*10)) - (L//10)); # try to ensure FloatRange length is 8-10, ending on a whole number
    if ((rangelimit == 0) or ((rangelimit // interval) > 25)): rangelimit = float(interval*10); # failed to set good integer limit, using float instead
    
    # assume that matching precision gives correct values
    perfectRange = FloatRange(0, rangelimit, interval, estPrecision)
    topPrecision = max([DecimalCount(PF) for PF in perfectRange])
    # assert(perfectRange[1] == interval), "first float should always equal 'interval'"
    if ((estPrecision != topPrecision) or (perfectRange[1] != interval)):
        print(f"[WARNING] float-imprecision detected. comparisons will not be accurate!!")
        # TODO: find a good base-precision if this happens
    
    precz = estPrecision+1
    generatedRanges = [
        FloatRange(0, rangelimit, interval, precision)
        for precision in range(precz, precz+numRounds)
    ]
    assert(all([(len(R) == len(perfectRange)) for R in generatedRanges])), "all ranges should have the same length!"
    comparisons = [(R == perfectRange) for R in generatedRanges]
    columns = [*zip(*generatedRanges, strict=True)]
    
    # these two are unused
    column_widths = [
        [DecimalCount(F,3) for F in column]
        for column in columns
    ]
    field_widths = [
        [*zip(*[DecimalCount(F,3) for F in column], strict=True)]
        for column in columns
    ]
    
    # note that the max totals in these tuples will be less than the sum of the max segments,
    # unless a single number contributed all three maximums.
    max_field_widths = [
        [ max(field_width) for field_width in 
        [*zip(*[DecimalCount(F,3) for F in column], strict=True)]
        ] for column in columns
    ]
    
    assert(len(max_field_widths) == len(perfectRange)), "should have a tuple for each column"
    
    results = [*zip(
        range(precz, precz+numRounds),
        comparisons,
        generatedRanges,
        strict=True
    )]
    
    print(f"interval: {interval} | rangelimit: {rangelimit} | estPrecision: {estPrecision}")
    print(f"perfectRange: {perfectRange}")
    
    goodValues = [f"({estPrecision})"] # added as a string for formatting reasons, will be replaced at the end.
    for (precision, isPerfect, floatRange) in results:
        if isPerfect: goodValues.append(precision)
        passFailStr = ("Pass" if isPerfect else "Fail")
        precisionStr = f"{(' ' if (precision < 10) else '')}{precision}"
        print(f'[{passFailStr}] [{precisionStr}]: [', end=" ")
        for (fnum, (overallW, wholeW, decimalW)) in zip(floatRange, max_field_widths):
            if (decimalW > decimalDisplayLimit): decimalW = decimalDisplayLimit;
            fmtstr = '{' + f':{wholeW}.{decimalW}f' + '}'
            zfill_amount = (wholeW + decimalW + 1)  # +1 because zfill counts the decimal-place, for some reason.
            # I don't actually want zeroes from 'zfill', just spaces. Unfortunately, simply replacing all zeroes just makes it unreadable.
            # The first 'replace' preserves any zeroes in the original number with a placeholder; which are restored by the last 'replace'
            print(fmtstr.format(fnum).replace('0','@').zfill(zfill_amount).replace('0',' ').replace('@','0'), end=", ")
        print(']')
    
    # just removing the quotes surrounding the parenthesized string
    goodValues_repr = goodValues.__repr__().replace("'","")
    # -1 because we're not including the initial precision in the test-count
    print(f"[{len(goodValues)-1}/{numRounds}] perfect-accuracy precisions: {goodValues_repr}")
    goodValues[0] = estPrecision # replacing the parenthesized string with the actual number
    return goodValues



if __name__ == "__main__":
    test_intervals = [0.025, 0.25, 0.255, 1.025, -1.025, 1.255, -1.255, 1.234567]
    print(f"\ntesting intervals: {test_intervals}\n")
    for interval in test_intervals:
        BruteForce_FloatRanges(interval)
        print("\n")
    
    print("done")
