#
# Copyright (c) 2008-2009 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.

""" Pure unit tests for tito's common module. """

from tito.common import *
from tito import common

import unittest

from mock import Mock


class CommonTests(unittest.TestCase):

    def test_normalize_class_name(self):
        """ Test old spacewalk.releng namespace is converted to tito. """
        self.assertEquals("tito.builder.Builder",
                normalize_class_name("tito.builder.Builder"))
        self.assertEquals("tito.builder.Builder",
                normalize_class_name("spacewalk.releng.builder.Builder"))
        self.assertEquals("tito.tagger.VersionTagger",
                normalize_class_name("spacewalk.releng.tagger.VersionTagger"))

    def test_replace_version_leading_whitespace(self):
        line = "    version='1.0'\n"
        expected = "    version='2.5.3'\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_no_whitespace(self):
        line = "version='1.0'\n"
        expected = "version='2.5.3'\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_some_whitespace(self):
        line = "version = '1.0'\n"
        expected = "version = '2.5.3'\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_double_quote(self):
        line = 'version="1.0"\n'
        expected = 'version="2.5.3"\n'
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_trailing_chars(self):
        line = "version = '1.0', blah blah blah\n"
        expected = "version = '2.5.3', blah blah blah\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_crazy_old_version(self):
        line = "version='1.0asjhd82371kjsdha98475h87asd7---asdai.**&'\n"
        expected = "version='2.5.3'\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_crazy_new_version(self):
        line = "version='1.0'\n"
        expected = "version='91asj.;]][[a]sd[]'\n"
        self.assertEquals(expected, replace_version(line,
            "91asj.;]][[a]sd[]"))

    def test_replace_version_uppercase(self):
        line = "VERSION='1.0'\n"
        expected = "VERSION='2.5.3'\n"
        self.assertEquals(expected, replace_version(line, "2.5.3"))

    def test_replace_version_no_match(self):
        line = "this isn't a version fool.\n"
        self.assertEquals(line, replace_version(line, "2.5.3"))

    def test_extract_sha1(self):
        ls_remote_output = "Could not chdir to home directory\n" + \
                           "fe87e2b75ed1850718d99c797cc171b88bfad5ca ref/origin/sometag"
        self.assertEquals("fe87e2b75ed1850718d99c797cc171b88bfad5ca",
                          extract_sha1(ls_remote_output))


class VersionMathTest(unittest.TestCase):
    def test_increase_version_minor(self):
        line = "1.0.0"
        expected = "1.0.1"
        self.assertEquals(expected, increase_version(line))

    def test_increase_version_major(self):
        line = "1.0"
        expected = "1.1"
        self.assertEquals(expected, increase_version(line))

    def test_increase_release(self):
        line = "1"
        expected = "2"
        self.assertEquals(expected, increase_version(line))

    def test_underscore_release(self):
        line = "1_PG5"
        expected = "2_PG5"
        self.assertEquals(expected, increase_version(line))

    def test_increase_versionless(self):
        line = "%{app_version}"
        expected = "%{app_version}"
        self.assertEquals(expected, increase_version(line))

    def test_increase_release_with_rpm_cruft(self):
        line = "1%{?dist}"
        expected = "2%{?dist}"
        self.assertEquals(expected, increase_version(line))

    def test_increase_release_with_zstream(self):
        line = "1%{?dist}.1"
        expected = "1%{?dist}.2"
        self.assertEquals(expected, increase_version(line))

    def test_unknown_version(self):
        line = "somethingstrange"
        expected = "somethingstrange"
        self.assertEquals(expected, increase_version(line))

    def test_empty_string(self):
        line = ""
        expected = ""
        self.assertEquals(expected, increase_version(line))

    def test_increase_zstream(self):
        line = "1%{?dist}"
        expected = "1%{?dist}.1"
        self.assertEquals(expected, increase_zstream(line))

    def test_increase_zstream_already_appended(self):
        line = "1%{?dist}.1"
        expected = "1%{?dist}.2"
        self.assertEquals(expected, increase_zstream(line))

    def test_reset_release_with_rpm_cruft(self):
        line = "2%{?dist}"
        expected = "1%{?dist}"
        self.assertEquals(expected, reset_release(line))

    def test_reset_release_with_more_rpm_cruft(self):
        line = "2.beta"
        expected = "1.beta"
        self.assertEquals(expected, reset_release(line))

    def test_reset_release(self):
        line = "2"
        expected = "1"
        self.assertEquals(expected, reset_release(line))


class ExtractBugzillasTest(unittest.TestCase):

    def test_single_line(self):
        commit_log = "- 123456: Did something interesting."
        results = extract_bzs(commit_log)
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_with_dash(self):
        commit_log = "- 123456 - Did something interesting."
        results = extract_bzs(commit_log)
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_with_no_spaces(self):
        commit_log = "- 123456-Did something interesting."
        results = extract_bzs(commit_log)
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_diff_format(self):
        commit_log = "+- 123456: Did something interesting."
        results = extract_bzs(commit_log)
        self.assertEquals(1, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])

    def test_single_line_no_bz(self):
        commit_log = "- Did something interesting."
        results = extract_bzs(commit_log)
        self.assertEquals(0, len(results))

    def test_multi_line(self):
        commit_log = "- 123456: Did something interesting.\n- Another commit.\n" \
            "- 456789: A third commit."
        results = extract_bzs(commit_log)
        self.assertEquals(2, len(results))
        self.assertEquals("Resolves: #123456 - Did something interesting.",
                results[0])
        self.assertEquals("Resolves: #456789 - A third commit.",
                results[1])

    def test_rpmbuild_cailms_to_be_successul(self):
        succeeded_result = "success"
        output = "Wrote: %s" % succeeded_result

        success_line = find_wrote_in_rpmbuild_output(output)

        self.assertEquals(succeeded_result, success_line[0])

    def test_rpmbuild_which_ended_with_error_is_described_with_the_analyzed_line(self):
        output = "some error output from rpmbuild\n" \
            "next error line"

        common.error_out = Mock()

        find_wrote_in_rpmbuild_output(output)

        common.error_out.assert_called_once_with("Unable to locate 'Wrote: ' lines in rpmbuild output: '%s'" % output)
