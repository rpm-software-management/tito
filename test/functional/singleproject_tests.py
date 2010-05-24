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

import os
import shutil
import tempfile
import unittest

import git

from tito.common import *

from functional_tests import TEST_SPEC
from functional_tests import cleanup_temp_git, tito

#TITO_REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class SingleProjectTests(unittest.TestCase):

    def setUp(self):
        self.repo_dir = tempfile.mkdtemp("-titotest")
        print
        print
        print("Testing in: %s" % self.repo_dir)
        print
        pkg_name = 'tito-test-pkg'

        # Initialize the repo:
        repo = git.Repo.init(path=self.repo_dir, mkdir=True, bare=False)

        # Write some files to the test git repo:
        filename = os.path.join(self.repo_dir, "a.txt")
        out_f = open(filename, 'w')
        out_f.write("BLERG\n")
        out_f.close()

        # Write the test spec file:
        filename = os.path.join(self.repo_dir, "%s.spec" % pkg_name)
        out_f = open(filename, 'w')
        out_f.write("Name: %s" % pkg_name)
        out_f.write(TEST_SPEC)
        out_f.close()

        os.chdir(self.repo_dir)
        tito("init")
        run_command('echo "offline = true" >> rel-eng/tito.props')

        index = repo.index
        index.add(['a.txt', '%s.spec' % pkg_name], 'rel-eng/tito.props')
        index.commit('-a -m "Initial commit."')

        #g = git.cmd.Git(self.repo_dir)

        tito('tag --keep-version --debug --accept-auto-changelog')

    def tearDown(self):
        #shutil.rmtree(self.repo_dir)
        pass

    def test_init_worked(self):
        # Not actually running init here, just making sure it worked when 
        # run during setup.
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng",
            "tito.props")))

