import unittest

from mgraph.stexcasp import parser


class CliTests(unittest.TestCase):
    def test_definitions_are_opt_in(self) -> None:
        self.assertFalse(parser().parse_args(["symbol-uri"]).definitions)
        self.assertTrue(
            parser().parse_args(["symbol-uri", "--definitions"]).definitions
        )

    def test_old_verbalizations_flag_is_an_alias(self) -> None:
        self.assertTrue(
            parser().parse_args(["symbol-uri", "--verbalizations"]).definitions
        )


if __name__ == "__main__":
    unittest.main()
