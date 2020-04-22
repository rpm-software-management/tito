import unittest
import mock
from datetime import datetime
from tito.tagger import VersionTagger
from tito.compat import PY2, RawConfigParser

from unit import is_epel6
if is_epel6:
    import unittest2 as unittest
else:
    import unittest


def strftime_mock(s):
    if not PY2:
        from datetime import timezone
    tzinfo = None if PY2 else timezone.utc
    someday = datetime(2020, 4, 22, 15, 2, tzinfo=tzinfo)
    return someday.strftime(s)


class TestVersionTagger(unittest.TestCase):
    def setUp(self):
        self.config = RawConfigParser()

    @mock.patch("tito.tagger.main.strftime", strftime_mock)
    def test_today(self):
        tagger = VersionTagger(self.config)
        assert tagger.today == "Wed Apr 22 2020"

    @unittest.skipIf(PY2, "It is not trivial to represent timezone in python2 because"
                          "datetime.timezone is python3 only and pytz is not in EPEL. This feature"
                          "is for F27+ and EPEL8+ so we don't need to test it for python2")
    @mock.patch("tito.tagger.main.strftime", strftime_mock)
    def test_today_datetime(self):
        self.config["buildconfig"] = {"changelog_date_with_time": True}
        tagger = VersionTagger(self.config)
        assert tagger.today == "Wed Apr 22 15:02:00 UTC 2020"
