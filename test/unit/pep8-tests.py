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

import pep8
from fixture import *


class TestPep8(TitoUnitTestFixture):
    def setUp(self):
        TitoUnitTestFixture.setUp(self)

    def test_conformance(self):
        tests = [
            # http://pep8.readthedocs.org/en/latest/intro.html#error-codes
            'E2',    # whitespace errors
            'E9',    # runtime errors (SyntaxError, IndentationError, IOError)
            'W2',    # whitespace warnings
            'W6',    # deprecated features
        ]

        try:
            checker = pep8.StyleGuide(select=tests, paths=[REPO_DIR])
            result = checker.check_files().total_errors
        except AttributeError:
            # We don't have pep8.StyleGuide, so we must be
            # using pep8 older than git tag 1.1-72-gf20d656.
            os.chdir(REPO_DIR)
            checks = ','.join(tests)
            cmd = "pep8 --select=%s %s | wc -l" % (checks, '.')
            result = int(getoutput(cmd))

        self.assertEqual(result, 0,
            "Found PEP8 errors that may break your code in Python 3.")
