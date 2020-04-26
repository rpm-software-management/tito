import unittest
import mock
from tito.compat import PY2, RawConfigParser
from tito.release import Releaser
from unit import builtins_input


class ReleaserTests(unittest.TestCase):

    @mock.patch("tito.release.main.create_builder")
    @mock.patch("tito.release.main.mkdtemp")
    def setUp(self, mkdtemp, create_builder):
        self.config = RawConfigParser()

        self.releaser_config = RawConfigParser()
        self.releaser_config.add_section("test")
        self.releaser_config.set('test', "releaser",
            "tito.release.Releaser")

        self.releaser = Releaser("titotestpkg", None, "/tmp/tito/",
            self.config, {}, "test", self.releaser_config, False,
            False, False, **{"offline": True})

    @mock.patch(builtins_input)
    def test_ask_yes_or_no(self, input_mock):
        input_mock.side_effect = "y"
        assert self.releaser._ask_yes_no()

        input_mock.side_effect = "n"
        assert not self.releaser._ask_yes_no()

        input_mock.side_effect = ["yy", "y"]
        assert self.releaser._ask_yes_no()

        input_mock.side_effect = ["yy", "no"]
        assert not self.releaser._ask_yes_no()
