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

import mock
from tito.compat import *  # NOQA
from tito.release import CoprReleaser
from unit import Capture

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

    def test_with_remote_defined_in_user_conf(self):
        self.releaser_config.remove_option("test", "remote_location")
        user_config = {'COPR_REMOTE_LOCATION': 'http://example.com/~otheruser/'}
        releaser = CoprReleaser(PKG_NAME, None, '/tmp/tito/',
            self.config, user_config, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        releaser.release(dry_run=True)
        self.assertTrue(releaser.srpm_submitted is not None)

    @mock.patch("tito.release.CoprReleaser._submit")
    @mock.patch("tito.release.CoprReleaser._upload")
    def test_no_remote_defined(self, upload, submit):
        self.releaser_config.remove_option("test", "remote_location")
        releaser = CoprReleaser(PKG_NAME, None, '/tmp/tito/',
            self.config, {}, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        releaser.release(dry_run=True)

        self.assertFalse(upload.called)
        self.assertTrue(submit.called)

    @mock.patch("tito.release.CoprReleaser._run_command")
    def test_multiple_project_names(self, run_command):
        self.releaser_config.remove_option("test", "remote_location")
        self.releaser_config.set('test', 'project_name', "%s %s" % (PKG_NAME,
            PKG_NAME))
        releaser = CoprReleaser(PKG_NAME, None, '/tmp/tito/',
            self.config, {}, 'test', self.releaser_config, False,
            False, False, **{'offline': True})
        releaser.release()
        args = mock.call('/usr/bin/copr-cli build --nowait releaseme %s' %
                releaser.builder.srpm_location)
        self.assertEquals(args, run_command.mock_calls[0])
        self.assertEquals(args, run_command.mock_calls[1])
