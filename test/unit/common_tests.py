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
from tito.common import (replace_version, find_spec_like_file, increase_version,
    search_for, compare_version, run_command_print, find_wrote_in_rpmbuild_output,
    render_cheetah, increase_zstream, reset_release, find_file_with_extension,
    normalize_class_name, extract_sha1, DEFAULT_BUILD_DIR, munge_specfile,
    munge_setup_macro, get_project_name,
    _out)

from tito.compat import StringIO
from tito.tagger import CargoBump

import os
import re
import unittest

from mock import Mock, patch, call
from tempfile import NamedTemporaryFile
from textwrap import dedent
from unit import open_mock, Capture
from blessed import Terminal


class CommonTests(unittest.TestCase):
    def setUp(self):
        # Start in a known location to prevent problems with tests that
        # end in a temp directory that is subsequently deleted.
        os.chdir(DEFAULT_BUILD_DIR)

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

    def test_compare_version(self):
        self.assertEquals(0, compare_version("1", "1"))
        self.assertTrue(compare_version("2.1", "2.2") < 0)
        self.assertTrue(compare_version("3.0.4.10", "3.0.4.2") > 0)
        self.assertTrue(compare_version("4.08", "4.08.01") < 0)
        self.assertTrue(compare_version("3.2.1.9.8144", "3.2") > 0)
        self.assertTrue(compare_version("3.2", "3.2.1.9.8144") < 0)
        self.assertTrue(compare_version("1.2", "2.1") < 0)
        self.assertTrue(compare_version("2.1", "1.2") > 0)
        self.assertTrue(compare_version("1.0", "1.0.1") < 0)
        self.assertTrue(compare_version("1.0.1", "1.0") > 0)
        self.assertEquals(0, compare_version("5.6.7", "5.6.7"))
        self.assertEquals(0, compare_version("1.01.1", "1.1.1"))
        self.assertEquals(0, compare_version("1.1.1", "1.01.1"))
        self.assertEquals(0, compare_version("1", "1.0"))
        self.assertEquals(0, compare_version("1.0", "1"))
        self.assertEquals(0, compare_version("1.0.2.0", "1.0.2"))

    def test_run_command_print(self):
        self.assertEquals('', run_command_print("sleep 0.1"))

    def test_rpmbuild_claims_to_be_successful(self):
        succeeded_result = "success"
        output = "Wrote: %s" % succeeded_result

        success_line = find_wrote_in_rpmbuild_output(output)

        self.assertEquals(succeeded_result, success_line[0])

    @patch("tito.common.error_out")
    def test_rpmbuild_which_ended_with_error_is_described_with_the_analyzed_line(self, mock_error):
        output = "some error output from rpmbuild\n" \
            "next error line"

        find_wrote_in_rpmbuild_output(output)

        mock_error.assert_called_once_with("Unable to locate 'Wrote: ' lines in rpmbuild output: '%s'" % output)

    @patch("tito.common.find_file_with_extension")
    def test_find_spec_like_file_tmpl(self, mock_find):
        mock_find.side_effect = [None, "result.spec.tmpl"]
        result = find_spec_like_file()
        self.assertEquals("result.spec.tmpl", result)
        self.assertEquals(2, len(mock_find.mock_calls))

    @patch("tito.common.find_file_with_extension")
    def test_find_spec_like_file_spec(self, mock_find):
        mock_find.side_effect = ["result.spec"]
        result = find_spec_like_file()
        self.assertEquals("result.spec", result)
        self.assertEquals(1, len(mock_find.mock_calls))

    @patch("tito.common.find_file_with_extension")
    def test_find_spec_like_file_no_match(self, mock_find):
        mock_find.side_effect = [None, None]
        with Capture(silent=True):
            self.assertRaises(SystemExit, find_spec_like_file)
            self.assertEquals(2, len(mock_find.mock_calls))

    @patch("os.listdir")
    def test_find_file_with_extension(self, mock_listdir):
        mock_listdir.return_value = ["hello.txt"]
        result = find_file_with_extension("/tmp", ".txt")
        self.assertEquals(mock_listdir.mock_calls[0], call("/tmp"))
        self.assertEquals("/tmp/hello.txt", result)

    @patch("os.listdir")
    def test_find_file_with_extension_no_match(self, mock_listdir):
        mock_listdir.return_value = ["hello.txt"]
        result = find_file_with_extension("/tmp", ".foo")
        self.assertEquals(mock_listdir.mock_calls[0], call("/tmp"))
        self.assertEqual(None, result)

    @patch("os.listdir")
    def test_find_file_with_extension_duplicates(self, mock_listdir):
        mock_listdir.return_value = ["hello.txt", "goodbye.txt"]
        with Capture(silent=True):
            self.assertRaises(SystemExit, find_file_with_extension, "/tmp", ".txt")

    def test_search_for(self):
        content = dedent("""
        HelloWorld
        Hello World
        """)
        with open_mock(content):
            results = search_for("foo", r"(Hello\s+World)", r"(HelloWorld)")
            self.assertEquals(("Hello World",), results[0])
            self.assertEquals(("HelloWorld",), results[1])

    def test_search_for_gets_first_match(self):
        content = dedent("""
        HelloWorld
        Hello World
        """)
        with open_mock(content):
            results = search_for("foo", r"(Hello.*)")
            self.assertEquals(("HelloWorld",), results[0])

    def test_search_for_no_match(self):
        content = dedent("""
        HelloWorld
        Goodbye World
        """)
        with open_mock(content):
            with Capture(silent=True):
                self.assertRaises(SystemExit, search_for, "foo", r"(NoMatch)")

    @patch("tito.common.read_user_config")
    def test_turn_off_colors(self, mock_user_conf):
        mock_user_conf.return_value = {'COLOR': '0'}
        stream = StringIO()
        _out('Hello world', None, Terminal().red, stream)
        self.assertEquals('Hello world\n', stream.getvalue())

    @patch("tito.common.read_user_config")
    def test_colors(self, mock_user_conf):
        mock_user_conf.return_value = {}
        stream = StringIO()
        _out('Hello world', None, Terminal().red, stream)
        # RHEL 6 doesn't have self.assertRegexpMatches unfortunately
        self.assertTrue(re.match('.+Hello world.+\n', stream.getvalue()))

    def test_get_project_name(self):
        TAGS = [
            ('package-1.0-1', 'package'),
            ('package-1.0', 'package'),
            ('long-package-name-that-should-not-be-an-issue-0.1-1', 'long-package-name-that-should-not-be-an-issue'),
            ('package-with-weird-version-0.1-0.1.beta1', 'package-with-weird-version'),
            ('grub2-efi-ia32-1.0-1', 'grub2-efi-ia32'),
            ('iwl5150-firmware-1.0-1', 'iwl5150-firmware'),
            ('389-ds-base-1.0-1', '389-ds-base'),
            ('avr-gcc-c++-1.0-1', 'avr-gcc-c++'),
            ('java-1.8.0-openjdk-1.8.0.232.b09-0', 'java-1.8.0-openjdk'),
            ('jsr-305-0-0.25.20130910svn', 'jsr-305')
        ]

        for (tag, package) in TAGS:
            self.assertEquals(package, get_project_name(tag, None))


class CheetahRenderTest(unittest.TestCase):
    @patch("os.unlink")
    @patch("glob.glob")
    @patch("shutil.move")
    @patch("tito.common.run_command")
    @patch("tempfile.NamedTemporaryFile")
    def test_renders_cheetah(self, mock_tempfile, mock_run_command, mock_move, mock_glob, mock_unlink):
        mock_run_command.return_value = True
        mock_tempfile.return_value.name = "temp_pickle"
        mock_unlink.return_value = True
        mock_glob.return_value = ["/tmp/foo.spec.cheetah"]
        mock_move.return_value = True

        render_cheetah("foo.spec.tmpl", "/tmp", {})
        expected = "cheetah fill --flat --pickle=temp_pickle --odir=/tmp --oext=cheetah foo.spec.tmpl"
        self.assertEquals(call(expected), mock_run_command.mock_calls[0])
        self.assertEquals(call("/tmp/*.cheetah"), mock_glob.mock_calls[0])
        self.assertEquals(call("/tmp/foo.spec.cheetah", "/tmp/foo.spec"), mock_move.mock_calls[0])
        self.assertEquals(call("temp_pickle"), mock_unlink.mock_calls[0])

    @patch("os.unlink")
    @patch("glob.glob")
    @patch("tito.common.run_command")
    @patch("tempfile.NamedTemporaryFile")
    def test_renders_cheetah_missing_result(self, mock_tempfile, mock_run_command, mock_glob, mock_unlink):
        mock_run_command.return_value = True
        mock_tempfile.return_value.name = "temp_pickle"
        mock_unlink.return_value = True
        mock_glob.return_value = []

        with Capture(silent=True):
            self.assertRaises(SystemExit, render_cheetah, "foo.spec.tmpl", "/tmp", {})
            expected = "cheetah fill --flat --pickle=temp_pickle --odir=/tmp --oext=cheetah foo.spec.tmpl"
            self.assertEquals(call(expected), mock_run_command.mock_calls[0])

            self.assertEquals(call("/tmp/*.cheetah"), mock_glob.mock_calls[0])
            self.assertEquals(call("temp_pickle"), mock_unlink.mock_calls[0])


class CargoTransformTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_case(self):
        input = ['[package]',
                 'name = "hello_world" # the name of the package',
                 'version = "0.1.0"    # the current version, obeying semver',
                 'authors = ["you@example.com"]']
        output = CargoBump.process_cargo_toml(input, "2.2.2")

        self.assertEquals(4, len(output))
        self.assertEquals("[package]", output[0])
        self.assertEquals("name = \"hello_world\" # the name of the package", output[1])
        self.assertEquals("version = \"2.2.2\"    # the current version, obeying semver", output[2])
        self.assertEquals("authors = [\"you@example.com\"]", output[3])

    def test_complicated_case(self):
        input = ['[package]',
                 'name = "hello_world"',
                 'version = "2.2.2"',
                 'authors = ["you@example.com"]',
                 '',
                 '[dependencies]',
                 'regex = "1.0.0"',
                 '',
                 '[dependencies.termion]',
                 'version = "0.1.0"']
        output = CargoBump.process_cargo_toml(input, "3.3.3")

        self.assertEquals(10, len(output))
        self.assertEquals("version = \"3.3.3\"", output[2])
        self.assertEquals("regex = \"1.0.0\"", output[6])
        self.assertEquals("version = \"0.1.0\"", output[9])


class SpecTransformTest(unittest.TestCase):
    def setUp(self):
        self.spec_file = NamedTemporaryFile(delete=False).name

    def tearDown(self):
        os.unlink(self.spec_file)

    def test_simple_transform(self):
        simple_spec = dedent("""
        Name: Hello
        Version: 1.0.0
        Release: 1%{?dist}
        Source: hello-1.0.0.tar.gz

        %prep
        %setup -q
        """)
        with open(self.spec_file, 'w') as f:
            f.write(simple_spec)

        sha = "acecafe"
        commit_count = 5
        display_version = "git-%s.%s" % (commit_count, sha)
        fullname = "hello-%s" % display_version
        munge_specfile(self.spec_file, sha, commit_count, fullname, "%s.tar.gz" % fullname)
        output = open(self.spec_file, 'r').readlines()

        self.assertEquals(8, len(output))
        self.assertEquals("Release: 1.git.%s.%s%%{?dist}\n" % (commit_count, sha), output[3])
        self.assertEquals("Source: %s.tar.gz\n" % fullname, output[4])
        self.assertEquals("%%setup -q -n %s\n" % fullname, output[7])

        # Spot check some things that should not change
        self.assertEquals("Name: Hello\n", output[1])
        self.assertEqual("%prep\n", output[6])

    def test_transform_release_only(self):
        simple_spec = dedent("""
        Release: 1%{?dist}
        Source: hello-1.0.0.tar.gz
        %setup -q
        """)
        with open(self.spec_file, 'w') as f:
            f.write(simple_spec)

        sha = "acecafe"
        commit_count = 5
        munge_specfile(self.spec_file, sha, commit_count)
        output = open(self.spec_file, 'r').readlines()

        self.assertEquals(4, len(output))
        self.assertEquals("Release: 1.git.%s.%s%%{?dist}\n" % (commit_count, sha), output[1])
        self.assertEquals("Source: hello-1.0.0.tar.gz\n", output[2])
        self.assertEquals("%setup -q\n", output[3])

    def test_transform_no_whitespace_modifications(self):
        simple_spec = dedent("""
        Release:    1%{?dist}
        Source:     hello-1.0.0.tar.gz
        """)
        with open(self.spec_file, 'w') as f:
            f.write(simple_spec)

        sha = "acecafe"
        commit_count = 5
        munge_specfile(self.spec_file, sha, commit_count)
        output = open(self.spec_file, 'r').readlines()

        self.assertEquals(3, len(output))
        self.assertEquals("Release:    1.git.%s.%s%%{?dist}\n" % (commit_count, sha), output[1])
        self.assertEquals("Source:     hello-1.0.0.tar.gz\n", output[2])

    def test_complex_setup_transform(self):
        simple_spec = dedent("""
        %setup -q -n hello-1
        """)
        with open(self.spec_file, 'w') as f:
            f.write(simple_spec)

        sha = "acecafe"
        commit_count = 5
        display_version = "git-%s.%s" % (commit_count, sha)
        fullname = "hello-%s" % display_version
        munge_specfile(self.spec_file, sha, commit_count, fullname, "%s.tar.gz" % fullname)
        output = open(self.spec_file, 'r').readlines()

        self.assertEquals("%%setup -q -n %s\n" % fullname, output[1])

    def test_transform_no_dist_tag(self):
        simple_spec = dedent("""
        Release: 1
        Source: hello-1.0.0.tar.gz
        """)
        with open(self.spec_file, 'w') as f:
            f.write(simple_spec)

        sha = "acecafe"
        commit_count = 5
        munge_specfile(self.spec_file, sha, commit_count)
        output = open(self.spec_file, 'r').readlines()

        self.assertEquals(3, len(output))
        self.assertEquals("Release: 1.git.%s.%s\n" % (commit_count, sha), output[1])
        self.assertEquals("Source: hello-1.0.0.tar.gz\n", output[2])


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


class MungeSetupMacroTests(unittest.TestCase):
    SOURCE = "tito-git-3.20362dd"

    def test_setup(self):
        line = "%setup -q -n tito-%{version}"
        self.assertEqual("%setup -q -n " + self.SOURCE,
                         munge_setup_macro(self.SOURCE, line))

    def test_autosetup(self):
        line = "%autosetup -n tito-%{version}"
        self.assertEqual("%autosetup -n " + self.SOURCE + " -p1",
                         munge_setup_macro(self.SOURCE, line))
