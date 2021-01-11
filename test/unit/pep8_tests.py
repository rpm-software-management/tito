#
# Copyright (c) 2008-2014 Red Hat, Inc.
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

"""
Use pep8 to check for errors or deprecations that can cause Python 3 to fail.
source: https://github.com/jcrocholl/pep8
docs:   http://pep8.readthedocs.org/en/latest/intro.html

Python 3 is picky about indentation:
http://docs.python.org/3.3/reference/lexical_analysis.html
"""

try:
    # python-pep8 package is retired in Fedora because upstream
    # moved to pycodestyle. Please see
    # https://bugzilla.redhat.com/show_bug.cgi?id=1667200
    import pep8
except ImportError:
    import pycodestyle as pep8


from tito.compat import *  # NOQA
from tito.compat import StringIO, redirect_stdout
from unit.fixture import TitoUnitTestFixture, REPO_DIR


class TestPep8(TitoUnitTestFixture):
    def setUp(self):
        TitoUnitTestFixture.setUp(self)

    def test_conformance(self):
        tests = [
            # http://pep8.readthedocs.org/en/latest/intro.html#error-codes
            'E101',  # indentation contains mixed spaces and tabs
            'E111',  # indentation is not a multiple of four
            'E112',  # expected an indented block
            'E113',  # unexpected indentation
            'E121',  # continuation line indentation is not a multiple of four
            'E122',  # continuation line missing indentation or outdented
            'E126',  # continuation line over-indented for hanging indent
            'E2',    # whitespace errors
            'E3',    # blank line errors
            'E4',    # import errors
            'E502',  # the backslash is redundant between brackets
            'E9',    # runtime errors (SyntaxError, IndentationError, IOError)
            'W1',    # indentation warnings
            'W2',    # whitespace warnings
            'W3',    # blank line warnings

            # @FIXME we currently have a lot of these errors introduced to our
            # codebase. Let's temporarily disable the check, so we can get travis
            # working again.
            # 'E7',    # statement errors
            # 'W6',    # deprecated features
        ]

        try:
            checker = pep8.StyleGuide(select=tests, paths=[REPO_DIR], reporter=pep8.StandardReport)
            # Unfortunatelly, IMHO the most interesting information
            # `checker.check_files()` prints to the STDOUT and doesn't provide
            # API to get it - the list of _bad_ files. Let's just read it from
            # the output
            with StringIO() as buf, redirect_stdout(buf):
                report = checker.check_files()
                result = report.total_errors
                output = buf.getvalue()

        except AttributeError:
            # We don't have pep8.StyleGuide, so we must be
            # using pep8 older than git tag 1.1-72-gf20d656.
            os.chdir(REPO_DIR)
            checks = ','.join(tests)
            cmd = "pep8 --select=%s %s | wc -l" % (checks, '.')
            result = int(getoutput(cmd))
            output = getoutput("pep8 --select %s %s" % (checks, '.'))

        if result != 0:
            self.fail("Found PEP8 errors that may break your code in Python 3:\n%s" % output)


class UglyHackishTest(TitoUnitTestFixture):
    def setUp(self):
        TitoUnitTestFixture.setUp(self)
        os.chdir(REPO_DIR)

    def test_exceptions_3(self):
        # detect 'except rpm.error, e:'
        regex = "'^[[:space:]]*except [^,]+,[[:space:]]*[[:alpha:]]+:'"
        cmd = "find . -type f -regex '.*\.py$' -exec egrep %s {} + | wc -l" % regex
        result = int(getoutput(cmd))
        self.assertEqual(result, 0, "Found except clause not supported in Python 3")

    def test_import_commands(self):
        cmd = "find . -type f -regex '.*\.py$' -exec egrep '^(import|from) commands\.' {} + | grep -v 'compat\.py' | wc -l"
        result = int(getoutput(cmd))
        self.assertEqual(result, 0, "Found commands module (not supported in Python 3)")

    def test_use_commands(self):
        cmd = "find . -type f -regex '.*\.py$' -exec egrep 'commands\.' {} + | grep -v 'compat\.py' | wc -l"
        result = int(getoutput(cmd))
        self.assertEqual(result, 0, "Found commands module (not supported in Python 3)")

    def test_print_function(self):
        cmd = "find . -type f -regex '.*\.py$' -exec grep '^[[:space:]]*print .*' {} + | wc -l"
        result = int(getoutput(cmd))
        self.assertEqual(result, 0, "Found print statement (not supported in Python 3)")
