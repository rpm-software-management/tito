#
# Copyright (c) 2008-2010 Red Hat, Inc.
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

from tito.common import *
from fixture import TitoGitTestFixture, tito

#TITO_REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
PKG_NAME = "titotestpkg"


class SingleProjectTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)

        self.create_project(PKG_NAME)
        os.chdir(self.repo_dir)

    def tearDown(self):
        shutil.rmtree(self.repo_dir)
        pass

    def test_init_worked(self):
        # Not actually running init here, just making sure it worked when
        # run during setup.
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, "rel-eng",
            "tito.props")))

    def test_initial_tag(self):
        self.assertTrue(tag_exists_locally("%s-0.0.1-1" % PKG_NAME))

    def test_tag(self):
        tito("tag --accept-auto-changelog --debug")
        check_tag_exists("%s-0.0.2-1" % PKG_NAME, offline=True)

    def test_tag_with_version(self):
        tito("tag --accept-auto-changelog --debug --use-version 9.0.0")
        check_tag_exists("%s-9.0.0-1" % PKG_NAME, offline=True)

    def test_undo_tag(self):
        commit = self.repo.heads.master.commit
        tito("tag --accept-auto-changelog --debug")
        tag = "%s-0.0.2-1" % PKG_NAME
        check_tag_exists(tag, offline=True)
        self.assertNotEqual(commit, self.repo.heads.master.commit)
        tito("tag -u")
        self.assertFalse(tag_exists_locally(tag))
        self.assertEqual(commit, self.repo.heads.master.commit)

    def test_latest_tgz(self):
        tito("build --tgz -o %s" % self.repo_dir)

    def test_tag_tgz(self):
        tito("build --tgz --tag=%s-0.0.1-1 -o %s" % (PKG_NAME,
            self.repo_dir))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir,
            "%s-0.0.1.tar.gz" % PKG_NAME)))

    def test_latest_srpm(self):
        tito("build --srpm")

    def test_tag_srpm(self):
        tito("build --srpm --tag=%s-0.0.1-1 -o %s" % (PKG_NAME, self.repo_dir))

    def test_latest_rpm(self):
        tito("build --rpm -o %s" % self.repo_dir)

    def test_tag_rpm(self):
        tito("build --rpm --tag=%s-0.0.1-1 -o %s" % (PKG_NAME,
            self.repo_dir))
