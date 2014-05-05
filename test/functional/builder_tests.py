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

import os
import tempfile
from os.path import join
from tito.builder import Builder
from tito.common import *
from functional.fixture import TitoGitTestFixture, tito

PKG_NAME = "titotestpkg"


class BuilderTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)
        os.chdir(self.repo_dir)

        self.config = RawConfigParser()
        self.output_dir = tempfile.mkdtemp("-titotestoutput")

    def test_untagged_test_version(self):
        self.create_project(PKG_NAME, tag=False)
        self.assertEqual("", run_command("git tag -l").strip())

        builder = Builder(PKG_NAME, None, self.output_dir,
            self.config, {}, {}, **{'offline': True, 'test': True})
        self.assertEqual('0.0.1-1', builder.build_version)

    def test_untagged_test_build(self):
        self.create_project(PKG_NAME, tag=False)
        self.assertEqual("", run_command("git tag -l").strip())
        tito('build --srpm --test')
