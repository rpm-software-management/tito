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

    def test_scl_from_options(self):
        self.create_project(PKG_NAME)
        builder = Builder(PKG_NAME, None, self.output_dir,
            self.config, {}, {'scl': 'ruby193'}, **{'offline': True})
        self.assertEqual('ruby193', builder.scl)

    def test_scl_from_kwargs(self):
        self.create_project(PKG_NAME)
        builder = Builder(PKG_NAME, None, self.output_dir,
            self.config, {}, {}, **{'offline': True, 'scl': 'ruby193'})
        self.assertEqual('ruby193', builder.scl)
