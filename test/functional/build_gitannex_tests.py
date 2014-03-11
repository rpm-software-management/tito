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
Functional Tests for the GitAnnexBuilder.
"""

import os
import glob
import tempfile
import shutil
from nose.plugins.skip import SkipTest
from os.path import join

from functional.fixture import TitoGitTestFixture, tito

from tito.compat import *
from tito.common import run_command
from tito.builder import GitAnnexBuilder

PKG_NAME = "extsrc"
GIT_ANNEX_MINIMUM_VERSION = '3.20130207'


class GitAnnexBuilderTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)

        # Guess based on python version.
        # Do not use anything based on uname in case we are in container.
        # Do not use `lsb_release` to avoid dependencies.
        if sys.version[0:3] == '2.4':
            raise SkipTest('git-annex is not available in epel-5')

        # git-annex needs to support --force when locking files.
        # rpm query is sub-optimal, but older versions do not support `git-annex version'.
        status, ga_version = getstatusoutput('rpm -q --qf=%{version} git-annex')
        if status != 0:
            raise SkipTest("git-annex is missing")
        if ga_version < GIT_ANNEX_MINIMUM_VERSION:
            raise SkipTest("git-annex '%s' is too old" % ga_version)

        # Setup test config:
        self.config = RawConfigParser()
        self.config.add_section("buildconfig")
        self.config.set("buildconfig", "builder",
                "tito.builder.GitAnnexBuilder")
        self.config.set("buildconfig", "offline",
                "true")

        os.chdir(self.repo_dir)
        spec = join(os.path.dirname(__file__), "specs/extsrc.spec")
        self.create_project_from_spec(PKG_NAME, self.config,
                spec=spec)
        self.source_filename = 'extsrc-0.0.2.tar.gz'

        # Make a fake source file, do we need something more real?
        run_command('touch %s' % self.source_filename)
        print(run_command('git-annex init'))

        self.output_dir = tempfile.mkdtemp("-titotestoutput")

    def tearDown(self):
        run_command('chmod -R u+rw %s' % self.output_dir)
        shutil.rmtree(self.output_dir)
        TitoGitTestFixture.tearDown(self)

    def test_simple_build(self):
        run_command('git annex add %s' % self.source_filename)
        run_command('git commit -a -m "Add source."')
        # This will create 0.0.2:
        tito('tag --debug --accept-auto-changelog')
        builder = GitAnnexBuilder(PKG_NAME, None, self.output_dir,
            self.config, {}, {}, **{'offline': True})
        builder.rpm()
        self.assertEquals(1, len(builder.sources))

        self.assertEquals(2, len(builder.artifacts))
        self.assertEquals(1, len(glob.glob(join(self.output_dir,
            "extsrc-0.0.2-1.*src.rpm"))))
        self.assertEquals(1, len(glob.glob(join(self.output_dir, 'noarch',
            "extsrc-0.0.2-1.*.noarch.rpm"))))
