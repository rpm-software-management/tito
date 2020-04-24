# Copyright (c) 2008-2011 Red Hat, Inc.
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
import subprocess
import sys

from tito.common import run_command, debug
from tito.compat import getoutput, write, getstatusoutput
from tito.release.distgit import FedoraGitReleaser
from tito.bugtracker import BugzillaExtractor


class ObsReleaser(FedoraGitReleaser):
    """ Releaser for Open Build System using osc command """

    REQUIRED_CONFIG = ['project_name']
    cli_tool = "osc"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        FedoraGitReleaser.__init__(self, name, tag, build_dir,
                user_config, target, releaser_config, no_cleanup, test, auto_accept)

        self.obs_project_name = \
            self.releaser_config.get(self.target, "project_name")

        if self.config.has_option(self.target, "package_name"):
            self.obs_package_name = self.config.get(self.target, "package_name")
        else:
            self.obs_package_name = self.project_name

        self.package_workdir = os.path.join(self.working_dir, self.obs_project_name,
                self.project_name)

    def release(self, dry_run=False, no_build=False, scratch=False):
        self.dry_run = dry_run
        self.no_build = no_build

        getoutput("mkdir -p %s" % self.working_dir)
        os.chdir(self.working_dir)
        run_command("%s co %s %s" % (self.cli_tool, self.obs_project_name, self.obs_package_name))

        os.chdir(self.package_workdir)

        self.builder.tgz()
        if self.test:
            self.builder._setup_test_specfile()

        self._obs_sync_files(self.package_workdir)
        self._obs_user_confirm_commit(self.package_workdir)

    def _confirm_commit_msg(self, diff_output):
        """
        Generates a commit message in a temporary file, gives the user a
        chance to edit it, and returns the filename to the caller.
        """

        fd, name = tempfile.mkstemp()
        debug("Storing commit message in temp file: %s" % name)
        write(fd, "Update %s to %s\n" % (self.obs_package_name,
            self.builder.build_version))
        # Write out Resolves line for all bugzillas we see in commit diff:
        extractor = BugzillaExtractor(diff_output)
        for line in extractor.extract():
            write(fd, line + "\n")

        print("")
        print("##### Commit message: #####")
        print("")

        os.lseek(fd, 0, 0)
        commit_file = os.fdopen(fd)
        for line in commit_file.readlines():
            print(line)
        commit_file.close()

        print("")
        print("###############################")
        print("")
        if self._ask_yes_no("Would you like to edit this commit message? [y/n] ", False):
            debug("Opening editor for user to edit commit message in: %s" % name)
            editor = 'vi'
            if "EDITOR" in os.environ:
                editor = os.environ["EDITOR"]
            subprocess.call(editor.split() + [name])

        return name

    def _obs_user_confirm_commit(self, project_checkout):
        """ Prompt user if they wish to proceed with commit. """
        print("")
        text = "Running '%s diff' in: %s" % (self.cli_tool, project_checkout)
        print("#" * len(text))
        print(text)
        print("#" * len(text))
        print("")

        os.chdir(project_checkout)

        (status, diff_output) = getstatusoutput("%s diff" % self.cli_tool)

        if diff_output.strip() == "":
            print("No changes in main branch, skipping commit.")
        else:
            print(diff_output)
            print("")
            print("##### Please review the above diff #####")
            if not self._ask_yes_no("Do you wish to proceed with commit? [y/n] "):
                print("Fine, you're on your own!")
                self.cleanup()
                sys.exit(1)

            print("Proceeding with commit.")
            commit_msg_file = self._confirm_commit_msg(diff_output)
            cmd = '%s commit -F %s' % (self.cli_tool,
                    commit_msg_file)
            debug("obs commit command: %s" % cmd)
            print
            if self.dry_run:
                self.print_dry_run_warning(cmd)
            else:
                print("Proceeding with commit.")
                os.chdir(self.package_workdir)
                print(run_command(cmd))

            os.unlink(commit_msg_file)

        if self.no_build:
            getstatusoutput("%s abortbuild %s %s" % (
                self.cli_tool, self.obs_project_name, self.obs_package_name))
            print("Aborting automatic rebuild because --no-build has been specified.")

    def _obs_sync_files(self, project_checkout):
        """
        Copy files from our obs checkout into each obs checkout and add them.

        A list of safe files is used to protect critical files both from
        being overwritten by a osc file of the same name, as well as being
        deleted after.
        """

        # Build the list of all files we will copy:
        debug("Searching for files to copy to build system osc checkout:")
        files_to_copy = self._list_files_to_copy()

        os.chdir(project_checkout)

        self._sync_files(files_to_copy, project_checkout)

        os.chdir(project_checkout)

        # Add/remove everything:
        run_command("%s addremove" % (self.cli_tool))
