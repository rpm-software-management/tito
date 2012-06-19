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
from ConfigParser import NoOptionError

"""
Code for submitting builds for release.
"""

import os
import commands
import tempfile
import subprocess
import rpm

from tempfile import mkdtemp
from shutil import rmtree, copy

from tito.common import *
from tito.exception import TitoException

DEFAULT_KOJI_OPTS = "build --nowait"
DEFAULT_CVS_BUILD_DIR = "cvswork"

# List of CVS files to protect when syncing git with a CVS module:
PROTECTED_BUILD_SYS_FILES = ('branch', 'CVS', '.cvsignore', 'Makefile', 'sources', ".git", ".gitignore")

RSYNC_USERNAME = 'RSYNC_USERNAME'  # environment variable name


class Releaser(object):
    """
    Parent class of all releasers.

    Can't really be used by itself, need to use one of the sub-classes.
    """
    GLOBAL_REQUIRED_CONFIG = ['releaser']
    REQUIRED_CONFIG = []
    OPTIONAL_CONFIG = []

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False):

        self.builder_args = self._parse_builder_args(releaser_config, target)

        # While we create a builder here, we don't actually call run on it
        # unless the releaser needs to:
        self.builder = create_builder(name, tag,
                version, pkg_config,
                build_dir, global_config, user_config, self.builder_args)
        self.project_name = self.builder.project_name

        # TODO: if it looks like we need custom CVSROOT's for different users,
        # allow setting of a property to lookup in ~/.spacewalk-build-rc to
        # use instead. (if defined)
        self.working_dir = os.path.join(self.builder.rpmbuild_basedir,
                DEFAULT_CVS_BUILD_DIR)
        self.working_dir = mkdtemp(dir=self.builder.rpmbuild_basedir,
                prefix="release-%s" % self.builder.project_name_and_sha1)
        print("Working in: %s" % self.working_dir)

        # When syncing files with CVS, only copy files with these extensions:
        self.cvs_copy_extensions = (".spec", ".patch")

        # Config for all releasers:
        self.releaser_config = releaser_config

        # The actual release target we're building:
        self.target = target

        self.dry_run = False

        self.no_cleanup = no_cleanup

        self._check_releaser_config()

    def _check_releaser_config(self):
        """
        Verify this release target has all the config options it needs.
        """
        for opt in self.GLOBAL_REQUIRED_CONFIG:
            if not self.releaser_config.has_option(self.target, opt):
                raise TitoException(
                        "Release target '%s' missing required option '%s'" %
                        (self.target, opt))
        for opt in self.REQUIRED_CONFIG:
            if not self.releaser_config.has_option(self.target, opt):
                raise TitoException(
                        "Release target '%s' missing required option '%s'" %
                        (self.target, opt))

        # TODO: accomodate 'builder.*' for yum releaser and we can use this:
        #for opt in self.releaser_config.options(self.target):
        #    if opt not in self.GLOBAL_REQUIRED_CONFIG and \
        #            opt not in self.REQUIRED_CONFIG and \
        #            opt not in self.OPTIONAL_CONFIG:
        #        raise TitoException(
        #                "Release target '%s' has unknown option '%s'" %
        #                (self.target, opt))

    def _parse_builder_args(self, releaser_config, target):
        """
        Any properties found in a releaser target section starting with
        "builder." are assumed to be builder arguments.

        i.e.:

        builder.mock = epel-6-x86_64

        Would indicate that we need to pass an argument "mock" to whatever
        builder is configured.
        """
        args = {}
        for opt in releaser_config.options(target):
            if opt.startswith("builder."):
                args[opt[len("builder."):]] = releaser_config.get(target, opt)
        debug("Parsed custom builder args: %s" % args)
        return args

    def release(self, dry_run=False):
        pass

    def cleanup(self):
        if not self.no_cleanup:
            debug("Cleaning up [%s]" % self.working_dir)
            run_command("rm -rf %s" % self.working_dir)
        else:
            print("WARNING: leaving %s (--no-cleanup)" % self.working_dir)

    def _list_files_to_copy(self):
        """
        Returns a list of the full file paths for each file that should be
        copied from our git project into the build system checkout. This
        is used to sync files to CVS or git during a release.

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
            for extension in self.cvs_copy_extensions:
                if filename.endswith(extension):
                    copy_it = True
                    continue
            if copy_it:
                debug("   copying:   %s" % filename)
                files_to_copy.append(full_filepath)

        return files_to_copy

    def print_dry_run_warning(self, command_that_would_be_run_otherwise):
        print
        print("WARNING: Skipping command due to --dry-run: %s" %
                command_that_would_be_run_otherwise)
        print

    def _sync_files(self, files_to_copy, dest_dir):
        debug("Copying files: %s" % files_to_copy)
        debug("   to: %s" % dest_dir)
        os.chdir(dest_dir)

        # Need a list of just the filenames for a set comparison later:
        filenames_to_copy = []
        for filename in files_to_copy:
            filenames_to_copy.append(os.path.basename(filename))

        # Base filename for entirely new files:
        new_files = []

        # Base filenames for pre-existing files we copied over:
        copied_files = []

        # Base filenames that need to be removed by the caller:
        old_files = []

        for copy_me in files_to_copy:
            base_filename = os.path.basename(copy_me)
            dest_path = os.path.join(dest_dir, base_filename)

            if not os.path.exists(dest_path):
                print("   adding: %s" % base_filename)
                new_files.append(base_filename)
            else:
                print("   copying: %s" % base_filename)

            cmd = "cp %s %s" % (copy_me, dest_path)
            run_command(cmd)

        # Track filenames that will need to be deleted by the caller.
        # Could be git or CVS.
        for filename in os.listdir(dest_dir):
            if filename not in PROTECTED_BUILD_SYS_FILES and \
                    filename not in filenames_to_copy:
                print("   deleting: %s" % filename)
                old_files.append(filename)

        return new_files, copied_files, old_files


class YumRepoReleaser(Releaser):
    """
    A releaser which will rsync down a yum repo, build the desired packages,
    plug them in, update the repodata, and push the yum repo back out.

    Building of the packages is done via mock.

    WARNING: This will not work in all
    situations, depending on the current OS, and the mock target you
    are attempting to use.
    """
    REQUIRED_CONFIG = ['rsync', 'builder']

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False):
        Releaser.__init__(self, name, version, tag, build_dir, pkg_config,
                global_config, user_config, target, releaser_config, no_cleanup)

        self.build_dir = build_dir

        # Use the builder from the release target, rather than the default
        # one defined for this git repo or sub-package:
        self.builder = create_builder(name, tag,
                version, pkg_config,
                build_dir, global_config, user_config, self.builder_args,
                builder_class=self.releaser_config.get(self.target, 'builder'))

    def release(self, dry_run=False):
        self.dry_run = dry_run

        # Should this run?
        self.builder.no_cleanup = self.no_cleanup
        self.builder.tgz()
        self.builder.srpm()
        self.builder._rpm()
        self.builder.cleanup()

        rsync_locations = self.releaser_config.get(self.target, 'rsync').split(" ")
        for rsync_location in rsync_locations:
            if RSYNC_USERNAME in os.environ:
                print("%s set, using rsync username: %s" % (RSYNC_USERNAME,
                        os.environ[RSYNC_USERNAME]))
                rsync_location = "%s@%s" % (os.environ[RSYNC_USERNAME], rsync_location)
            # Make a temp directory to sync the existing repo contents into:
            yum_temp_dir = mkdtemp(dir=self.build_dir, prefix="yumrepo-")
            os.chdir(yum_temp_dir)
            print("Syncing yum repo: %s -> %s" % (rsync_location, yum_temp_dir))
            output = run_command("rsync -rlvz %s %s" % (rsync_location, yum_temp_dir))
            debug(output)

            rpm_ts = rpm.TransactionSet()
            self.new_rpm_dep_sets = {}
            for artifact in self.builder.artifacts:
                if artifact.endswith(".rpm") and not artifact.endswith(".src.rpm"):
                    header = self._read_rpm_header(rpm_ts, artifact)
                    self.new_rpm_dep_sets[header['name']] = header.dsOfHeader()
                    copy(artifact, yum_temp_dir)
                    print("Copied %s to yum repo." % artifact)

            # Now cleanout any other version of the package we just built,
            # both older or newer. (can be used to downgrade the contents
            # of a yum repo)
            for filename in os.listdir(yum_temp_dir):
                if not filename.endswith(".rpm"):
                    continue
                hdr = self._read_rpm_header(rpm_ts,
                        os.path.join(yum_temp_dir, filename))
                if hdr['name'] in self.new_rpm_dep_sets:
                    dep_set = hdr.dsOfHeader()
                    if dep_set.EVR() < self.new_rpm_dep_sets[hdr['name']].EVR():
                        print("Deleting old package: %s" % filename)
                        run_command("rm %s" % os.path.join(yum_temp_dir,
                            filename))

            print("Refreshing yum repodata...")
            output = run_command("createrepo ./")
            debug(output)

            print("Syncing yum repository back to: %s" % rsync_location)
            # TODO: configurable rsync options?
            cmd = "rsync -rlvz --delete %s/ %s" % \
                    (yum_temp_dir, rsync_location)
            if self.dry_run:
                self.print_dry_run_warning(cmd)
            else:
                output = run_command(cmd)
                debug(output)
            if not self.no_cleanup:
                debug("Cleaning up [%s]" % yum_temp_dir)
                os.chdir("/")
                rmtree(yum_temp_dir)
            else:
                print("WARNING: leaving %s (--no-cleanup)" % yum_temp_dir)

    def _read_rpm_header(self, ts, new_rpm_path):
        """
        Read RPM header for the given file.
        """
        fd = os.open(new_rpm_path, os.O_RDONLY)
        header = ts.hdrFromFdno(fd)
        os.close(fd)
        return header

    def cleanup(self):
        """ No-op, we clean up during self.release() """
        pass


class FedoraGitReleaser(Releaser):

    REQUIRED_CONFIG = ['branches']
    cli_tool = "fedpkg"

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False):
        Releaser.__init__(self, name, version, tag, build_dir, pkg_config,
                global_config, user_config, target, releaser_config, no_cleanup)

        self.git_branches = \
            self.releaser_config.get(self.target, "branches").split(" ")

        self.package_workdir = os.path.join(self.working_dir,
                self.project_name)

        build_target_parser = BuildTargetParser(self.releaser_config, self.target,
                                                self.git_branches)
        self.build_targets = build_target_parser.get_build_targets()

    def release(self, dry_run=False):
        self.dry_run = dry_run
        self._git_release()

    def _get_build_target_for_branch(self, branch):
        if branch in self.build_targets:
            return self.build_targets[branch]
        return None

    def _git_release(self):

        commands.getoutput("mkdir -p %s" % self.working_dir)
        os.chdir(self.working_dir)
        run_command("%s clone %s" % (self.cli_tool, self.project_name))

        project_checkout = os.path.join(self.working_dir, self.project_name)
        os.chdir(project_checkout)
        run_command("%s switch-branch %s" % (self.cli_tool, self.git_branches[0]))

        self.builder.tgz()

        self._git_sync_files(project_checkout)
        self._git_upload_sources(project_checkout)
        self._git_user_confirm_commit(project_checkout)

    def _confirm_commit_msg(self, diff_output):
        """
        Generates a commit message in a temporary file, gives the user a
        chance to edit it, and returns the filename to the caller.
        """

        fd, name = tempfile.mkstemp()
        debug("Storing commit message in temp file: %s" % name)
        os.write(fd, "Update %s to %s\n" % (self.project_name,
            self.builder.build_version))
        # Write out Resolves line for all bugzillas we see in commit diff:
        for line in extract_bzs(diff_output):
            os.write(fd, line + "\n")

        print("")
        print("##### Commit message: #####")
        print("")

        os.lseek(fd, 0, 0)
        file = os.fdopen(fd)
        for line in file.readlines():
            print line
        file.close()

        print("")
        print("###############################")
        print("")
        answer = raw_input("Would you like to edit this commit message? [y/n] ")
        if answer.lower() in ['y', 'yes', 'ok', 'sure']:
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
        (status, diff_output) = commands.getstatusoutput("git diff --cached")
        if diff_output.strip() == "":
            (status, diff_output) = commands.getstatusoutput("git diff")

        if diff_output.strip() == "":
            print("No changes in main branch, skipping commit for: %s" % main_branch)
        else:
            print(diff_output)
            print("")
            print("##### Please review the above diff #####")
            answer = raw_input("Do you wish to proceed with commit? [y/n] ")
            if answer.lower() not in ['y', 'yes', 'ok', 'sure']:
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
                output = run_command(cmd)

            os.unlink(commit_msg_file)

        cmd = "%s push" % self.cli_tool
        if self.dry_run:
            self.print_dry_run_warning(cmd)
        else:
            # Push
            print(cmd)
            run_command(cmd)

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
                run_command(cmd)

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
        (status, output) = commands.getstatusoutput(build_cmd)
        if status > 0:
            if "already been built" in output:
                print("Build has been submitted previously, continuing...")
            else:
                sys.stderr.write("ERROR: Unable to submit build.")
                sys.stderr.write("  Status code: %s" % status)
                sys.stderr.write("  Output: %s" % output)
                sys.exit(1)

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

        # TODO:
        #for branch in self.cvs_branches:
        #print("Syncing files with git branch [%s]" % branch)
        new, copied, old =  \
                self._sync_files(files_to_copy, project_checkout)

        os.chdir(project_checkout)

        # Git add everything:
        for add_file in (new + copied):
            commands.getstatusoutput("git add %s" % add_file)

        # Cleanup obsolete files:
        for cleanup_file in old:
            # Can't delete via full path, must not chdir:
            run_command("git rm %s" % cleanup_file)


class DistGitReleaser(FedoraGitReleaser):
    cli_tool = "rhpkg"


class CvsReleaser(Releaser):
    """
    Release packages via a CVS build system.

    WARNING: no longer relevant to Fedora, which now uses Git.
    """

    REQUIRED_CONFIG = ['cvsroot', 'branches']

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False):
        Releaser.__init__(self, name, version, tag, build_dir, pkg_config,
                global_config, user_config, target, releaser_config, no_cleanup)

        self.package_workdir = os.path.join(self.working_dir,
                self.project_name)

        # Configure CVS variables if possible. Will check later that
        # they're actually defined if the user requested CVS work be done.
        if self.releaser_config.has_option(target, "cvsroot"):
            self.cvs_root = self.releaser_config.get(target, "cvsroot")
            debug("cvs_root = %s" % self.cvs_root)
        if self.releaser_config.has_option(target, "branches"):
            self.cvs_branches = \
                self.releaser_config.get(target, "branches").split(" ")

    def release(self, dry_run=False):
        self.dry_run = dry_run

        self._cvs_release()

    def _cvs_release(self):
        """
        Sync spec file/patches with CVS, create tags, and submit to brew/koji.
        """

        self._verify_cvs_module_not_already_checked_out()

        print("Building release in CVS...")
        commands.getoutput("mkdir -p %s" % self.working_dir)
        debug("cvs_branches = %s" % self.cvs_branches)

        self.cvs_checkout_module()
        self.cvs_verify_branches_exist()

        # Get the list of all sources from the builder:
        self.builder.tgz()

        self.cvs_sync_files()

        # Important step here, ends up populating several important members
        # on the builder object so some of the below lines will not work
        # if moved above this one.
        self.cvs_upload_sources()

        self._cvs_user_confirm_commit()

        self._cvs_make_tag()
        self._cvs_make_build()

    def _verify_cvs_module_not_already_checked_out(self):
        """ Exit if CVS module appears to already be checked out. """
        # Make sure the cvs checkout directory doesn't already exist:
        cvs_co_dir = os.path.join(self.working_dir, self.project_name)
        if os.path.exists(cvs_co_dir):
            error_out("CVS workdir exists, please remove and try again: %s"
                    % cvs_co_dir)

    def cvs_checkout_module(self):
        print("Checking out cvs module [%s]" % self.project_name)
        os.chdir(self.working_dir)
        run_command("cvs -d %s co %s" % (self.cvs_root, self.project_name))
        for i in range(0, len(self.cvs_branches)):
            if self.cvs_branches[i].find('/') > -1:
                debug("Checking out zstream branch %s" % self.cvs_branches[i])
                (base, zstream) = self.cvs_branches[i].split('/')
                run_command("make -C %s zstreams" %
                        (os.path.join(self.package_workdir, base)))
                self.cvs_branches[i] = zstream

    def cvs_verify_branches_exist(self):
        """ Check that CVS checkout contains the branches we expect. """
        os.chdir(self.package_workdir)
        for branch in self.cvs_branches:
            if not os.path.exists(os.path.join(self.working_dir,
                self.project_name, branch)):
                error_out("%s CVS checkout is missing branch: %s" %
                        (self.project_name, branch))

    def cvs_sync_files(self):
        """
        Copy files from git into each CVS branch and add them. Extra files
        found in CVS will then be deleted.

        A list of CVS safe files is used to protect critical files both from
        being overwritten by a git file of the same name, as well as being
        deleted after.
        """

        # Build the list of all files we will copy from git to CVS.
        debug("Searching for git files to copy to CVS:")
        files_to_copy = self._list_files_to_copy()

        for branch in self.cvs_branches:
            print("Syncing files with CVS branch [%s]" % branch)
            branch_dir = os.path.join(self.working_dir, self.project_name,
                    branch)

            new, copied, old =  \
                    self._sync_files(files_to_copy, branch_dir)

            os.chdir(branch_dir)

            # For entirely new files we need to cvs add:
            for add_file in new:
                commands.getstatusoutput("cvs add %s" % add_file)

            # Cleanup obsolete files:
            for cleanup_file in old:
                # Can't delete via full path, must not chdir:
                run_command("cvs rm -Rf %s" % cleanup_file)

    def cvs_upload_sources(self):
        """
        Upload any tarballs to the CVS lookaside directory. (if necessary)
        Uses the "make new-sources" target in common.
        """
        if not self.builder.sources:
            debug("No sources need to be uploaded.")
            return

        print("Uploading sources to dist-cvs lookaside:")
        for branch in self.cvs_branches:
            branch_dir = os.path.join(self.working_dir, self.project_name,
                    branch)
            os.chdir(branch_dir)
            cmd = 'make new-sources FILES="%s"' % (" ".join(self.builder.sources))
            debug(cmd)
            if self.dry_run:
                self.print_dry_run_warning(cmd)
                return

            output = run_command(cmd)
            debug(output)

    def _cvs_user_confirm_commit(self):
        """ Prompt user if they wish to proceed with commit. """
        print("")
        text = "Running 'cvs diff -u' in: %s" % self.package_workdir
        print("#" * len(text))
        print(text)
        print("#" * len(text))
        print("")

        os.chdir(self.package_workdir)
        (status, diff_output) = commands.getstatusoutput("cvs diff -u")
        print(diff_output)

        print("")
        print("##### Please review the above diff #####")
        answer = raw_input("Do you wish to proceed with commit? [y/n] ")
        if answer.lower() not in ['y', 'yes', 'ok', 'sure']:
            print("Fine, you're on your own!")
            self.cleanup()
            sys.exit(1)

        self._cvs_user_confirm_commit_msg(diff_output)

    def _cvs_user_confirm_commit_msg(self, diff_output):

        fd, name = tempfile.mkstemp()
        debug("Storing CVS commit message in temp file: %s" % name)
        os.write(fd, "Update %s to %s\n" % (self.project_name,
            self.builder.build_version))
        # Write out Resolves line for all bugzillas we see in commit diff:
        for line in extract_bzs(diff_output):
            os.write(fd, line + "\n")

        print("")
        print("##### CVS commit message: #####")
        print("")

        os.lseek(fd, 0, 0)
        file = os.fdopen(fd)
        for line in file.readlines():
            print line
        file.close()

        print("")
        print("###############################")
        print("")
        answer = raw_input("Would you like to edit this commit message? [y/n] ")
        if answer.lower() in ['y', 'yes', 'ok', 'sure']:
            debug("Opening editor for user to edit commit message in: %s" % name)
            editor = 'vi'
            if "EDITOR" in os.environ:
                editor = os.environ["EDITOR"]
            subprocess.call(editor.split() + [name])

        cmd = 'cvs commit -F %s' % name
        debug("CVS commit command: %s" % cmd)
        if self.dry_run:
            self.print_dry_run_warning(cmd)
        else:
            print("Proceeding with commit.")
            os.chdir(self.package_workdir)
            output = run_command(cmd)

        os.unlink(name)

    def _cvs_make_tag(self):
        """ Create a CVS tag based on what we just committed. """
        os.chdir(self.package_workdir)
        cmd = "make tag"
        if self.dry_run:
            self.print_dry_run_warning(cmd)
            return
        print("Creating CVS tags...")
        for branch in self.cvs_branches:
            branch_dir = os.path.join(self.working_dir, self.project_name,
                    branch)
            os.chdir(branch_dir)
            (status, output) = commands.getstatusoutput(cmd)
            print(output)
            if status > 1:
                self.cleanup()
                sys.exit(1)

    def _cvs_make_build(self):
        """ Build srpm and submit to build system. """
        cmd = "BUILD_FLAGS=--nowait make build"
        if self.dry_run:
            self.print_dry_run_warning(cmd)
            return
        os.chdir(self.package_workdir)
        print("Submitting CVS builds...")
        for branch in self.cvs_branches:
            branch_dir = os.path.join(self.working_dir, self.project_name,
                    branch)
            os.chdir(branch_dir)
            output = run_command(cmd)
            print(output)


class KojiReleaser(Releaser):
    """
    Releaser for the Koji build system.

    WARNING: this is more of use to people running their own Koji instance.
    Fedora projects will most likely want to use the Fedora git releaser.
    """

    REQUIRED_CONFIG = ['autobuild_tags']

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            pkg_config=None, global_config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False):
        Releaser.__init__(self, name, version, tag, build_dir, pkg_config,
                global_config, user_config, target, releaser_config, no_cleanup)

        self.only_tags = []
        if 'ONLY_TAGS' in os.environ:
            self.only_tags = os.environ['ONLY_TAGS'].split(' ')

        self.skip_srpm = False

    def release(self, dry_run=False):
        self.dry_run = dry_run

        self._koji_release()

    def _koji_release(self):
        """
        Lookup autobuild Koji tags from global config, create srpms with
        appropriate disttags, and submit builds to Koji.
        """
        autobuild_tags = self.releaser_config.get(self.target, "autobuild_tags")
        print("Building release in Koji...")
        debug("Koji tags: %s" % autobuild_tags)
        koji_tags = autobuild_tags.strip().split(" ")

        koji_opts = DEFAULT_KOJI_OPTS
        if 'KOJI_OPTIONS' in self.builder.user_config:
            koji_opts = self.builder.user_config['KOJI_OPTIONS']

        if 'SCRATCH' in os.environ and os.environ['SCRATCH'] == '1':
            koji_opts = ' '.join([koji_opts, '--scratch'])

        # TODO: need to re-do this metaphor to use release targets instead:
        for koji_tag in koji_tags:
            if self.only_tags and koji_tag not in self.only_tags:
                continue
            # Lookup the disttag configured for this Koji tag:
            disttag = self.builder.config.get(koji_tag, "disttag")
            if self.builder.config.has_option(koji_tag, "whitelist"):
                # whitelist implies only those packages can be built to the
                # tag,regardless if blacklist is also defined.
                if not self.__is_whitelisted(koji_tag):
                    print("WARNING: %s not specified in whitelist for %s" % (
                        self.project_name, koji_tag))
                    print("   Package *NOT* submitted to Koji.")
                    continue
            elif self.__is_blacklisted(koji_tag):
                print("WARNING: %s specified in blacklist for %s" % (
                    self.project_name, koji_tag))
                print("   Package *NOT* submitted to Koji.")
                continue

            # Getting tricky here, normally Builder's are only used to
            # create one rpm and then exit. Here we're going to try
            # to run multiple srpm builds:
            if not self.skip_srpm:
                self.builder.srpm(dist=disttag, reuse_cvs_checkout=True)

            self._submit_build("koji", koji_opts, koji_tag)

    def __is_whitelisted(self, koji_tag):
        """ Return true if package is whitelisted in tito.props"""
        return self.builder.config.has_option(koji_tag, "whitelist") and \
            self.project_name in self.builder.config.get(koji_tag,
                        "whitelist").strip().split(" ")

    def __is_blacklisted(self, koji_tag):
        """ Return true if package is blacklisted in tito.props"""
        return self.builder.config.has_option(koji_tag, "blacklist") and \
            self.project_name in self.builder.config.get(koji_tag,
                        "blacklist").strip().split(" ")

    def _submit_build(self, executable, koji_opts, tag):
        """ Submit srpm to brew/koji. """
        cmd = "%s %s %s %s" % (executable, koji_opts, tag, self.builder.srpm_location)
        print("\nSubmitting build with: %s" % cmd)

        if self.dry_run:
            self.print_dry_run_warning(cmd)
            return

        output = run_command(cmd)
        print(output)


class KojiGitReleaser(KojiReleaser):
    """
    A derivative of the Koji releaser which uses a git repository to build off,
    rather than submitting srpms.
    """

    REQUIRED_CONFIG = ['autobuild_tags', 'git_url']

    def _koji_release(self):
        self.skip_srpm = True
        KojiReleaser._koji_release(self)

    def _submit_build(self, executable, koji_opts, tag):
        """ Submit build to koji. """
        cmd = "%s %s %s %s/#%s" % \
                (executable, koji_opts, tag,
                        self.releaser_config.get(self.target, 'git_url'),
                        self.builder.build_tag)
        print("\nSubmitting build with: %s" % cmd)

        if self.dry_run:
            self.print_dry_run_warning(cmd)
            return

        output = run_command(cmd)
        print(output)


class BuildTargetParser(object):
    """
    Parses build targets from a string in the format of:
        <branch1>:<target> <branch2>:<target> ...

    Each target must be associated with a valid branch.
    """

    def __init__(self, releaser_config, release_target, valid_branches):
        self.releaser_config = releaser_config
        self.release_target = release_target
        self.valid_branches = valid_branches

    def get_build_targets(self):
        build_targets = {}
        if not self.releaser_config.has_option(self.release_target, "build_targets"):
            return build_targets

        defined_build_targets = self.releaser_config.get(self.release_target,
                                                         "build_targets").split(" ")
        for build_target in defined_build_targets:
            # Ignore any empty from multiple spaces in the file.
            if not build_target:
                continue

            branch, target = self._parse_build_target(build_target)
            build_targets[branch] = target

        return build_targets

    def _parse_build_target(self, build_target):
        """ Parses a string in the format of branch:target """
        if not build_target:
            raise TitoException("Invalid build_target: %s. Format: <branch>:<target>"
                                % build_target)

        parts = build_target.split(":")
        if len(parts) != 2:
            raise TitoException("Invalid build_target: %s. Format: <branch>:<target>"
                                % build_target)
        branch = parts[0]
        if not branch in self.valid_branches:
            raise TitoException("Invalid build_target: %s. Unknown branch reference."
                                % build_target)
        target = parts[1]
        if not target:
            raise TitoException("Invalid build_target: %s. Empty target" % build_target)

        return (branch, target)
