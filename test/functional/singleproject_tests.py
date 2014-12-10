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
from tito.common import *
from tito.builder import *
from tito.release import Releaser
from functional.fixture import TitoGitTestFixture, tito

PKG_NAME = "titotestpkg"


class SingleProjectTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)

        self.create_project(PKG_NAME)
        os.chdir(self.repo_dir)

        self.config = RawConfigParser()
        self.config.add_section("buildconfig")
        self.config.set("buildconfig", "builder", "tito.builder.Builder")
        self.config.set("buildconfig", "offline", "true")

        self.releaser_config = RawConfigParser()
        self.releaser_config.add_section('test')
        self.releaser_config.set('test', 'releaser',
            'tito.release.Releaser')

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
        os.chdir(self.repo_dir)
        original_head = getoutput('git show-ref -s refs/heads/master')

        # Create tito tag, which adds a new commit and moves head.
        tito("tag --accept-auto-changelog --debug")
        tag = "%s-0.0.2-1" % PKG_NAME
        check_tag_exists(tag, offline=True)
        new_head = getoutput('git show-ref -s refs/heads/master')
        self.assertNotEqual(original_head, new_head)

        # Undo tito tag, which rewinds one commit to original head.
        tito("tag -u")
        self.assertFalse(tag_exists_locally(tag))
        new_head = getoutput('git show-ref -s refs/heads/master')
        self.assertEqual(original_head, new_head)

    def test_latest_tgz(self):
        tito("build --tgz -o %s" % self.repo_dir)

    def test_build_tgz_tag(self):
        tito("build --tgz --tag=%s-0.0.1-1 -o %s" % (PKG_NAME,
            self.repo_dir))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir,
            "%s-0.0.1.tar.gz" % PKG_NAME)))

    def test_build_latest_srpm(self):
        tito("build --srpm")

    def test_build_srpm_tag(self):
        tito("build --srpm --tag=%s-0.0.1-1 -o %s" % (PKG_NAME, self.repo_dir))

    def test_build_latest_rpm(self):
        tito("build --rpm -o %s" % self.repo_dir)

    def test_build_rpm_tag(self):
        tito("build --rpm --tag=%s-0.0.1-1 -o %s" % (PKG_NAME,
            self.repo_dir))

    def test_release(self):
        releaser = Releaser(PKG_NAME, None, '/tmp/tito/',
            self.config, {}, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        self.assertTrue(isinstance(releaser.builder, Builder))
        releaser.release(dry_run=True)

    def test_release_override_builder(self):
        self.releaser_config.set('test', 'builder',
            'tito.builder.UpstreamBuilder')
        releaser = Releaser(PKG_NAME, None, '/tmp/tito/',
            self.config, {}, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        self.assertTrue(isinstance(releaser.builder,
            UpstreamBuilder))
        releaser.release(dry_run=True)
