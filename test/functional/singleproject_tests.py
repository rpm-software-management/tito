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
from tito.builder import Builder, UpstreamBuilder
from tito.common import tag_exists_locally, check_tag_exists
from tito.release import Releaser
from tito.compat import getoutput
from functional.fixture import TitoGitTestFixture, tito
from tito.compat import RawConfigParser
from unit import Capture

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
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, ".tito")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, ".tito",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(self.repo_dir, ".tito",
            "tito.props")))

    def test_initial_tag(self):
        self.assertTrue(tag_exists_locally("%s-0.0.1-1" % PKG_NAME))

    def test_tag(self):
        tito("tag --accept-auto-changelog --debug")
        check_tag_exists("%s-0.0.2-1" % PKG_NAME, offline=True)

    def test_tag_with_version(self):
        tito("tag --accept-auto-changelog --debug --use-version 9.0.0")
        check_tag_exists("%s-9.0.0-1" % PKG_NAME, offline=True)

    def test_tag_with_release(self):
        tito("tag --accept-auto-changelog --debug --use-release dummyvalue")
        check_tag_exists("%s-0.0.2-dummyvalue" % PKG_NAME, offline=True)

    def test_tag_with_version_and_release(self):
        tito("tag --accept-auto-changelog --debug --use-version 9.0.0 --use-release dummyvalue")
        check_tag_exists("%s-9.0.0-dummyvalue" % PKG_NAME, offline=True)

    def test_tag_with_changelog(self):
        tito("tag --accept-auto-changelog --use-version 9.0.0 --changelog='-Test'")
        check_tag_exists("%s-9.0.0-1" % PKG_NAME, offline=True)

        changelog = getoutput("cat *.spec")
        self.assertTrue('-Test' in changelog)

    def test_tag_with_changelog_format(self):
        tito("tag --accept-auto-changelog --use-version 9.0.0 --changelog=Test")
        check_tag_exists("%s-9.0.0-1" % PKG_NAME, offline=True)

        changelog = getoutput("cat *.spec")
        self.assertTrue('- Test' in changelog)

    def test_tag_with_changelog_multiple(self):
        tito("tag --accept-auto-changelog --use-version 9.0.0 --changelog=Test --changelog=Fake")
        check_tag_exists("%s-9.0.0-1" % PKG_NAME, offline=True)

        changelog = getoutput("cat *.spec")
        self.assertTrue('- Test' in changelog)
        self.assertTrue('- Fake' in changelog)

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

    def test_tag_with_custom_message(self):
        os.chdir(self.repo_dir)
        with open(os.path.join(self.repo_dir, '.tito', 'tito.props'), 'a') as f:
            f.write('tag_commit_message_format = No info plz\n')

        tito("tag --accept-auto-changelog")

        last_msg = getoutput('git log -n 1 --pretty=format:%s')
        self.assertEqual('No info plz', last_msg.strip())

    def test_tag_with_custom_message_bad_placeholder(self):
        os.chdir(self.repo_dir)
        with open(os.path.join(self.repo_dir, '.tito', 'tito.props'), 'a') as f:
            f.write('tag_commit_message_format = %(ultimate_answer)s\n')

        with Capture(silent=True) as capture:
            self.assertRaises(SystemExit, tito, "tag --accept-auto-changelog")
        self.assertTrue("Unknown placeholder 'ultimate_answer' in tag_commit_message_format" in
                      capture.err)

    def test_tag_with_custom_message_containing_quotes(self):
        os.chdir(self.repo_dir)
        with open(os.path.join(self.repo_dir, '.tito', 'tito.props'), 'a') as f:
            f.write('tag_commit_message_format = Hack"%(name)s\\\n')

        tito("tag --accept-auto-changelog")

        last_msg = getoutput('git log -n 1 --pretty=format:%s')
        self.assertEqual('Hack"titotestpkg\\', last_msg.strip())

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
