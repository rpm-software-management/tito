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

# Make sure we run from the source:
TEST_SCRIPT_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
print TEST_SCRIPT_DIR
SRC_DIR = os.path.normpath(os.path.join(TEST_SCRIPT_DIR, "../src/"))
SRC_BIN_DIR = os.path.abspath(os.path.join(TEST_SCRIPT_DIR, "../bin/"))

import spacewalk.releng.cli # prevents a circular import
from spacewalk.releng.common import *

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_DIR = '/tmp/titotests/'
SINGLE_GIT = os.path.join(TEST_DIR, 'single-project')
MULTI_GIT = os.path.join(TEST_DIR, 'multi-project')

def tito(argstring):
    """ Run the tito script from source with given arguments. """
    run_command("%s/%s %s" % (SRC_BIN_DIR, 'tito', argstring))

def cleanup_test_git_repos():
    """ Delete the test directory if it exists. """
    if os.path.exists(TEST_DIR):
        #error_out("Test Git repo already exists: %s" % TEST_DIR)
        run_command('rm -rf %s' % TEST_DIR)

def create_test_git_repo(multi_project=False):
    """ Create a test git repository. """
    cleanup_test_git_repos()

    run_command('mkdir -p %s' % TEST_DIR)
    run_command('mkdir -p %s' % SINGLE_GIT)
    run_command('mkdir -p %s' % MULTI_GIT)

    run_command('cp -R %s/* %s' % (os.path.join(TEST_SCRIPT_DIR,
        'fakegitfiles'), SINGLE_GIT))
    os.chdir(SINGLE_GIT)
    run_command('git init')
    run_command('git add a.txt')
    run_command('git add b.txt')
    run_command('git add c.txt')
    #run_command('git add tito-test-pkg.spec')
    run_command('git commit -a -m "Initial commit."')



class InitTests(unittest.TestCase):

    def test_init(self):
        # Probably already there but just to make sure:
        os.chdir(SINGLE_GIT)
        self.assertFalse(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        tito("init")
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "tito.props")))


class TaggerTests(unittest.TestCase):

    def test_tag_new_package(self):
        tito("tag")


if __name__ == '__main__':
    print("Running tito tests.")

    create_test_git_repo()

    suites = [
            unittest.makeSuite(InitTests),
            unittest.makeSuite(TaggerTests),
    ]
    # Now run the tests, order is important:
    suite = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=2).run(suite)
