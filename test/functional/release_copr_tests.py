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
Functional Tests for the CoprReleaser.
"""

from functional.fixture import TitoGitTestFixture

from tito.compat import *  # NOQA
from tito.release import CoprReleaser

PKG_NAME = "releaseme"

RELEASER_CONF = """
[test]
releaser = tito.release.CoprReleaser
builder = tito.builder.Builder
"""


class CoprReleaserTests(TitoGitTestFixture):

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

        self.releaser_config = RawConfigParser()
        self.releaser_config.add_section('test')
        self.releaser_config.set('test', 'releaser',
            'tito.release.CoprReleaser')
        self.releaser_config.set('test', 'builder',
            'tito.builder.Builder')
        self.releaser_config.set('test', 'project_name', PKG_NAME)
        self.releaser_config.set('test', 'upload_command',
            'scp %(srpm)s example.com/public_html/my_srpm/')
        self.releaser_config.set('test', 'remote_location',
            'http://example.com/~someuser/my_srpm/')

    def test_with_releaser(self):
        releaser = CoprReleaser(PKG_NAME, None, '/tmp/tito/',
            self.config, {}, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        releaser.release(dry_run=True)
        self.assertTrue(releaser.srpm_submitted is not None)
