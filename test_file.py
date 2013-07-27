def lol(a):
    b = a
    if a == 0:
        b = 12

    if a == 1:
        b = 11

    if a == 2:
        raise KeyError("this sure is a strange function")

    return 2 * b
