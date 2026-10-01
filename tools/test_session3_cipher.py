"""Verify the cipher and the stated deduction path without exposing the key."""
import string
import unittest

import session3_cipher as puzzle


class CipherTests(unittest.TestCase):
    def test_bijective_not_a_shift(self):
        self.assertEqual(set(puzzle.WRITTEN),set(string.ascii_uppercase))
        self.assertGreater(len({(ord(b)-ord(a)) % 26 for a,b in zip(puzzle.PLAIN,puzzle.WRITTEN)}),1)
        self.assertEqual(puzzle.decode(puzzle.encode(puzzle.MEETING)),puzzle.MEETING)

    def test_documented_deductions_cover_message_and_reply(self):
        # Reconstruct a player's sheet from the two identified gift labels,
        # then the words the Director's route says they can infer. Do not use
        # the remaining entries of the full alphabet to fill any gaps.
        sheet={}
        def infer(written,ordinary):
            self.assertEqual(len(written),len(ordinary))
            for a,b in zip(written,ordinary):
                if a not in string.ascii_uppercase:
                    self.assertEqual(a,b)
                    continue
                self.assertIn(sheet.get(a,b),(b,))
                self.assertNotIn(b,[v for k,v in sheet.items() if k!=a])
                sheet[a]=b
        infer("TOSN DZFV","GILT MASK")
        infer("RGOBZNH FZSH","PRIVATE SALE")
        self.assertEqual(len(sheet),12)
        for written,ordinary in [("NKH","THE"),("CPPV","BOOK"),("NKOGM","THIRD"),
            ("ZUNHG","AFTER"),("OI","IN"),("NWP","TWO"),("YZGM","YARD"),("LPDH","COME")]:
            infer(written,ordinary)
        self.assertEqual(len(sheet),21)
        self.assertEqual("".join(sheet.get(c,c) for c in puzzle.encode(puzzle.MEETING)),puzzle.MEETING)
        reverse={b:a for a,b in sheet.items()}
        reply="".join(reverse.get(c,c) for c in puzzle.NEUTRAL_REPLY)
        self.assertEqual(reply,"NKH CPPV OF FZUH. O WOSS LPDH.")
        self.assertEqual(puzzle.decode(reply),puzzle.NEUTRAL_REPLY)


if __name__=="__main__":unittest.main()
