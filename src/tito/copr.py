# Copyright (c) 2013 Red Hat, Inc.
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
import os.path

from tito.common import run_command
from tito.release import KojiReleaser


class CoprReleaser(KojiReleaser):
    """ Releaser for Copr using copr-cli command """

    REQUIRED_CONFIG = ['project_name', 'upload_command', 'remote_location']
    cli_tool = "copr-cli"
    NAME = "Copr"

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False, test=False, auto_accept=False):
        KojiReleaser.__init__(self, name, version, tag, build_dir, pkg_config,
                global_config, user_config, target, releaser_config, no_cleanup, test, auto_accept)

        self.copr_project_name = \
            self.releaser_config.get(self.target, "project_name")
        self.srpm_submitted = False

    def autobuild_tags(self):
        """ will return list of project for which we are building """
        result = self.releaser_config.get(self.target, "project_name")
        return result.strip().split(" ")

    def _koji_release(self):
        self.srpm_submitted = False
        if not self.builder.config.has_section(self.copr_project_name):
            self.builder.config.add_section(self.copr_project_name)
        KojiReleaser._koji_release(self)

    def _submit_build(self, executable, koji_opts, tag, srpm_location):
        """ Copy srpm to remote destination and submit it to Copr """
        cmd = self.releaser_config.get(self.target, "upload_command", raw = True)
        url = self.releaser_config.get(self.target, "remote_location")
        if self.srpm_submitted:
            srpm_location = self.srpm_submitted
        srpm_base_name = os.path.basename(srpm_location)

        # e.g. "scp %(srpm)s my.web.com:public_html/my_srpm/"
        cmd_upload = cmd % { 'srpm' : srpm_location }
        cmd_submit = "/usr/bin/copr-cli build %s %s%s" % ( self.releaser_config.get(self.target, "project_name"),
            url, srpm_base_name)

        if self.dry_run:
            self.print_dry_run_warning(cmd_upload)
            self.print_dry_run_warning(cmd_submit)
            return
        if not self.srpm_submitted:
            print "Uploading src.rpm."
            print run_command(cmd_upload)
            self.srpm_submitted = srpm_location
        print "Submiting build into %s." % self.NAME
        print run_command(cmd_submit)
