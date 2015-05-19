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
import sys
import tempfile

from tito.common import run_command, BugzillaExtractor, debug, extract_sources, \
    MissingBugzillaCredsException, error_out, chdir
from tito.compat import getoutput, getstatusoutput, write
from tito.release import Releaser
from tito.release.main import PROTECTED_BUILD_SYS_FILES
from tito.buildparser import BuildTargetParser
from tito.exception import RunCommandException


class FedoraGitReleaser(Releaser):

    REQUIRED_CONFIG = ['branches']
    cli_tool = "fedpkg"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        Releaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test,
                auto_accept, **kwargs)

        self.git_branches = \
            self.releaser_config.get(self.target, "branches").split(" ")

        if self.config.has_option(self.target, "remote_git_name"):
            overwrite_checkout = self.config.get(self.target, "remote_git_name")
        else:
            overwrite_checkout = None
        if overwrite_checkout:
            self.project_name = overwrite_checkout

        self.package_workdir = os.path.join(self.working_dir,
                self.project_name)

        build_target_parser = BuildTargetParser(self.releaser_config, self.target,
                                                self.git_branches)
        self.build_targets = build_target_parser.get_build_targets()

        # Files we should copy to git during a release:
        self.copy_extensions = (".spec", ".patch")

    def release(self, dry_run=False, no_build=False, scratch=False):
        self.dry_run = dry_run
        self.no_build = no_build
        self._git_release()

    def _get_build_target_for_branch(self, branch):
        if branch in self.build_targets:
            return self.build_targets[branch]
        return None

    def _git_release(self):
        getoutput("mkdir -p %s" % self.working_dir)
        with chdir(self.working_dir):
            run_command("%s clone %s" % (self.cli_tool, self.project_name))

        project_checkout = os.path.join(self.working_dir, self.project_name)
        with chdir(project_checkout):
            run_command("%s switch-branch %s" % (self.cli_tool, self.git_branches[0]))

        # Mead builds need to be in the git_root.  Other builders are agnostic.
        with chdir(self.git_root):
            self.builder.tgz()

        if self.test:
            self.builder._setup_test_specfile()

        self._git_sync_files(project_checkout)
        self._git_upload_sources(project_checkout)
        self._git_user_confirm_commit(project_checkout)

    def _get_bz_flags(self):
        required_bz_flags = None
        if self.releaser_config.has_option(self.target,
            'required_bz_flags'):
            required_bz_flags = self.releaser_config.get(self.target,
                'required_bz_flags').split(" ")
            debug("Found required flags: %s" % required_bz_flags)

        placeholder_bz = None
        if self.releaser_config.has_option(self.target,
            'placeholder_bz'):
            placeholder_bz = self.releaser_config.get(self.target,
                'placeholder_bz')
            debug("Found placeholder bugzilla: %s" % placeholder_bz)

        return (required_bz_flags, placeholder_bz)

    def _confirm_commit_msg(self, diff_output):
        """
        Generates a commit message in a temporary file, gives the user a
        chance to edit it, and returns the filename to the caller.
        """

        fd, name = tempfile.mkstemp()
        debug("Storing commit message in temp file: %s" % name)
        write(fd, "Update %s to %s\n" % (self.project_name,
            self.builder.build_version))
        # Write out Resolves line for all bugzillas we see in commit diff:
        # TODO: move to DistGitBuilder only?
        try:
            (required_bz_flags, placeholder_bz) = self._get_bz_flags()
            extractor = BugzillaExtractor(diff_output,
                required_flags=required_bz_flags,
                placeholder_bz=placeholder_bz)
            for line in extractor.extract():
                write(fd, line + "\n")
        except MissingBugzillaCredsException:
            error_out([
                "Releaser specifies required flags but you have not configured",
                "a ~/.bugzillarc with your bugzilla credentials.",
                "Example:",
                "",
                "[bugzilla.redhat.com]",
                "user = dgoodwin@redhat.com",
                "password = mypassword"])

        print("")
        print("##### Commit message: #####")
        print("")

        os.lseek(fd, 0, 0)
        f = os.fdopen(fd)
        for line in f.readlines():
            print(line)
        f.close()

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

    def _git_user_confirm_commit(self, project_checkout):
        """ Prompt user if they wish to proceed with commit. """
        print("")
        text = "Running 'git diff' in: %s" % project_checkout
        print("#" * len(text))
        print(text)
        print("#" * len(text))
        print("")

        main_branch = self.git_branches[0]

        os.chdir(project_checkout)

        # Newer versions of git don't seem to want --cached here? Try both:
        (unused, diff_output) = getstatusoutput("git diff --cached")
        if diff_output.strip() == "":
            debug("git diff --cached returned nothing, falling back to git diff.")
            (unused, diff_output) = getstatusoutput("git diff")

        if diff_output.strip() == "":
            print("No changes in main branch, skipping commit for: %s" % main_branch)
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
            debug("git commit command: %s" % cmd)
            print
            if self.dry_run:
                self.print_dry_run_warning(cmd)
            else:
                print("Proceeding with commit.")
                os.chdir(self.package_workdir)
                run_command(cmd)

            os.unlink(commit_msg_file)

        cmd = "%s push" % self.cli_tool
        if self.dry_run:
            self.print_dry_run_warning(cmd)
        else:
            # Push
            print(cmd)
            try:
                run_command(cmd)
            except RunCommandException as e:
                error_out("`%s` failed with: %s" % (cmd, e.output))

        if not self.no_build:
            self._build(main_branch)

        for branch in self.git_branches[1:]:
            print("Merging branch: '%s' -> '%s'" % (main_branch, branch))
            run_command("%s switch-branch %s" % (self.cli_tool, branch))
            self._merge(main_branch)

            cmd = "git push origin %s:%s" % (branch, branch)
            if self.dry_run:
                self.print_dry_run_warning(cmd)
            else:
                print(cmd)
                try:
                    run_command(cmd)
                except RunCommandException as e:
                    error_out("`%s` failed with: %s" % (cmd, e.output))

            if not self.no_build:
                self._build(branch)

            print

    def _merge(self, main_branch):
        try:
            run_command("git merge %s" % main_branch)
        except:
            print
            print("WARNING!!! Conflicts occurred during merge.")
            print
            print("You are being dropped to a shell in the working directory.")
            print
            print("Please resolve this by doing the following:")
            print
            print("  1. List the conflicting files: git ls-files --unmerged")
            print("  2. Edit each resolving the conflict and then: git add FILENAME")
            print("  4. Commit the result when you are done: git commit")
            print("  4. Return to the tito release: exit")
            print
            # TODO: maybe prompt y/n here
            os.system(os.environ['SHELL'])

    def _build(self, branch):
        """ Submit a Fedora build from current directory. """
        target_param = ""
        build_target = self._get_build_target_for_branch(branch)
        if build_target:
            target_param = "--target %s" % build_target

        build_cmd = "%s build --nowait %s" % (self.cli_tool, target_param)

        if self.dry_run:
            self.print_dry_run_warning(build_cmd)
            return

        print("Submitting build: %s" % build_cmd)
        (status, output) = getstatusoutput(build_cmd)
        if status > 0:
            if "already been built" in output:
                print("Build has been submitted previously, continuing...")
            else:
                sys.stderr.write("ERROR: Unable to submit build.\n")
                sys.stderr.write("  Status code: %s\n" % status)
                sys.stderr.write("  Output: %s\n" % output)
                sys.exit(1)

        # Print the task ID and URL:
        for line in extract_task_info(output):
            print(line)

    def _git_upload_sources(self, project_checkout):
        """
        Upload any tarballs to the lookaside directory. (if necessary)
        Uses the "fedpkg new-sources" command.
        """
        if not self.builder.sources:
            debug("No sources need to be uploaded.")
            return

        print("Uploading sources to lookaside:")
        os.chdir(project_checkout)
        cmd = '%s new-sources %s' % (self.cli_tool, " ".join(self.builder.sources))
        debug(cmd)

        if self.dry_run:
            self.print_dry_run_warning(cmd)
            return

        output = run_command(cmd)
        debug(output)
        debug("Removing write-only permission on:")
        for filename in self.builder.sources:
            run_command("chmod u+w %s" % filename)

    def _list_files_to_copy(self):
        """
        Returns a list of the full file paths for each file that should be
        copied from our git project into the build system checkout. This
        is used to sync files to git during a release.

        i.e. spec file, .patches.

        It is assumed that any file found in the build system checkout
        but not in this list, and not in the protected files list, should
        probably be cleaned up.
        """
        # Include the spec file explicitly, in the case of SatelliteBuilder
        # we modify and then use a spec file copy from a different location.
        files_to_copy = [self.builder.spec_file]  # full paths

        f = open(self.builder.spec_file, 'r')
        lines = f.readlines()
        f.close()
        source_filenames = extract_sources(lines)
        debug("Watching for source filenames: %s" % source_filenames)

        for filename in os.listdir(self.builder.rpmbuild_gitcopy):
            full_filepath = os.path.join(self.builder.rpmbuild_gitcopy, filename)
            if os.path.isdir(full_filepath):
                # skip it
                continue
            if filename in PROTECTED_BUILD_SYS_FILES:
                debug("   skipping:  %s (protected file)" % filename)
                continue
            elif filename.endswith(".spec"):
                # Skip the spec file, we already copy this explicitly as it
                # can come from a couple different locations depending on which
                # builder is in use.
                continue

            # Check if file looks like it matches a Source line in the spec file:
            if filename in source_filenames:
                debug("   copying:   %s" % filename)
                files_to_copy.append(full_filepath)
                continue

            # Check if file ends with something this builder subclass wants
            # to copy:
            copy_it = False
            for extension in self.copy_extensions:
                if filename.endswith(extension):
                    copy_it = True
                    continue
            if copy_it:
                debug("   copying:   %s" % filename)
                files_to_copy.append(full_filepath)

        return files_to_copy

    def _git_sync_files(self, project_checkout):
        """
        Copy files from our git into each git build branch and add them.

        A list of safe files is used to protect critical files both from
        being overwritten by a git file of the same name, as well as being
        deleted after.
        """

        # Build the list of all files we will copy:
        debug("Searching for files to copy to build system git:")
        files_to_copy = self._list_files_to_copy()

        os.chdir(project_checkout)

        new, copied, old =  \
                self._sync_files(files_to_copy, project_checkout)

        os.chdir(project_checkout)

        # Git add everything:
        for add_file in (new + copied):
            run_command("git add %s" % add_file)

        # Cleanup obsolete files:
        for cleanup_file in old:
            # Can't delete via full path, must not chdir:
            run_command("git rm %s" % cleanup_file)


class DistGitReleaser(FedoraGitReleaser):
    cli_tool = "rhpkg"


class DistGitMeadReleaser(DistGitReleaser):
    REQUIRED_CONFIG = ['mead_scm', 'branches']

    def __init__(self, name=None, tag=None, build_dir=None,
        config=None, user_config=None,
        target=None, releaser_config=None, no_cleanup=False,
        test=False, auto_accept=False,
        prefix="temp_dir=", **kwargs):

        if 'builder_args' in kwargs:
            kwargs['builder_args']['local'] = False

        DistGitReleaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test,
                auto_accept, **kwargs)

        self.mead_scm = self.releaser_config.get(self.target, "mead_scm")

        self.mead_url = "%s#%s" % (
            self.mead_scm,
            self.builder.build_tag)

        if self.releaser_config.has_option(self.target, "mead_push_url"):
            self.push_url = self.releaser_config.get(self.target, "mead_push_url")
        else:
            self.push_url = self.mead_scm

    def _sync_mead_scm(self):
        with chdir(self.git_root):
            print("Syncing local repo with %s" % self.push_url)
            try:
                run_command("git push %s %s" % (self.push_url, self.builder.build_tag))
            except RunCommandException as e:
                if "rejected" in e.output:
                    if self._ask_yes_no("The remote rejected a push.  Force push? [y/n] ", False):
                        run_command("git push --force %s %s" % (self.mead_scm, self.builder.build_tag))
                    else:
                        error_out("Could not sync with %s" % self.mead_scm)
                raise

    def _git_release(self):
        self._sync_mead_scm()
        DistGitReleaser._git_release(self)

    def _git_upload_sources(self, project_checkout):
        DistGitReleaser._git_upload_sources(self, project_checkout)

        if self.dry_run:
            self.print_dry_run_warning("echo '%s' > tito-mead-url" % self.mead_url)
            return

        with chdir(project_checkout):
            with open("tito-mead-url", "w") as f:
                f.write(self.mead_url)
                f.write("\n")

            run_command("git add tito-mead-url")

    def _build(self, branch):
        """ Submit a Mead build from current directory. """
        target_param = ""
        build_target = self._get_build_target_for_branch(branch)
        if build_target:
            target_param = "--target=%s" % build_target

        build_cmd = [self.cli_tool, "maven-build", "--nowait"]

        for arg in self.builder.maven_args:
            build_cmd.append("--maven-option='%s'" % arg)

        for prop in self.builder.maven_properties:
            build_cmd.append("--property='%s'" % prop)
        build_cmd.append("--sources=%s" % self.mead_url)
        build_cmd.append(target_param)
        build_cmd = " ".join(build_cmd)

        if self.dry_run:
            self.print_dry_run_warning(build_cmd)
            return

        print("Submitting build: %s" % build_cmd)
        (status, output) = getstatusoutput(build_cmd)
        if status > 0:
            if "already been built" in output:
                print("Build has been submitted previously, continuing...")
            else:
                sys.stderr.write("ERROR: Unable to submit build.\n")
                sys.stderr.write("  Status code: %s\n" % status)
                sys.stderr.write("  Output: %s\n" % output)
                sys.exit(1)

        # Print the task ID and URL:
        for line in extract_task_info(output):
            print(line)


def extract_task_info(output):
    """ Extracts task ID and URL from koji/brew build output. """
    task_lines = []
    for line in output.splitlines():
        if "Created task" in line:
            task_lines.append(line)
        elif "Task info" in line:
            task_lines.append(line)
    return task_lines
