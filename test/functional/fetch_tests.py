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
Functional Tests for the FetchBuilder.
"""

import glob
import os
import sys
import shutil
import tempfile

from os.path import join

from tito.common import run_command
from tito.compat import *  # NOQA
from functional.fixture import TitoGitTestFixture, tito
from unit import Capture, is_epel6, is_rawhide

if is_epel6:
    import unittest2 as unittest
else:
    import unittest


EXT_SRC_PKG = "extsrc"

RELEASER_CONF = """
[yum-test]
releaser = tito.release.YumRepoReleaser
builder = tito.builder.FetchBuilder
srpm_disttag = .fc20
rsync = %s
"""


class FetchBuilderTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)
        self.pkg_dir = join(self.repo_dir, EXT_SRC_PKG)

        specname = "extsrc-3.spec" if sys.version_info[0] == 3 else "extsrc-2.spec"
        spec = join(os.path.dirname(__file__), "specs", specname)
        shutil.copyfile(spec, os.path.join(self.repo_dir, "extsrc.spec"))
        spec = join(self.repo_dir, "extsrc.spec")

        # Setup test config:
        self.config = RawConfigParser()
        self.config.add_section("buildconfig")
        self.config.set("buildconfig", "builder",
                "tito.builder.FetchBuilder")

        self.config.add_section('builder')
        self.config.set('builder', 'fetch_strategy',
                'tito.builder.fetch.ArgSourceStrategy')

        self.create_project_from_spec(EXT_SRC_PKG, self.config,
                pkg_dir=self.pkg_dir, spec=spec)
        self.source_filename = 'extsrc-0.0.2.tar.gz'
        os.chdir(self.pkg_dir)

        # Make a fake source file, do we need something more real?
        run_command('touch %s' % self.source_filename)

        self.output_dir = tempfile.mkdtemp("-titotestoutput")

    def tearDown(self):
        TitoGitTestFixture.tearDown(self)
        # Git annex restricts permissions, change them before we remove:
        shutil.rmtree(self.output_dir)

    def test_simple_build_no_tag(self):
        # We have not tagged here. Build --rpm should just work:
        self.assertFalse(os.path.exists(
            join(self.pkg_dir, '.tito/packages/extsrc')))

        tito('build --rpm --output=%s --no-cleanup --debug --arg=source=%s ' %
                (self.output_dir, self.source_filename))
        self.assertEquals(1, len(glob.glob(join(self.output_dir,
            "extsrc-0.0.2-1.*src.rpm"))))
        self.assertEquals(1, len(glob.glob(join(self.output_dir,
            "noarch/extsrc-0.0.2-1.*noarch.rpm"))))

    def test_tag_rejected(self):
        with Capture(silent=True):
            self.assertRaises(SystemExit, tito,
                    'build --tag=extsrc-0.0.1-1 --rpm --output=%s --arg=source=%s ' %
                    (self.output_dir, self.source_filename))

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
        tito('release --debug yum-test --arg source=%s' %
                self.source_filename)

        self.assertEquals(1, len(glob.glob(join(yum_repo_dir,
            "extsrc-0.0.2-1.*noarch.rpm"))))
        self.assertEquals(1, len(glob.glob(join(yum_repo_dir,
            "repodata/repomd.xml"))))
