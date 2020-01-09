import exportPRG
import unittest

class TestExportPRG(unittest.TestCase):
    def test_quotes_and_rem(self):
        # a two-line program which tests quotes and rem handling:
        ascii_prg = '10 print "rem":rem "print": end\n'
        ascii_prg += '1337 print"print"+chr$(67)+"chr$(67)"'
        
        # ground truth from VICE:
        bin_from_vice = b'\x01\x1C\x1C\x1C\x0A\x00\x99\x20\x22\x52\x45\x4D\x22\x3A\x8F\x20\x22\x50\x52'
        bin_from_vice += b'\x49\x4E\x54\x22\x3A\x20\x45\x4E\x44\x00\x3A\x1C\x39\x05\x99\x22\x50\x52\x49'
        bin_from_vice += b'\x4E\x54\x22\xAA\xC7\x28\x36\x37\x29\xAA\x22\x43\x48\x52\x24\x28\x36\x37\x29'
        bin_from_vice += b'\x22\x00\x00\x00'
        bin_from_vice = bytearray(bin_from_vice)

        self.assertEqual(exportPRG.ascii_to_c128prg(ascii_prg), bin_from_vice)


if __name__ == '__main__':
    unittest.main()
