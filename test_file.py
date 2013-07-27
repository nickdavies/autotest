def lol(a):
    if a == 0:
        a = 12

    if a == 1:
        a = 11

    if a == 2:
        raise KeyError("this sure is a strange function")

    return 2 * a
