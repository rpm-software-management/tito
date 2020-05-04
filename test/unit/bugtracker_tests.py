import unittest
from tito.bugtracker import BugzillaExtractor
from mock import Mock, patch


class ExtractBugzillasTest(unittest.TestCase):

    def test_single_line(self):
        commit_log = "- 123456: Did something interesting."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_with_dash(self):
        commit_log = "- 123456 - Did something interesting."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_with_no_spaces(self):
        commit_log = "- 123456-Did something interesting."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_diff_format(self):
        commit_log = "+- 123456: Did something interesting."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_line_no_bz(self):
        commit_log = "- Did something interesting."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(0, len(results))

    def test_multi_line(self):
        commit_log = "- 123456: Did something interesting.\n- Another commit.\n" \
            "- 456789: A third commit."
        extractor = BugzillaExtractor(commit_log)
        results = extractor.extract()
        self.assertEquals(2, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])
        self.assertEquals("Resolves: #456789 - A third commit.",
                results[1])

    def test_single_required_flag_found(self):

        extractor = BugzillaExtractor("", required_flags=[
            'myos-1.0+', 'pm_ack+'])
        bug1 = ('123456', 'Did something interesting.')
        extractor._extract_bzs = Mock(return_value=[
            bug1])
        extractor._check_for_bugzilla_creds = Mock()

        extractor._load_bug = Mock(
            return_value=MockBug(bug1[0], ['myos-1.0+', 'pm_ack+']))

        results = extractor.extract()

        self.assertEquals(1, len(extractor.bzs))
        self.assertEquals(bug1[0], extractor.bzs[0][0])
        self.assertEquals(bug1[1], extractor.bzs[0][1])

        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_required_flags_found(self):

        extractor = BugzillaExtractor("", required_flags=[
            'myos-1.0+', 'pm_ack+'])
        bug1 = ('123456', 'Did something interesting.')
        bug2 = ('444555', 'Something else.')
        bug3 = ('987654', 'Such amaze!')
        extractor._extract_bzs = Mock(return_value=[
            bug1, bug2, bug3])
        extractor._check_for_bugzilla_creds = Mock()

        bug_mocks = [
            MockBug(bug1[0], ['myos-1.0+', 'pm_ack+']),
            MockBug(bug2[0], ['myos-2.0?', 'pm_ack?']),
            MockBug(bug3[0], ['myos-1.0+', 'pm_ack+'])]

        def next_bug(*args):
            return bug_mocks.pop(0)

        extractor._load_bug = Mock(side_effect=next_bug)

        results = extractor.extract()

        self.assertEquals(2, len(extractor.bzs))
        self.assertEquals(bug1[0], extractor.bzs[0][0])
        self.assertEquals(bug1[1], extractor.bzs[0][1])
        self.assertEquals(bug3[0], extractor.bzs[1][0])
        self.assertEquals(bug3[1], extractor.bzs[1][1])

        self.assertEquals(2, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])
        self.assertEquals("Resolves: #987654 - Such amaze!",
                results[1])

    @patch("tito.bugtracker.error_out")
    def test_required_flags_missing(self, mock_error):
        required_flags = ['myos-2.0+']
        extractor = BugzillaExtractor("", required_flags)
        bug1 = ('123456', 'Did something interesting.')
        bug2 = ('444555', 'Something else.')
        bug3 = ('987654', 'Such amaze!')
        extractor._extract_bzs = Mock(return_value=[
            bug1, bug2, bug3])
        extractor._check_for_bugzilla_creds = Mock()

        bug_mocks = [
            MockBug(bug1[0], ['myos-1.0+', 'pm_ack+']),
            MockBug(bug2[0], ['myos-2.0?', 'pm_ack?']),
            MockBug(bug3[0], ['myos-1.0+', 'pm_ack+'])]

        def next_bug(*args):
            return bug_mocks.pop(0)

        extractor._load_bug = Mock(side_effect=next_bug)

        results = extractor.extract()

        self.assertEquals(0, len(extractor.bzs))
        self.assertEquals(0, len(results))
        mock_error.assert_called_once_with("No bugzillas found with required flags: %s" % required_flags)

    def test_required_flags_missing_with_placeholder(self):

        extractor = BugzillaExtractor("", required_flags=[
            'myos-2.0+'], placeholder_bz="54321")
        bug1 = ('123456', 'Did something interesting.')
        extractor._extract_bzs = Mock(return_value=[
            bug1])
        extractor._check_for_bugzilla_creds = Mock()

        extractor._load_bug = Mock(
            return_value=MockBug(bug1[0], ['myos-1.0+', 'pm_ack+']))

        results = extractor.extract()

        self.assertEquals(0, len(extractor.bzs))

        self.assertEquals(1, len(results))
        self.assertEquals("Related: #54321", results[0])

    def test_same_id_multiple_times(self):

        extractor = BugzillaExtractor("", required_flags=[
            'myos-1.0+', 'pm_ack+'])
        bug1 = ('123456', 'Did something interesting.')
        bug3 = ('123456', 'Oops, lets try again.')
        extractor._extract_bzs = Mock(return_value=[
            bug1, bug3])
        extractor._check_for_bugzilla_creds = Mock()

        extractor._load_bug = Mock(
            return_value=MockBug(bug1[0], ['myos-1.0+', 'pm_ack+']))

        results = extractor.extract()

        self.assertEquals(2, len(extractor.bzs))
        self.assertEquals(bug1[0], extractor.bzs[0][0])
        self.assertEquals(bug1[1], extractor.bzs[0][1])
        self.assertEquals(bug3[0], extractor.bzs[1][0])
        self.assertEquals(bug3[1], extractor.bzs[1][1])

        self.assertEquals(2, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])
        self.assertEquals("Resolves: #123456 - Oops, lets try again.",
                results[1])

    @patch("tito.bugtracker.error_out")
    def test_bug_doesnt_exist(self, mock_error):
        required_flags = ['myos-1.0+', 'pm_ack+']
        extractor = BugzillaExtractor("", required_flags)
        bug1 = ('123456', 'Did something interesting.')
        extractor._extract_bzs = Mock(return_value=[
            bug1])
        extractor._check_for_bugzilla_creds = Mock()

        from tito.compat import xmlrpclib
        extractor._load_bug = Mock(side_effect=xmlrpclib.Fault("", ""))

        results = extractor.extract()

        self.assertEquals(0, len(extractor.bzs))
        self.assertEquals(0, len(results))
        mock_error.assert_called_once_with("No bugzillas found with required flags: %s" % required_flags)


class MockBug(object):
    def __init__(self, bug_id, flags):
        self.flags = {}
        for flag in flags:
            self.flags[flag[0:-1]] = flag[-1]

    def get_flag_status(self, flag):
        if flag in self.flags:
            return self.flags[flag]
        else:
            return None
