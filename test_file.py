def lol(a):
    b = a
    if a > 5:
        if a > 10:
            b *= 2
        b *= -1

    if a == 0:
        b = 12
        
    if a == 6:
        b += 1

    if a == 11:
        raise Exception("ohh no!")

    return 2 * b
