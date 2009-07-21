#!/usr/bin/env python
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
"""
Executes all tests.
"""

import sys
import os
import os.path

import unittest

# Make sure we run from the source code and not a version of tito 
# installed on the system:
TEST_SCRIPT_DIR = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(TEST_SCRIPT_DIR, "../src/"))
SRC_SCRIPT_DIR = sys.path.append(os.path.join(TEST_SCRIPT_DIR, "../bin/"))

import spacewalk.releng.cli # prevents a circular import
from spacewalk.releng.common import *

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_GIT_LOCATION = '/tmp/tito-test-git-repo'

def tito(argstring):
    """ Run the tito script from source with given arguments. """
    run_command("%s/%s %s" % (SRC_SCRIPT_DIR, 'tito', argstring))

class InitTests(unittest.TestCase):

    def test_something(self):
        pass



if __name__ == '__main__':
    print("Running tito tests.")

    if os.path.exists(TEST_GIT_LOCATION):
        #error_out("Test Git repo already exists: %s" % TEST_GIT_LOCATION)
        run_command('rm -rf %s' % TEST_GIT_LOCATION)

    run_command('mkdir -p %s' % TEST_GIT_LOCATION)
    run_command('cp -R %s/* %s' % (os.path.join(TEST_SCRIPT_DIR,
        'fakegitfiles'), TEST_GIT_LOCATION))
    os.chdir(TEST_GIT_LOCATION)
    run_command('git init')
    run_command('git add a.txt')
    run_command('git commit -a -m "added a.txt"')
    run_command('git add b.txt')
    run_command('git commit -a -m "added b.txt"')
    run_command('git add c.txt')
    run_command('git commit -a -m "added c.txt"')

    # Now run the tests, order is important:
    suite = unittest.makeSuite(InitTests)
    result = unittest.TestResult()
    suite.run(result)
    print(result.errors)
    print(result.failures)
    print(result.wasSuccessful())


