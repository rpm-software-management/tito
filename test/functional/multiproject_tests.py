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
"""
Functional Tests for Tito at the CLI level.

NOTE: These tests require a makeshift git repository created in /tmp.
"""

import os
from os.path import join

from tito.common import run_command, \
    get_latest_tagged_version, tag_exists_locally
from functional.fixture import TitoGitTestFixture, tito

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.

TEST_PKG_1 = 'titotestpkg'

TEST_PKG_2 = 'titotestpkg2'

TEST_PKG_3 = 'titotestpkg3'

TEST_PKGS = [TEST_PKG_1, TEST_PKG_2, TEST_PKG_3]


def release_bumped(initial_version, new_version):
    first_release = initial_version.split('-')[-1]
    new_release = new_version.split('-')[-1]
    return new_release == str(int(first_release) + 1)


TEMPLATE_TAGGER_TITO_PROPS = """
[buildconfig]
tagger = tito.tagger.VersionTagger
builder = tito.builder.Builder

[version_template]
destination_file = version.txt
template_file = .tito/templates/version.rb
"""

VERSION_TEMPLATE_FILE = """
module Iteng
    module Util
      VERSION = "$version-$release"
    end
  end
"""


class MultiProjectTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)

        self.create_project(TEST_PKG_1, os.path.join(self.repo_dir, 'pkg1'))
        self.create_project(TEST_PKG_2, os.path.join(self.repo_dir, 'pkg2'))
        self.create_project(TEST_PKG_3, os.path.join(self.repo_dir, 'pkg3'))

        # For second test package, use a tito.props to override and use the
        # ReleaseTagger:
        filename = os.path.join(self.repo_dir, 'pkg2', "tito.props")
        out_f = open(filename, 'w')
        out_f.write("[buildconfig]\n")
        out_f.write("tagger = tito.tagger.ReleaseTagger\n")
        out_f.write("builder = tito.builder.Builder\n")
        out_f.close()

        os.chdir(self.repo_dir)
        run_command('git add pkg2/tito.props')
        run_command("git commit -m 'add tito.props for pkg2'")

    def test_template_version_tagger(self):
        """
        Make sure the template is applied and results in the correct file
        being included in the tag.
        """
        pkg_dir = join(self.repo_dir, 'pkg3')
        filename = join(pkg_dir, "tito.props")
        self.write_file(filename, TEMPLATE_TAGGER_TITO_PROPS)
        run_command('mkdir -p %s' % join(self.repo_dir, '.tito/templates'))
        self.write_file(join(self.repo_dir,
            '.tito/templates/version.rb'), VERSION_TEMPLATE_FILE)

        os.chdir(self.repo_dir)
        run_command('git add pkg3/tito.props')
        run_command("git commit -m 'add tito.props for pkg3'")

        # Create another pkg3 tag and make sure we got a generated
        # template file.
        os.chdir(os.path.join(self.repo_dir, 'pkg3'))
        tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_3)
        self.assertEquals("0.0.2-1", new_ver)

        dest_file = os.path.join(self.repo_dir, 'pkg3', "version.txt")
        self.assertTrue(os.path.exists(dest_file))

        f = open(dest_file, 'r')
        contents = f.read()
        f.close()

        self.assertTrue("VERSION = \"0.0.2-1\"" in contents)

    def test_initial_tag_keep_version(self):
        # Tags were actually created in setup code:
        for pkg_name in TEST_PKGS:
            self.assertTrue(tag_exists_locally("%s-0.0.1-1" % pkg_name))
            self.assertTrue(os.path.exists(os.path.join(self.repo_dir,
                ".tito/packages", pkg_name)))

    def test_release_tagger(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        start_ver = get_latest_tagged_version(TEST_PKG_2)
        tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertTrue(release_bumped(start_ver, new_ver))

    def test_release_tagger_use_release(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        tito('tag --debug --accept-auto-changelog --use-release 42')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertEquals(new_ver.split('-')[-1], "42")

    def test_release_tagger_use_version(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        start_ver = get_latest_tagged_version(TEST_PKG_2)
        tito('tag --debug --accept-auto-changelog --use-version 1.3.37')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertFalse(release_bumped(start_ver, new_ver))
        self.assertEquals(new_ver, "1.3.37-1")

    def test_build_tgz(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg1'))
        artifacts = tito('build --tgz')
        self.assertEquals(1, len(artifacts))
        self.assertEquals('%s-0.0.1.tar.gz' % TEST_PKG_1,
                os.path.basename(artifacts[0]))

    def test_build_rpm(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg1'))
        artifacts = tito('build --rpm')
        self.assertEquals(3, len(artifacts))
