
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
Functional Tests for the YumReleaser.
"""

import glob
import os
import shutil
import tempfile

from os.path import join

from functional.fixture import TitoGitTestFixture, tito

from tito.compat import *  # NOQA
from tito.common import run_command


# There is not many simple options to check on what distribution this is running.
# Fortunately, we only need to check for Fedora Rawhide and EPEL6, so we can
# determine it from python version. This is compatible for all distributions.
import sys
is_rawhide = sys.version_info[:2] >= (3, 8)
is_epel6 = sys.version_info[:2] == (2, 6)

if is_epel6:
    import unittest2 as unittest
else:
    import unittest


PKG_NAME = "releaseme"

RELEASER_CONF = """
[yum-test]
releaser = tito.release.YumRepoReleaser
builder = tito.builder.Builder
srpm_disttag = .fc20
rsync = %s
"""


class YumReleaserTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)
        self.create_project(PKG_NAME)

        # Setup test config:
        self.config = RawConfigParser()
        self.config.add_section("buildconfig")
        self.config.set("buildconfig", "builder",
                "tito.builder.Builder")
        self.config.set("buildconfig", "offline",
                "true")

        self.output_dir = tempfile.mkdtemp("-titotestoutput")

    def tearDown(self):
        TitoGitTestFixture.tearDown(self)
        shutil.rmtree(self.output_dir)
        pass

    def _setup_fetchbuilder_releaser(self, yum_repo_dir):
        self.write_file(join(self.repo_dir, '.tito/releasers.conf'),
                RELEASER_CONF % yum_repo_dir)

    # createrepo_c (0.15.5+ which is in rawhide) currently coredumps
    # https://github.com/rpm-software-management/createrepo_c/issues/202
    @unittest.skipIf(is_rawhide, "Re-enable once createrepo_c #202 gets fixed")
    def test_with_releaser(self):
        yum_repo_dir = os.path.join(self.output_dir, 'yum')
        run_command('mkdir -p %s' % yum_repo_dir)
        self._setup_fetchbuilder_releaser(yum_repo_dir)
        tito('release --debug yum-test')

        self.assertEquals(1, len(glob.glob(join(yum_repo_dir,
            "releaseme-0.0.1-1.*noarch.rpm"))))
        self.assertEquals(1, len(glob.glob(join(yum_repo_dir,
            "repodata/repomd.xml"))))
