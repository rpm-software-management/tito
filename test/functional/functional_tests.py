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

import unittest

from tito.common import check_tag_exists, commands, run_command, \
        get_latest_tagged_version, tag_exists_locally
from fixture import *


# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.

TEST_PKG_1 = 'tito-test-pkg'
TEST_PKG_1_DIR = "%s/" % TEST_PKG_1

TEST_PKG_2 = 'tito-test-pkg2'
TEST_PKG_2_DIR = "%s/" % TEST_PKG_2

TEST_PKG_3 = 'tito-test-pkg3'
TEST_PKG_3_DIR = "blah/whatever/%s/" % TEST_PKG_3

TEST_PKGS = [TEST_PKG_1, TEST_PKG_2, TEST_PKG_3]

def release_bumped(initial_version, new_version):
    first_release = initial_version.split('-')[-1]
    new_release = new_version.split('-')[-1]
    return new_release == str(int(first_release) + 1)

class MultiProjectTaggerTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)

        self.create_project(TEST_PKG_1, os.path.join(self.repo_dir, 'pkg1'))
        self.create_project(TEST_PKG_2, os.path.join(self.repo_dir, 'pkg2'))
        self.create_project(TEST_PKG_3, os.path.join(self.repo_dir, 'pkg3'))
        os.chdir(self.repo_dir)

        # For second test package, use a tito.props to override and use the 
        # ReleaseTagger:
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        filename = os.path.join(self.repo_dir, 'pkg2', "tito.props")
        out_f = open(filename, 'w')
        out_f.write("[buildconfig]\n")
        out_f.write("tagger = tito.tagger.ReleaseTagger\n")
        out_f.write("builder = tito.builder.Builder\n")
        out_f.close()
        index = self.repo.index
        index.add(['pkg2/tito.props'])
        index.commit("Adding tito.props for pkg2.")

    def test_initial_tag_keep_version(self):
        # Tags were actually created in setup code:
        for pkg_name in TEST_PKGS:
            self.assertTrue(tag_exists_locally("%s-0.0.1-1" % pkg_name))
            self.assertTrue(os.path.exists(os.path.join(self.repo_dir, 
                "rel-eng/packages", pkg_name)))

    def test_release_tagger(self):
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        start_ver = get_latest_tagged_version(TEST_PKG_2)
        tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertTrue(release_bumped(start_ver, new_ver))

    def test_release_tagger_legacy_props_file(self):
        # Test that build.py.props filename is still picked up:
        os.chdir(os.path.join(self.repo_dir, 'pkg2'))
        start_ver = get_latest_tagged_version(TEST_PKG_2)
        run_command("git mv tito.props build.py.props")
        index = self.repo.index
        index.add(['pkg2/build.py.props'])
        index.commit("Rename to build.py.props.")

        tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertTrue(release_bumped(start_ver, new_ver))


