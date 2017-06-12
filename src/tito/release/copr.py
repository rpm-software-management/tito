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

import os.path
import subprocess

from tito.common import run_command, info_out, error_out
from tito.release import KojiReleaser


class CoprReleaser(KojiReleaser):
    """ Releaser for Copr using copr-cli command """

    REQUIRED_CONFIG = ['project_name']
    cli_tool = "copr-cli"
    NAME = "Copr"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        self.user_config = user_config

        KojiReleaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test,
                auto_accept, **kwargs)

        self.copr_project_name = \
            self.releaser_config.get(self.target, "project_name")
        self.srpm_submitted = False

        # 'copr-cli build' options, e.g. --chroot
        # Default to --nowait, so that it mirrors the behavior of fedpkg
        self.copr_options = '--nowait'
        if self.releaser_config.has_option(self.target, "copr_options"):
            self.copr_options = \
                self.releaser_config.get(self.target, "copr_options")

    def autobuild_tags(self):
        """ will return list of project for which we are building """
        result = self.releaser_config.get(self.target, "project_name")
        return result.strip().split(" ")

    def _koji_release(self):
        self.srpm_submitted = False
        if not self.builder.config.has_section(self.copr_project_name):
            self.builder.config.add_section(self.copr_project_name)
        KojiReleaser._koji_release(self)

    def _check_releaser_config(self):
        """
        Verify this release target has all the config options it needs.
        """
        self.remote_location = None
        if self.releaser_config.has_option(self.target, "remote_location"):
            self.remote_location = self.releaser_config.get(self.target, "remote_location")
        elif 'COPR_REMOTE_LOCATION' in self.user_config:
            self.remote_location = self.user_config['COPR_REMOTE_LOCATION']
        KojiReleaser._check_releaser_config(self)

    def _submit_build(self, executable, koji_opts, tag, srpm_location):
        """
        Submit the build into Copr
        If `remote_location` was specified, the SRPM package is uploaded
        there and then submitted into Copr via URL. Otherwise the package
        is submitted from local storage directly to the Copr
        """
        path = srpm_location
        if self.remote_location:
            path = self.remote_location + os.path.basename(srpm_location)
            self._upload(srpm_location)
        self._submit(path, tag)

    def _upload(self, srpm_location):
        if self.srpm_submitted:
            srpm_location = self.srpm_submitted

        # e.g. "scp %(srpm)s my.web.com:public_html/my_srpm/"
        cmd = self.releaser_config.get(self.target, "upload_command")
        cmd_upload = cmd % {'srpm': srpm_location}

        if self.dry_run:
            self.print_dry_run_warning(cmd_upload)
            return

        # TODO: no error handling when run_command fails:
        if not self.srpm_submitted:
            print("Uploading src.rpm.")
            print(run_command(cmd_upload))
            self.srpm_submitted = srpm_location

    def _submit(self, srpm_location, project):
        cmd_submit = "/usr/bin/%s build %s %s %s" % \
                     (self.cli_tool, self.copr_options, project, srpm_location)
        if self.dry_run:
            self.print_dry_run_warning(cmd_submit)
            return

        info_out("Submitting build into %s." % self.NAME)
        self._run_command(cmd_submit)

    def _run_command(self, cmd):
        process = subprocess.Popen(cmd.split())
        process.wait()
        if process.returncode > 0:
            error_out("Failed running `%s`" % cmd)
