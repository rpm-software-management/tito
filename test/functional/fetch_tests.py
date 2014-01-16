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

import ConfigParser
import os
import shutil
import tempfile

from tito.common import run_command
from fixture import TitoGitTestFixture, tito

EXT_SRC_PKG = "extsrc"

class FetchBuilderTests(TitoGitTestFixture):

    def setUp(self):
        TitoGitTestFixture.setUp(self)
        self.pkg_dir = os.path.join(self.repo_dir, EXT_SRC_PKG)
        spec = os.path.join(os.path.dirname(__file__), "specs/extsrc.spec")

        # Setup test config:
        self.config = ConfigParser.RawConfigParser()
        self.config.add_section("buildconfig")
        self.config.set("buildconfig", "builder",
                "tito.builder.FetchBuilder")

        self.config.add_section('builder')
        self.config.set('builder', 'fetch_strategy',
                'tito.builder.fetch.KeywordArgSourceStrategy')

        self.create_project_from_spec(EXT_SRC_PKG, self.config,
                pkg_dir=self.pkg_dir, spec=spec)
        self.source_filename = 'extsrc-0.0.2.tar.gz'
        os.chdir(self.pkg_dir)

        # Make a fake source file, do we need something more real?
        run_command('touch %s' % self.source_filename)

        self.output_dir = tempfile.mkdtemp("-titotestoutput")

    def tearDown(self):
        TitoGitTestFixture.tearDown(self)
        shutil.rmtree(self.output_dir)

    def test_simple_build_no_tag(self):
        # We have not tagged here. Build --rpm should just work:
        self.assertFalse(os.path.exists(
            os.path.join(self.pkg_dir, 'rel-eng/packages/extsrc')))

        tito('build --rpm --output=%s --no-cleanup --debug --arg=source=%s ' %
                (self.output_dir, self.source_filename))
        self.assertTrue(os.path.exists(
            os.path.join(self.output_dir, 'extsrc-0.0.2-1.fc20.src.rpm')))
        self.assertTrue(os.path.exists(
            os.path.join(self.output_dir, 'noarch/extsrc-0.0.2-1.fc20.noarch.rpm')))

    def test_tag_rejected(self):
        self.assertRaises(SystemExit, tito,
                'build --tag=extsrc-0.0.1-1 --rpm --output=%s --arg=source=%s ' %
                (self.output_dir, self.source_filename))



