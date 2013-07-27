# Autotest

## Example

An example input of:

   def lol(a):
    if a == 0:
        a = 12

    if a == 1:
        a = 11

    if a == 2:
        raise KeyError("this sure is a strange function")

    return 2 * a 
 
will result in code that looks like:

   import  test_file

    assert test_file.lol(0) == 24
    assert test_file.lol(1) == 22
    assert test_file.lol(3) == 6

    try:
        test_file.lol(2)
        assert False, 'Did not raise KeyError'
    except KeyError:
         pass

## What dosen't work

Just about anything except the example file
