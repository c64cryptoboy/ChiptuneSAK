import unittest
from chiptunesak import ctsGenPrg  # src/


class TestExportPRG(unittest.TestCase):
    def test_quotes_and_rem(self):
        # a two-line program which tests quotes and rem handling:
        ascii_prg = '10 print "rem":rem "print": end\n'
        ascii_prg += '1337 print"print"+chr$(67)+"chr$(67)"'

        # print(' '.join('%02X' % b for b in ctsGenPrg.ascii_to_c128prg(ascii_prg)))

        # ground truth from VICE:
        tmp = '''01 1C 1C 1C 0A 00 99 20 22 52 45 4D 22 3A 8F 20 22 50 52
                 49 4E 54 22 3A 20 45 4E 44 00 3A 1C 39 05 99 22 50 52 49
                 4E 54 22 AA C7 28 36 37 29 AA 22 43 48 52 24 28 36 37 29
                 22 00 00 00'''
        bin_from_vice = bytearray(int(x, 16) for x in tmp.split())

        self.assertEqual(ctsGenPrg.ascii_to_prg_c128(ascii_prg), bin_from_vice)


if __name__ == '__main__':
    unittest.main()
