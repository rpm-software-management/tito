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
"""
Code for submitting builds for release.
"""

import copy
import os
import sys
import tempfile
import subprocess
import rpm

from tempfile import mkdtemp
import shutil

from tito.common import *
from tito.compat import *
from tito.buildparser import BuildTargetParser
from tito.exception import TitoException
from tito.config_object import ConfigObject

DEFAULT_KOJI_OPTS = "build --nowait"

# List of files to protect when syncing:
PROTECTED_BUILD_SYS_FILES = ('branch', 'Makefile', 'sources', ".git", ".gitignore", ".osc")

RSYNC_USERNAME = 'RSYNC_USERNAME'  # environment variable name


def extract_task_info(output):
    """ Extracts task ID and URL from koji/brew build output. """
    task_lines = []
    for line in output.splitlines():
        if "Created task" in line:
            task_lines.append(line)
        elif "Task info" in line:
            task_lines.append(line)
    return task_lines


class Releaser(ConfigObject):
    """
    Parent class of all releasers.

    Can't really be used by itself, need to use one of the sub-classes.
    """
    GLOBAL_REQUIRED_CONFIG = ['releaser']
    REQUIRED_CONFIG = []
    OPTIONAL_CONFIG = []

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):

        ConfigObject.__init__(self, config=config)
        config_builder_args = self._parse_builder_args(releaser_config, target)
        if test:
            config_builder_args['test'] = True  # builder must know to build from HEAD

        # Override with builder args from command line if any were given:
        if 'builder_args' in kwargs:
            # (in case of dupes, last one wins)
            self.builder_args = dictionary_override(
                config_builder_args,
                kwargs['builder_args']
            )
        else:
            self.builder_args = config_builder_args

        # While we create a builder here, we don't actually call run on it
        # unless the releaser needs to:
        self.offline = False
        if 'offline' in kwargs:
            self.offline = kwargs['offline']

        # Config for all releasers:
        self.releaser_config = releaser_config

        # The actual release target we're building:
        self.target = target

        # Use the builder from the release target, rather than the default
        # one defined for this git repo or sub-package:
        builder_class = None
        if self.releaser_config.has_option(self.target, 'builder'):
            builder_class = self.releaser_config.get(self.target, 'builder')
        self.builder = create_builder(name, tag,
                config,
                build_dir, user_config, self.builder_args,
                builder_class=builder_class, offline=self.offline)

        self.project_name = self.builder.project_name

        self.working_dir = mkdtemp(dir=self.builder.rpmbuild_basedir,
                prefix="release-%s" % self.builder.project_name)
        print("Working in: %s" % self.working_dir)

        self.dry_run = False
        self.test = test  # releaser must know to use builder designation rather than tag
        self.auto_accept = auto_accept  # don't ask for input, just go ahead
        self.no_cleanup = no_cleanup

        self._check_releaser_config()

    def _ask_yes_no(self, prompt="Y/N? ", default_auto_answer=True):
        if self.auto_accept:
            return default_auto_answer
        else:
            answer = raw_input(prompt)
            return answer.lower() in ['y', 'yes', 'ok', 'sure']

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
        # for opt in self.releaser_config.options(self.target):
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

    def release(self, dry_run=False, no_build=False, scratch=False):
        pass

    def cleanup(self):
        if not self.no_cleanup:
            debug("Cleaning up [%s]" % self.working_dir)
            run_command("rm -rf %s" % self.working_dir)

            if self.builder:
                self.builder.cleanup()
        else:
            print("WARNING: leaving %s (--no-cleanup)" % self.working_dir)

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
                copied_files.append(base_filename)

            cmd = "cp %s %s" % (copy_me, dest_path)
            run_command(cmd)

        # Track filenames that will need to be deleted by the caller.
        for filename in os.listdir(dest_dir):
            if filename not in PROTECTED_BUILD_SYS_FILES and \
                    filename not in filenames_to_copy:
                print("   deleting: %s" % filename)
                old_files.append(filename)

        return new_files, copied_files, old_files


class RsyncReleaser(Releaser):
    """
    A releaser which will rsync from a remote host, build the desired packages,
    plug them in, and upload to server.

    Building of the packages is done via mock.

    WARNING: This will not work in all
    situations, depending on the current OS, and the mock target you
    are attempting to use.
    """
    REQUIRED_CONFIG = ['rsync', 'builder']

    # Default list of packages to copy
    filetypes = ['rpm', 'srpm', 'tgz']

    # By default run rsync with these paramaters
    rsync_args = "-rlvz"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False,
            prefix="temp_dir=", **kwargs):
        Releaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test,
                auto_accept, **kwargs)

        self.build_dir = build_dir
        self.prefix = prefix

        if self.releaser_config.has_option(self.target, "scl"):
            sys.stderr.write("WARNING: please rename 'scl' to "
                "'builder.scl' in releasers.conf\n")
            self.builder.scl = self.releaser_config.get(self.target, "scl")

    def release(self, dry_run=False, no_build=False, scratch=False):
        self.dry_run = dry_run

        # Should this run?
        self.builder.no_cleanup = self.no_cleanup
        self.builder.tgz()
        self.builder.srpm()
        self.builder.rpm()
        self.builder.cleanup()

        if self.releaser_config.has_option(self.target, 'rsync_args'):
            self.rsync_args = self.releaser_config.get(self.target, 'rsync_args')

        rsync_locations = self.releaser_config.get(self.target, 'rsync').split(" ")
        for rsync_location in rsync_locations:
            if RSYNC_USERNAME in os.environ:
                print("%s set, using rsync username: %s" % (RSYNC_USERNAME,
                        os.environ[RSYNC_USERNAME]))
                rsync_location = "%s@%s" % (os.environ[RSYNC_USERNAME], rsync_location)

            # Make a temp directory to sync the existing repo contents into:
            temp_dir = mkdtemp(dir=self.build_dir, prefix=self.prefix)

            self._rsync_from_remote(self.rsync_args, rsync_location, temp_dir)
            self._copy_files_to_temp_dir(temp_dir)
            self.process_packages(temp_dir)
            self.rsync_to_remote(self.rsync_args, temp_dir, rsync_location)

    def _rsync_from_remote(self, rsync_args, rsync_location, temp_dir):
        os.chdir(temp_dir)
        print("rsync %s %s %s" % (rsync_args, rsync_location, temp_dir))
        output = run_command("rsync %s %s %s" % (rsync_args, rsync_location, temp_dir))
        debug(output)

    def rsync_to_remote(self, rsync_args, temp_dir, rsync_location):
        print("rsync %s --delete %s/ %s" % (rsync_args, temp_dir, rsync_location))
        os.chdir(temp_dir)
        # TODO: configurable rsync options?
        cmd = "rsync %s --delete %s/ %s" % (rsync_args, temp_dir, rsync_location)
        if self.dry_run:
            self.print_dry_run_warning(cmd)
        else:
            output = run_command(cmd)
            debug(output)
        if not self.no_cleanup:
            debug("Cleaning up [%s]" % temp_dir)
            os.chdir("/")
            shutil.rmtree(temp_dir)
        else:
            print("WARNING: leaving %s (--no-cleanup)" % temp_dir)

    def _copy_files_to_temp_dir(self, temp_dir):
        os.chdir(temp_dir)

        # overwrite default self.filetypes if filetypes option is specified in config
        if self.releaser_config.has_option(self.target, 'filetypes'):
            self.filetypes = self.releaser_config.get(self.target, 'filetypes').split(" ")

        for artifact in self.builder.artifacts:
            if artifact.endswith('.tar.gz'):
                artifact_type = 'tgz'
            elif artifact.endswith('src.rpm'):
                artifact_type = 'srpm'
            elif artifact.endswith('.rpm'):
                artifact_type = 'rpm'
            else:
                continue

            if artifact_type in self.filetypes:
                print("copy: %s > %s" % (artifact, temp_dir))
                shutil.copy(artifact, temp_dir)

    def process_packages(self, temp_dir):
        """ no-op. This will be overloaded by a subclass if needed. """
        pass

    def cleanup(self):
        """ No-op, we clean up during self.release() """
        pass


class YumRepoReleaser(RsyncReleaser):
    """
    A releaser which will rsync down a yum repo, build the desired packages,
    plug them in, update the repodata, and push the yum repo back out.

    Building of the packages is done via mock.

    WARNING: This will not work in all
    situations, depending on the current OS, and the mock target you
    are attempting to use.
    """

    # Default list of packages to copy
    filetypes = ['rpm']

    # By default run createrepo without any paramaters
    createrepo_command = "createrepo ."

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        RsyncReleaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test, auto_accept,
                prefix="yumrepo-", **kwargs)

    def _read_rpm_header(self, ts, new_rpm_path):
        """
        Read RPM header for the given file.
        """
        fd = os.open(new_rpm_path, os.O_RDONLY)
        header = ts.hdrFromFdno(fd)
        os.close(fd)
        return header

    def process_packages(self, temp_dir):
        self.prune_other_versions(temp_dir)
        print("Refreshing yum repodata...")
        if self.releaser_config.has_option(self.target, 'createrepo_command'):
            self.createrepo_command = self.releaser_config.get(self.target, 'createrepo_command')
        os.chdir(temp_dir)
        output = run_command(self.createrepo_command)
        debug(output)

    def prune_other_versions(self, temp_dir):
        """
        Cleanout any other version of the package we just built.

        Both older and newer packages will be removed (can be used
        to downgrade the contents of a yum repo).
        """
        os.chdir(temp_dir)
        rpm_ts = rpm.TransactionSet()
        self.new_rpm_dep_sets = {}
        for artifact in self.builder.artifacts:
            if artifact.endswith(".rpm") and not artifact.endswith(".src.rpm"):
                try:
                    header = self._read_rpm_header(rpm_ts, artifact)
                except rpm.error:
                    continue
                self.new_rpm_dep_sets[header['name']] = header.dsOfHeader()

        # Now cleanout any other version of the package we just built,
        # both older or newer. (can be used to downgrade the contents
        # of a yum repo)
        for filename in os.listdir(temp_dir):
            if not filename.endswith(".rpm"):
                continue
            full_path = os.path.join(temp_dir, filename)
            try:
                hdr = self._read_rpm_header(rpm_ts, full_path)
            except rpm.error:
                e = sys.exc_info()[1]
                print("error reading rpm header in '%s': %s" % (full_path, e))
                continue
            if hdr['name'] in self.new_rpm_dep_sets:
                dep_set = hdr.dsOfHeader()
                if dep_set.EVR() < self.new_rpm_dep_sets[hdr['name']].EVR():
                    print("Deleting old package: %s" % filename)
                    run_command("rm %s" % os.path.join(temp_dir,
                        filename))


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
        os.chdir(self.working_dir)
        run_command("%s clone %s" % (self.cli_tool, self.project_name))

        project_checkout = os.path.join(self.working_dir, self.project_name)
        os.chdir(project_checkout)
        run_command("%s switch-branch %s" % (self.cli_tool, self.git_branches[0]))

        self.builder.tgz()
        if self.test:
            self.builder._setup_test_specfile()

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
        write(fd, "Update %s to %s\n" % (self.project_name,
            self.builder.build_version))
        # Write out Resolves line for all bugzillas we see in commit diff:
        for line in extract_bzs(diff_output):
            write(fd, line + "\n")

        print("")
        print("##### Commit message: #####")
        print("")

        os.lseek(fd, 0, 0)
        file = os.fdopen(fd)
        for line in file.readlines():
            print(line)
        file.close()

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
        (status, diff_output) = getstatusoutput("git diff --cached")
        if diff_output.strip() == "":
            debug("git diff --cached returned nothing, falling back to git diff.")
            (status, diff_output) = getstatusoutput("git diff")

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
                output = run_command(cmd)

            os.unlink(commit_msg_file)

        cmd = "%s push" % self.cli_tool
        if self.dry_run:
            self.print_dry_run_warning(cmd)
        else:
            # Push
            print(cmd)
            run_command(cmd)

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
                run_command(cmd)

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


class KojiReleaser(Releaser):
    """
    Releaser for the Koji build system.

    WARNING: this is more of use to people running their own Koji instance.
    Fedora projects will most likely want to use the Fedora git releaser.
    """

    REQUIRED_CONFIG = ['autobuild_tags']
    NAME = "Koji"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        Releaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test, auto_accept,
                **kwargs)

        self.only_tags = []
        if 'ONLY_TAGS' in os.environ:
            self.only_tags = os.environ['ONLY_TAGS'].split(' ')

        self.skip_srpm = False

    def release(self, dry_run=False, no_build=False, scratch=False):
        self.dry_run = dry_run
        self.scratch = scratch

        self._koji_release()

    def autobuild_tags(self):
        """ will return list of tags for which we are building """
        result = self.releaser_config.get(self.target, "autobuild_tags")
        return result.strip().split(" ")

    def _koji_release(self):
        """
        Lookup autobuild Koji tags from global config, create srpms with
        appropriate disttags, and submit builds to Koji.
        """
        koji_tags = self.autobuild_tags()
        print("Building release in %s..." % self.NAME)
        debug("%s tags: %s" % (self.NAME, koji_tags))

        koji_opts = DEFAULT_KOJI_OPTS
        if 'KOJI_OPTIONS' in self.builder.user_config:
            koji_opts = self.builder.user_config['KOJI_OPTIONS']

        if self.scratch or ('SCRATCH' in os.environ and os.environ['SCRATCH'] == '1'):
            koji_opts = ' '.join([koji_opts, '--scratch'])

        # TODO: need to re-do this metaphor to use release targets instead:
        for koji_tag in koji_tags:
            if self.only_tags and koji_tag not in self.only_tags:
                continue
            scl = None
            if self.builder.config.has_option(koji_tag, "scl"):
                scl = self.builder.config.get(koji_tag, "scl")
            # Lookup the disttag configured for this Koji tag:
            if self.builder.config.has_option(koji_tag, "disttag"):
                disttag = self.builder.config.get(koji_tag, "disttag")
            else:
                disttag = ''
            if self.builder.config.has_option(koji_tag, "whitelist"):
                # whitelist implies only those packages can be built to the
                # tag,regardless if blacklist is also defined.
                if not self.__is_whitelisted(koji_tag, scl):
                    print("WARNING: %s not specified in whitelist for %s" % (
                        self.project_name, koji_tag))
                    print("   Package *NOT* submitted to %s." % self.NAME)
                    continue
            elif self.__is_blacklisted(koji_tag, scl):
                print("WARNING: %s specified in blacklist for %s" % (
                    self.project_name, koji_tag))
                print("   Package *NOT* submitted to %s." % self.NAME)
                continue

            # Getting tricky here, normally Builder's are only used to
            # create one rpm and then exit. Here we're going to try
            # to run multiple srpm builds:
            builder = self.builder
            if not self.skip_srpm:
                if scl:
                    builder = copy.copy(self.builder)
                    builder.scl = scl
                builder.srpm(dist=disttag)

            self._submit_build("koji", koji_opts, koji_tag, builder.srpm_location)

    def __is_whitelisted(self, koji_tag, scl):
        """ Return true if package is whitelisted in tito.props"""
        return self.builder.config.has_option(koji_tag, "whitelist") and \
            get_project_name(self.builder.build_tag, scl) in self.builder.config.get(koji_tag,
                        "whitelist").strip().split()

    def __is_blacklisted(self, koji_tag, scl):
        """ Return true if package is blacklisted in tito.props"""
        return self.builder.config.has_option(koji_tag, "blacklist") and \
            get_project_name(self.builder.build_tag, scl) in self.builder.config.get(koji_tag,
                        "blacklist").strip().split()

    def _submit_build(self, executable, koji_opts, tag, srpm_location):
        """ Submit srpm to brew/koji. """
        cmd = "%s %s %s %s" % (executable, koji_opts, tag, srpm_location)
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

    def _submit_build(self, executable, koji_opts, tag, srpm_location):
        """
        Submit build to koji using the git URL from config. We will ignore
        srpm_location here.

        NOTE: overrides KojiReleaser._submit_build.
        """
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
