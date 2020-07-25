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
import rpm

from tempfile import mkdtemp
import shutil

from tito.common import create_builder, debug, \
    run_command, get_project_name, warn_out, error_out
from tito.compat import PY2, dictionary_override
from tito.exception import TitoException
from tito.config_object import ConfigObject

# List of files to protect when syncing:
PROTECTED_BUILD_SYS_FILES = ('branch', 'Makefile', 'sources', ".git", ".gitignore", ".osc", "tito-mead-url", "tests", "gating.yaml")

RSYNC_USERNAME = 'RSYNC_USERNAME'  # environment variable name


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
            config_builder_args['test'] = [True]  # builder must know to build from HEAD

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

        yes = ['y', 'yes', 'ok', 'sure']
        no = ['n', 'no', 'nah', 'nope']
        answers = yes + no

        while True:
            input_function = raw_input if PY2 else input
            answer = input_function(prompt).lower()
            if answer in answers:
                return answer in yes

    def _check_releaser_config(self):
        """
        Verify this release target has all the config options it needs.
        """
        for opt in self.GLOBAL_REQUIRED_CONFIG:
            if not self.releaser_config.has_option(self.target, opt):
                error_out("Release target '%s' missing required option '%s'" %
                    (self.target, opt))
        for opt in self.REQUIRED_CONFIG:
            if not self.releaser_config.has_option(self.target, opt):
                error_out("Release target '%s' missing required option '%s'" %
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
                prefix, delimiter, opt_name = opt.partition('.')
                args.setdefault(opt_name, []).append(releaser_config.get(target, opt))
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
            warn_out("leaving %s (--no-cleanup)" % self.working_dir)

    def print_dry_run_warning(self, command_that_would_be_run_otherwise):
        print
        warn_out("Skipping command due to --dry-run: %s" %
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
    REQUIRED_CONFIG = ['rsync', 'builder', 'srpm_disttag']

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
            warn_out("please rename 'scl' to 'builder.scl' in releasers.conf")
            self.builder.scl = self.releaser_config.get(self.target, "scl")

    def release(self, dry_run=False, no_build=False, scratch=False):
        self.dry_run = dry_run

        # Should this run?
        self.builder.no_cleanup = self.no_cleanup
        self.builder.tgz()

        # Check if the releaser specifies a srpm disttag:
        srpm_disttag = None
        if self.releaser_config.has_option(self.target, "srpm_disttag"):
            srpm_disttag = self.releaser_config.get(self.target, "srpm_disttag")
        self.builder.srpm(dist=srpm_disttag)

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
            warn_out("leaving %s (--no-cleanup)" % temp_dir)

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

    # By default run createrepo_c without any paramaters
    createrepo_command = "createrepo_c ."

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


class KojiReleaser(Releaser):
    """
    Releaser for the Koji build system.

    WARNING: this is more of use to people running their own Koji instance.
    Fedora projects will most likely want to use the Fedora git releaser.
    """

    REQUIRED_CONFIG = ['autobuild_tags']
    NAME = "Koji"
    DEFAULT_KOJI_OPTS = "build --nowait"

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):
        Releaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test, auto_accept,
                **kwargs)

        if self.releaser_config.has_option(self.target, "koji_profile"):
            self.profile = self.releaser_config.get(self.target, "koji_profile")
        else:
            self.profile = None

        if self.releaser_config.has_option(self.target, "koji_config_file"):
            self.conf_file = self.releaser_config.get(self.target, "koji_config_file")
        else:
            self.conf_file = None

        self.executable = "koji"

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

        koji_opts = self.DEFAULT_KOJI_OPTS
        if 'KOJI_OPTIONS' in self.builder.user_config:
            koji_opts = self.builder.user_config['KOJI_OPTIONS']

        scratch = self.scratch or ('SCRATCH' in os.environ and os.environ['SCRATCH'] == '1')
        if scratch:
            koji_opts = ' '.join([koji_opts, '--scratch'])

        if scratch and (self.test or self.builder.test):
            koji_opts = ' '.join([koji_opts, '--no-rebuild-srpm'])

        if self.profile:
            koji_opts = ' '.join(['--profile', self.profile, koji_opts])

        if self.conf_file:
            koji_opts = ' '.join(['--config', self.conf_file, koji_opts])

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
                    warn_out([
                        "%s not specified in whitelist for %s" % (self.project_name, koji_tag),
                        "   Package *NOT* submitted to %s." % self.NAME,
                    ])
                    continue
            elif self.__is_blacklisted(koji_tag, scl):
                warn_out([
                    "%s specified in blacklist for %s" % (self.project_name, koji_tag),
                    "   Package *NOT* submitted to %s." % self.NAME,
                ])
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

            self._submit_build(self.executable, koji_opts, koji_tag, builder.srpm_location)

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
