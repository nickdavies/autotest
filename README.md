# Autotest

## Example

An example input of:

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

will result in code that looks like:

    import pytest

    import test_file

    def test_lol_normal():

        assert test_file.lol(12) == -48
        assert test_file.lol(6) == -10
        assert test_file.lol(7) == -14
        assert test_file.lol(0) == 24
        assert test_file.lol(-1) == -2

    def test_lol_errors():

        with pytest.raises(Exception):
            test_file.lol(11)

## What dosen't work

Just about anything except the example file
