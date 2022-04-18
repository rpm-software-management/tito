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
Tito builders for a variety of common methods of building sources, srpms,
and rpms.
"""

import gzip
import os
import sys
import re
import shutil
import rpm
from pkg_resources import require
from distutils.version import LooseVersion as loose_version
from tempfile import mkdtemp

from tito.common import scl_to_rpm_option, get_latest_tagged_version, \
    find_wrote_in_rpmbuild_output, debug, error_out, run_command_print, \
    find_spec_file, run_command, get_build_commit, get_relative_project_dir, \
    get_relative_project_dir_cwd, get_spec_version_and_release, \
    check_tag_exists, create_tgz, get_latest_commit, \
    get_commit_count, find_gemspec_file, create_builder, compare_version,\
    find_cheetah_template_file, render_cheetah, replace_spec_release, \
    find_spec_like_file, warn_out, get_commit_timestamp, chdir, mkdir_p, \
    find_git_root, info_out, munge_specfile, BUILDCONFIG_SECTION
from tito.compat import getstatusoutput, getoutput, urlparse, urlretrieve
from tito.exception import RunCommandException
from tito.exception import TitoException
from tito.config_object import ConfigObject
from tito.tar import TarFixer


class BuilderBase(object):
    """
    A base class for all builders.

    Handles things we will *always* do, primarily handling temporary directories
    for rpmbuild.

    This class should *not* assume we're even using git.
    """
    REQUIRED_ARGS = []

    # TODO: merge config into an object and kill the ConfigObject parent class
    def __init__(self, name=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        # Project directory where we started this build:
        self.start_dir = os.getcwd()

        self.project_name = name
        self.user_config = user_config
        self.args = args
        self.kwargs = kwargs
        self.config = config

        # Optional keyword arguments:
        self.dist = self._get_optional_arg(kwargs, 'dist', None)

        self.offline = self._get_optional_arg(kwargs, 'offline', False)
        self.auto_install = self._get_optional_arg(kwargs, 'auto_install',
                False)
        self.escalate_privileges = self._get_optional_arg(kwargs, 'escalate',
                True)
        self.scl = self._get_optional_arg(args, 'scl', [None])[0] or \
                self._get_optional_arg(kwargs, 'scl', '')

        self.quiet = self._get_optional_arg(kwargs, 'quiet', False)
        self.verbose = self._get_optional_arg(kwargs, 'verbose', False)

        # The default for the builder instantiated from Releasers
        config_fetch_default = False
        if self.config.has_option(BUILDCONFIG_SECTION, "fetch_sources"):
            config_fetch_default = self.config.get(BUILDCONFIG_SECTION, "fetch_sources")
        self.fetch_sources = self._get_optional_arg(kwargs, 'fetch_sources', config_fetch_default)

        rpmbuildopts = self._get_optional_arg(args, 'rpmbuild_options', None)
        if rpmbuildopts:
            self.rpmbuild_options = ' '.join(rpmbuildopts)
        else:
            self.rpmbuild_options = self._get_optional_arg(kwargs, 'rpmbuild_options', '')

        if self.fetch_sources:
            self.rpmbuild_options += "--define '%_disable_source_fetch 0'"

        self.test = self._get_optional_arg(kwargs, 'test', False)
        # Allow a builder arg to override the test setting passed in, used by
        # releasers in their config sections.
        if args and 'test' in args:
            self.test = True

        # Location where we do all tito work and store resulting rpms:
        self.rpmbuild_basedir = build_dir
        # Location where we do actual rpmbuilds
        self.rpmbuild_dir = mkdtemp(dir=self.rpmbuild_basedir,
            prefix="rpmbuild-%s" % self.project_name)
        debug("Building in temp dir: %s" % self.rpmbuild_dir)
        self.rpmbuild_sourcedir = os.path.join(self.rpmbuild_dir, "SOURCES")
        self.rpmbuild_builddir = os.path.join(self.rpmbuild_dir, "BUILD")

        self._check_required_args()

        # Set to true once we've created/setup sources: (i.e. tar.gz)
        self.ran_tgz = False

        self.no_cleanup = False

        # List of full path to all sources for this package.
        self.sources = []

        # Artifacts we built:
        self.artifacts = []

        # Use most suitable package manager for current OS
        self.package_manager = package_manager()

    def _get_optional_arg(self, kwargs, arg, default):
        """
        Return the value of an optional keyword argument if it's present,
        otherwise the default provided.
        """
        if arg in kwargs:
            return kwargs[arg]
        return default

    def _check_required_args(self):
        for arg in self.REQUIRED_ARGS:
            if arg not in self.args:
                raise TitoException("Builder missing required argument: %s" %
                        arg)

    def run(self, options):
        """
        Perform the actions requested of the builder.

        NOTE: this method may do nothing if the user requested no build actions
        be performed. (i.e. only release tagging, etc)
        """
        info_out("Building package [%s]" % (self.build_tag))
        self.no_cleanup = options.no_cleanup

        # Reset list of artifacts on each call to run().
        self.artifacts = []

        try:
            try:
                if options.tgz:
                    self.tgz()
                if options.srpm:
                    self.srpm()
                if options.rpm:
                    # TODO: not protected anymore
                    self.rpm()
                    self._auto_install()
            except KeyboardInterrupt:
                print("Interrupted, cleaning up...")
        finally:
            self.cleanup()

        return self.artifacts

    def cleanup(self):
        """
        Remove all temporary files and directories.
        """
        if not self.no_cleanup:
            debug("Cleaning up %s" % self.rpmbuild_dir)
            shutil.rmtree(self.rpmbuild_dir)
        else:
            warn_out("Leaving rpmbuild files in: %s" % self.rpmbuild_dir)

    def _check_build_dirs_access(self, build_dirs):
        """
        Ensure the build directories are writable.
        """
        msgs = []
        for d in build_dirs:
            if not os.access(d, os.W_OK):
                msgs.append("%s is not writable." % d)
        if msgs:
            error_out(msgs)

    def _create_build_dirs(self):
        """
        Create the build directories. Can safely be called multiple times.
        """
        build_dirs = [
            self.rpmbuild_basedir,
            self.rpmbuild_dir,
            self.rpmbuild_sourcedir,
            self.rpmbuild_builddir,
        ]
        for d in build_dirs:
            mkdir_p(d)
        self._check_build_dirs_access(build_dirs)

    def copy_extra_sources(self):
        """
        Copy extra %{SOURCEX} files to the SOURCE folder.
        """
        return NotImplemented

    def srpm(self, dist=None):
        """
        Build a source RPM.
        """
        self._create_build_dirs()
        if not self.ran_tgz:
            self.tgz()

        if self.test:
            self._setup_test_specfile()

        self.copy_extra_sources()

        debug("Creating srpm from spec file: %s" % self.spec_file)
        define_dist = ""
        if self.dist:
            debug("using self.dist: %s" % self.dist)
            define_dist = "--define 'dist %s'" % self.dist
        elif dist:
            debug("using dist: %s" % dist)
            define_dist = "--define 'dist %s'" % dist
        else:
            debug("*NOT* using dist at all")

        rpmbuild_options = self.rpmbuild_options + self._scl_to_rpmbuild_option()

        cmd = ('rpmbuild %s %s %s --nodeps -bs %s' % (
               rpmbuild_options, self._get_rpmbuild_dir_options(),
               define_dist, self.spec_file))

        run_command_func = run_command if self.quiet else run_command_print
        output = run_command_func(cmd)
        self.srpm_location = find_wrote_in_rpmbuild_output(output)[0]
        self.artifacts.append(self.srpm_location)

    # Assume that if tito's --no-cleanup option is set, also disable %clean in rpmbuild:
    def _get_clean_option(self):
        if self.no_cleanup:
            output = run_command('rpmbuild --help')
            if '--noclean' in output:
                return "--noclean"
            else:
                return ""
        else:
            return "--clean"

    def _get_verbosity_option(self):
        if self.verbose:
            return "--verbose"
        else:
            return ""

    def rpm(self):
        """ Build an RPM. """
        self._create_build_dirs()
        if not self.ran_tgz:
            self.tgz()
        self.copy_extra_sources()

        cmd = 'rpmbuild {0}'.format(
            " ".join([
                self.rpmbuild_options,
                self._scl_to_rpmbuild_option(),
                self._get_rpmbuild_dir_options(),
                "--define 'dist {0}'".format(self.dist) if self.dist else "",
                self._get_clean_option(),
                self._get_verbosity_option(),
                '-ba {0}'.format(self.spec_file),
            ])
        )
        try:
            if self.quiet:
                output = run_command(cmd)
            else:
                output = run_command_print(cmd)
        except (KeyboardInterrupt, SystemExit):
            print("")
            exit(1)
        except RunCommandException:
            err = sys.exc_info()[1]
            msg = str(err)
            if re.search('Failed build dependencies', err.output):
                cmd = self.package_manager.builddep(find_spec_file(self.relative_project_dir))
                msg = "Please run '%s' as root." % cmd
            error_out('%s' % msg)
        except Exception:
            err = sys.exc_info()[1]
            error_out('%s' % str(err))
        files_written = find_wrote_in_rpmbuild_output(output)
        if len(files_written) < 2:
            error_out("Error parsing rpmbuild output")
        self.srpm_location = files_written[0]
        self.artifacts.extend(files_written)

        print
        info_out("Successfully built: %s" % '\n\t- '.join(files_written))

    def _scl_to_rpmbuild_option(self):
        """ Returns rpmbuild option which disable or enable SC and print warning if needed """
        return scl_to_rpm_option(self.scl)

    def _auto_install(self):
        """
        If requested, auto install the RPMs we just built.
        """
        if self.auto_install:
            print
            print("Auto-installing packages:")
            print

            dont_install = []
            if 'NO_AUTO_INSTALL' in self.user_config:
                dont_install = self.user_config['NO_AUTO_INSTALL'].split(" ")
                debug("Will not auto-install any packages matching: %s" % dont_install)

            do_install = []
            for to_inst in self.artifacts:
                # Only install rpms:
                if not to_inst.endswith(".rpm") or to_inst.endswith(".src.rpm"):
                    continue

                install = True
                for skip in dont_install:
                    if skip in to_inst:
                        install = False
                        print("Skipping: %s" % to_inst)
                        break
                if install:
                    do_install.append(to_inst)

            print
            reinstall = self.package_manager.is_installed(self.project_name, self.build_version)
            cmd = self.package_manager.install(do_install, reinstall=reinstall, auto=True, offline=True,
                                               escalate=self.escalate_privileges)
            print("%s" % cmd)
            try:
                run_command_print(cmd)
                print
            except KeyboardInterrupt:
                pass


class Builder(ConfigObject, BuilderBase):
    """
    Parent builder class.

    Includes functionality for a standard Spacewalk package build. Packages
    which require other unusual behavior can subclass this to inject the
    desired behavior.
    """
    REQUIRED_ARGS = []

    # TODO: drop version
    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        """
        name - Package name that is being built.

        version - Version and release being built.

        tag - The git tag being built.

        build_dir - Temporary build directory where we can safely work.

        config - Merged configuration. (global plus package specific)

        user_config - User configuration from ~/.titorc.

        args - Optional arguments specific to each builder. Can be passed
        in explicitly by user on the CLI, or via a release target config
        entry. Only for things which vary on invocations of the builder,
        avoid using these if possible.  *Given in the format of a dictionary
        of lists.*
        """
        ConfigObject.__init__(self, config=config)
        BuilderBase.__init__(self, name=name, build_dir=build_dir, config=config,
                user_config=user_config, args=args, **kwargs)
        self.build_tag = tag

        self.build_version = self._get_build_version()

        if kwargs and 'options' in kwargs:
            warn_out("'options' no longer a supported builder constructor argument.")

        if self.config.has_section("requirements"):
            if self.config.has_option("requirements", "tito"):
                if loose_version(self.config.get("requirements", "tito")) > \
                        loose_version(require('tito')[0].version):
                    error_out([
                        "tito version %s or later is needed to build this project." %
                        self.config.get("requirements", "tito"),
                        "Your version: %s" % require('tito')[0].version
                    ])

        self.display_version = self._get_display_version()

        with chdir(find_git_root()):
            self.git_commit_id = get_build_commit(tag=self.build_tag,
                test=self.test)

        self.relative_project_dir = get_relative_project_dir(
            project_name=self.project_name, commit=self.git_commit_id)
        if self.relative_project_dir is None and self.test:
            warn_out(".tito/packages/%s doesn't exist "
                "in git, using current directory" % self.project_name)
            self.relative_project_dir = get_relative_project_dir_cwd(
                self.git_root)

        tgz_base = self._get_tgz_name_and_ver()
        self.tgz_filename = tgz_base + ".tar.gz"
        self.tgz_dir = tgz_base
        self.artifacts = []

        # A copy of the git code from commit we're building:
        self.rpmbuild_gitcopy = os.path.join(self.rpmbuild_sourcedir,
                self.tgz_dir)

        # Used to make sure we only modify the spec file for a test build
        # once. The srpm method may be called multiple times during koji
        # releases to create the proper disttags, but we only want to modify
        # the spec file once.
        self.ran_setup_test_specfile = False

        # NOTE: These are defined later when/if we actually dump a copy of the
        # project source at the tag we're building. Only then can we search for
        # a spec file.
        self.spec_file_name = None
        self.spec_file = None

        # Set to path to srpm once we build one.
        self.srpm_location = None

    def _create_build_dirs(self):
        """
        Create the build directories. Can safely be called multiple times.
        """
        BuilderBase._create_build_dirs(self)
        build_dirs = [
            self.rpmbuild_gitcopy,
        ]
        for d in build_dirs:
            mkdir_p(d)
        self._check_build_dirs_access(build_dirs)

    def _get_build_version(self):
        """
        Figure out the git tag and version-release we're building.
        """
        # Determine which package version we should build:
        build_version = None
        if self.build_tag:
            build_version = self.build_tag[len(self.project_name + "-"):]
        else:
            build_version = get_latest_tagged_version(self.project_name)
            if build_version is None:
                if not self.test:
                    error_out(["Unable to lookup latest package info.",
                            "Perhaps you need to tag first?"])
                warn_out("unable to lookup latest package "
                    "tag, building untagged test project")
                build_version = get_spec_version_and_release(self.start_dir,
                    find_spec_like_file(self.start_dir))
            self.build_tag = self._get_tag_for_version(build_version)

        self.spec_version = build_version.split('-')[0]
        self.spec_release = build_version.split('-')[-1]
        if not self.test:
            check_tag_exists(self.build_tag, offline=self.offline)
        return build_version

    def _get_tag_for_version(self, version_and_release):
        """
        Determine what the tag will look like for a given version.
        Can be overridden when custom taggers override counterpart,
        tito.Builder._get_tag_for_version().
        """
        version = version_and_release.split('-')[0]
        release = version_and_release.split('-')[-1]
        if self.config.has_option(BUILDCONFIG_SECTION, "tag_format"):
            tag_format = self.config.get(BUILDCONFIG_SECTION, "tag_format")
        else:
            tag_format = "{component}-{version}-{release}"
        kwargs = {
            'component': self.project_name,
            'version': version,
            'release': release
        }
        # Strip extra dashes if one of the params is empty
        return tag_format.format(**kwargs).strip('-')

    def copy_and_download_extra_sources(self):
        """
        Copy extra %{SOURCEX} files to the SOURCE folder, and when
        self.fetch_sources is configured download external sources as well.
        """
        return self._copy_extra_sources(download_sources=True)

    def copy_extra_sources(self):
        """
        Copy extra %{SOURCEX} files to the SOURCE folder.
        """
        return self._copy_extra_sources()

    def _download_one_source(self, source):
        target = os.path.join(
            self.rpmbuild_sourcedir,
            os.path.basename(source),
        )
        info_out("Downloading %s into %s" % (source, target))
        urlretrieve(source, target)
        self.sources.append(target)

    def _copy_extra_sources(self, download_sources=False):
        cmd = "spectool -S '%s' --define '_sourcedir %s' 2> /dev/null | awk '{print $2}'"\
            % (self.spec_file, self.start_dir)
        sources = getoutput(cmd).split("\n")

        for source in sources[1:]:
            dst_file = os.path.join(self.rpmbuild_sourcedir, source)
            if os.path.isfile(dst_file):
                debug('Source file "%s" already exists. Skiping.' % dst_file)
                continue

            parse = urlparse(source)
            if parse.scheme and parse.netloc:
                # For self.srpm() and self.rpm() we call
                # self.download_sources() and later rpmbuild.  We know we can
                # rely on defined macro `%_disable_source_fetch 0`, and the
                # file will be automatically downloaded by rpmbuild to the
                # SOURCES directory. We can safely skip the download here.
                # For other use-cases (e.g. releasing to Fedora DistGit) we
                # don't run rpmbuild at all, and we need to download the file
                # right now (and add it to self.sources).
                if self.fetch_sources and download_sources:
                    self._download_one_source(source)
                    continue
                debug('Source "%s" is not a local file. Skiping.' % source)
                continue

            if not os.path.exists(source):
                debug('Source "%s" file does not exist. Skiping.' % source)
                continue

            src = os.path.join(self.rpmbuild_sourcedir, self.tgz_dir, source)
            if os.path.islink(src) and os.path.isabs(src):
                src = os.path.join(self.start_dir, os.readlink(src))

            debug("Copying %s -> %s" % (src, self.rpmbuild_sourcedir))
            shutil.copy(src, self.rpmbuild_sourcedir)

    def tgz(self):
        """
        Create the .tar.gz required to build this package.

        Returns full path to the created tarball.
        """
        self._setup_sources()

        run_command("cp %s/%s %s/" %
                (self.rpmbuild_sourcedir, self.tgz_filename,
                    self.rpmbuild_basedir))

        self.ran_tgz = True
        full_path = os.path.join(self.rpmbuild_basedir, self.tgz_filename)
        info_out("Wrote: %s" % full_path)
        self.sources.append(full_path)
        self.artifacts.append(full_path)
        return full_path

    def rpm(self):
        """ Build an RPM. """
        self._create_build_dirs()
        if not self.ran_tgz:
            self.tgz()
        if self.test:
            self._setup_test_specfile()
        BuilderBase.rpm(self)

    def _setup_sources(self):
        """
        Create a copy of the git source for the project at the point in time
        our build tag was created.

        Created in the temporary rpmbuild SOURCES directory.
        """
        self._create_build_dirs()

        debug("Creating %s from git tag: %s..." % (self.tgz_filename,
            self.git_commit_id))
        create_tgz(self.git_root, self.tgz_dir, self.git_commit_id,
                self.relative_project_dir,
                os.path.join(self.rpmbuild_sourcedir, self.tgz_filename))

        # Extract the source so we can get at the spec file, etc.
        debug("Copying git source to: %s" % self.rpmbuild_gitcopy)
        run_command("cd %s/ && tar xzf %s" % (self.rpmbuild_sourcedir,
            self.tgz_filename))

        debug("Show contents of the directory structure we just extracted:\n%s"
              % os.listdir(self.rpmbuild_gitcopy))

        # NOTE: The spec file we actually use is the one exported by git
        # archive into the temp build directory. This is done so we can
        # modify the version/release on the fly when building test rpms
        # that use a git SHA1 for their version.
        self.spec_file_name = os.path.basename(find_spec_like_file(self.rpmbuild_gitcopy))
        self.spec_file = os.path.join(
            self.rpmbuild_gitcopy, self.spec_file_name)

    def _setup_test_specfile(self):
        if self.test and not self.ran_setup_test_specfile:
            # If making a test rpm we need to get a little crazy with the spec
            # file we're building off. (note that this is a temp copy of the
            # spec) Swap out the actual release for one that includes the git
            # SHA1 we're building for our test package:
            sha = self.git_commit_id[:7]
            fullname = "%s-%s" % (self.project_name, self.display_version)
            munge_specfile(
                self.spec_file,
                sha,
                self.commit_count,
                fullname,
                self.tgz_filename,
            )

            self.build_version += ".git." + str(self.commit_count) + "." + str(sha)
            self.ran_setup_test_specfile = True

    def _get_rpmbuild_dir_options(self):
        return ('--define "_topdir %s" --define "_sourcedir %s" --define "_builddir %s" --define '
            '"_srcrpmdir %s" --define "_rpmdir %s" ' % (
                self.rpmbuild_dir,
                self.rpmbuild_sourcedir, self.rpmbuild_builddir,
                self.rpmbuild_basedir, self.rpmbuild_basedir))

    def _get_tgz_name_and_ver(self):
        """
        Returns the project name for the .tar.gz to build. Normally this is
        just the project name, but in the case of Satellite packages it may
        be different.
        """
        return "%s-%s" % (self.project_name, self.display_version)

    def _get_display_version(self):
        """
        Get the package display version to build.

        Normally this is whatever is .tito/packages/. In the case of a --test
        build it will be the SHA1 for the HEAD commit of the current git
        branch.
        """
        if self.test:
            # should get latest commit for given directory *NOT* HEAD
            latest_commit = get_latest_commit(".")
            self.commit_count = get_commit_count(self.build_tag, latest_commit)
            version = "git-%s.%s" % (self.commit_count, latest_commit[:7])
        else:
            version = self.build_version.split("-")[0]
        return version


class NoTgzBuilder(Builder):
    """
    Builder for packages that do not require the creation of a tarball.
    Usually these packages have source tarballs checked directly into git.
    """

    def tgz(self):
        """ Override parent behavior, we already have a tgz. """
        # TODO: Does it make sense to allow user to create a tgz for this type
        # of project?
        self._setup_sources()
        self.ran_tgz = True

        debug("Scanning for sources.")
        cmd = "/usr/bin/spectool --list-files '%s' | awk '{print $2}' |xargs -l1 --no-run-if-empty basename " % self.spec_file
        result = run_command(cmd)
        self.sources = []
        for source in result.split("\n"):
            self.sources.append(os.path.join(self.rpmbuild_gitcopy, source))
        debug("  Sources: %s" % self.sources)

    def _get_rpmbuild_dir_options(self):
        """
        Override parent behavior slightly.

        These packages store tar's, patches, etc, directly in their project
        dir, use the git copy we create as the sources directory when
        building package so everything can be found:
        """
        return ('--define "_topdir %s" --define "_sourcedir %s" --define "_builddir %s" '
            '--define "_srcrpmdir %s" --define "_rpmdir %s" ' % (
                self.rpmbuild_dir,
                self.rpmbuild_gitcopy, self.rpmbuild_builddir,
                self.rpmbuild_basedir, self.rpmbuild_basedir))

    def _setup_test_specfile(self):
        """ Override parent behavior. """
        if self.test:
            # If making a test rpm we need to get a little crazy with the spec
            # file we're building off. (note that this is a temp copy of the
            # spec) Swap out the actual release for one that includes the git
            # SHA1 we're building for our test package:
            debug("setup_test_specfile:commit_count = %s" % str(self.commit_count))
            munge_specfile(
                self.spec_file,
                self.git_commit_id[:7],
                self.commit_count
            )


class GemBuilder(NoTgzBuilder):
    """
    Gem Builder

    Builder for packages whose sources are managed as gem source structures
    and the upstream project does not want to store gem files in git.
    """

    def _setup_sources(self):
        """
        Create a copy of the git source for the project at the point in time
        our build tag was created.

        Created in the temporary rpmbuild SOURCES directory.
        """
        self._create_build_dirs()

        debug("Creating %s from git tag: %s..." % (self.tgz_filename,
            self.git_commit_id))
        create_tgz(self.git_root, self.tgz_dir, self.git_commit_id,
                self.relative_project_dir,
                os.path.join(self.rpmbuild_sourcedir, self.tgz_filename))

        # Extract the source so we can get at the spec file, etc.
        debug("Copying git source to: %s" % self.rpmbuild_gitcopy)
        run_command("cd %s/ && tar xzf %s" % (self.rpmbuild_sourcedir,
            self.tgz_filename))

        # Find the gemspec
        gemspec_filename = find_gemspec_file(self.rpmbuild_gitcopy)

        debug("Building gem: %s in %s" % (gemspec_filename,
            self.rpmbuild_gitcopy))
        # FIXME - this is ugly and should probably be handled better
        cmd = "gem_name=$(cd %s/ && gem build %s | awk '/File/ {print $2}'); \
            cp %s/$gem_name %s/" % (self.rpmbuild_gitcopy, gemspec_filename,
            self.rpmbuild_gitcopy, self.rpmbuild_sourcedir)

        run_command(cmd)

        # NOTE: The spec file we actually use is the one exported by git
        # archive into the temp build directory. This is done so we can
        # modify the version/release on the fly when building test rpms
        # that use a git SHA1 for their version.
        self.spec_file_name = find_spec_file(self.rpmbuild_gitcopy)
        self.spec_file = os.path.join(
            self.rpmbuild_gitcopy, self.spec_file_name)


class UpstreamBuilder(NoTgzBuilder):
    """
    Builder for packages that are based off an upstream git tag.
    Commits applied in downstream git become patches applied to the
    upstream tarball.

    i.e. satellite-java-0.4.0-5 built from spacewalk-java-0.4.0-1 and any
    patches applied in satellite git.
    i.e. spacewalk-setup-0.4.0-20 built from spacewalk-setup-0.4.0-1 and any
    patches applied in satellite git.
    """

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        NoTgzBuilder.__init__(self, name=name, tag=tag,
                build_dir=build_dir, config=config,
                user_config=user_config,
                args=args, **kwargs)

        if not config or not config.has_option("buildconfig",
                "upstream_name"):
            # No upstream_name defined, assume we're keeping the project name:
            self.upstream_name = self.project_name
        else:
            self.upstream_name = config.get("buildconfig", "upstream_name")
        # Need to assign these after we've exported a copy of the spec file:
        self.upstream_version = None
        self.upstream_tag = None

    def tgz(self):
        """
        Override parent behavior, we need a tgz from the upstream spacewalk
        project we're based on.
        """
        # TODO: Wasteful step here, all we really need is a way to look for a
        # spec file at the point in time this release was tagged.
        NoTgzBuilder._setup_sources(self)
        # If we knew what it was named at that point in time we could just do:
        # Export a copy of our spec file at the revision to be built:
#        cmd = "git show %s:%s%s > %s" % (self.git_commit_id,
#                self.relative_project_dir, self.spec_file_name,
#                self.spec_file)
#        debug(cmd)
        self._create_build_dirs()

        self.upstream_version = self._get_upstream_version()
        self.upstream_tag = "%s-%s-1" % (self.upstream_name,
                self.upstream_version)

        print("Building upstream tgz for tag [%s]" % (self.upstream_tag))
        if self.upstream_tag != self.build_tag:
            check_tag_exists(self.upstream_tag, offline=self.offline)

        self.spec_file = os.path.join(self.rpmbuild_sourcedir,
                self.spec_file_name)
        command = "cp %s %s" % (os.path.join(self.rpmbuild_gitcopy,
            self.spec_file_name), self.spec_file)
        run_command(command)

        # Create the upstream tgz:
        prefix = "%s-%s" % (self.upstream_name, self.upstream_version)
        tgz_filename = "%s.tar.gz" % prefix
        commit = get_build_commit(tag=self.upstream_tag)
        relative_dir = get_relative_project_dir(
            project_name=self.upstream_name, commit=commit)
        tgz_fullpath = os.path.join(self.rpmbuild_sourcedir, tgz_filename)
        print("Creating %s from git tag: %s..." % (tgz_filename, commit))
        create_tgz(self.git_root, prefix, commit, relative_dir,
                tgz_fullpath)
        self.ran_tgz = True
        self.sources.append(tgz_fullpath)

        # If these are equal then the tag we're building was likely created in
        # Spacewalk and thus we don't need to do any patching.
        if (self.upstream_tag == self.build_tag and not self.test):
            return

        self.patch_upstream()

    def _patch_upstream(self):
        """ Insert patches into the spec file we'll be building
            returns (patch_number, patch_insert_index, patch_apply_index, lines)
        """
        f = open(self.spec_file, 'r')
        lines = f.readlines()
        f.close()

        patch_pattern = re.compile('^Patch(\d+):')
        source_pattern = re.compile('^Source(\d+)?:')

        # Find the largest PatchX: line, or failing that SourceX:
        patch_number = 0  # What number should we use for our PatchX line
        patch_insert_index = 0  # Where to insert our PatchX line in the list
        patch_apply_index = 0  # Where to insert our %patchX line in the list
        array_index = 0  # Current index in the array
        for line in lines:
            match = source_pattern.match(line)
            if match:
                patch_insert_index = array_index + 1

            match = patch_pattern.match(line)
            if match:
                patch_insert_index = array_index + 1
                patch_number = int(match.group(1)) + 1

            if line.startswith("%prep"):
                # We'll apply patch right after prep if there's no %setup line
                patch_apply_index = array_index + 2
            elif line.startswith("%setup"):
                patch_apply_index = array_index + 2  # already added a line
            elif line.startswith("%autosetup"):
                patch_apply_index = -1  # autosetup will do this for us

            array_index += 1

        debug("patch_insert_index = %s" % patch_insert_index)
        debug("patch_apply_index = %s" % patch_apply_index)
        if patch_insert_index == 0 or patch_apply_index == 0:
            error_out("Unable to insert PatchX or %patchX lines in spec file")
        return (patch_number, patch_insert_index, patch_apply_index, lines)

    def patch_upstream(self):
        """
        Generate patches for any differences between our tag and the
        upstream tag, and apply them into an exported copy of the
        spec file.
        """
        patch_filename = "%s-to-%s-%s.patch" % (self.upstream_tag,
                self.project_name, self.build_version)
        patch_file = os.path.join(self.rpmbuild_gitcopy,
                patch_filename)
        patch_dir = self.git_root
        if self.relative_project_dir != "/":
            patch_dir = os.path.join(self.git_root,
                    self.relative_project_dir)
        os.chdir(patch_dir)
        debug("patch dir = %s" % patch_dir)
        print("Generating patch [%s]" % patch_filename)
        debug("Patch: %s" % patch_file)
        patch_command = "git diff --relative %s..%s > %s" % \
                (self.upstream_tag, self.git_commit_id,
                        patch_file)
        debug("Generating patch with: %s" % patch_command)
        output = run_command(patch_command)
        print(output)
        (status, output) = getstatusoutput(
            "grep 'Binary files .* differ' %s " % patch_file)
        if status == 0 and output != "":
            print(output)
            error_out("You are doomed. Diff contains binary files. You can not use this builder")

        # Creating two copies of the patch here in the temp build directories
        # just out of laziness. Some builders need sources in SOURCES and
        # others need them in the git copy. Being lazy here avoids one-off
        # hacks and both copies get cleaned up anyhow.
        run_command("cp %s %s" % (patch_file, self.rpmbuild_sourcedir))

        (patch_number, patch_insert_index, patch_apply_index, lines) = self._patch_upstream()

        lines.insert(patch_insert_index, "Patch%s: %s\n" % (patch_number,
            patch_filename))
        if patch_apply_index > 0:
            lines.insert(patch_apply_index, "%%patch%s -p1\n" % (patch_number))
        self._write_spec(lines)

    def _write_spec(self, lines):
        """ Write 'lines' to self.spec_file """
        # Now write out the modified lines to the spec file copy:
        f = open(self.spec_file, 'w')
        for line in lines:
            f.write(line)
        f.close()

    def _get_upstream_version(self):
        """
        Get the upstream version. Checks for "upstreamversion" in the spec file
        and uses it if found. Otherwise assumes the upstream version is equal
        to the version we're building.

        i.e. satellite-java-0.4.15 will be built on spacewalk-java-0.4.15
        with just the package release being incremented on rebuilds.
        """
        # Use upstreamversion if defined in the spec file:
        (status, output) = getstatusoutput(
            "cat %s | grep 'define upstreamversion' | "
            "awk '{ print $3 ; exit }'" % self.spec_file)
        if status == 0 and output != "":
            return output

        if self.test:
            return self.build_version.split("-")[0]
        # Otherwise, assume we use our version:
        else:
            return self.display_version

    def _get_rpmbuild_dir_options(self):
        """
        Override parent behavior slightly.

        These packages store tar's, patches, etc, directly in their project
        dir, use the git copy we create as the sources directory when
        building package so everything can be found:
        """
        return ('--define "_topdir %s" --define "_sourcedir %s" --define "_builddir %s" '
            '--define "_srcrpmdir %s" --define "_rpmdir %s" ' % (
                self.rpmbuild_dir,
                self.rpmbuild_sourcedir, self.rpmbuild_builddir,
                self.rpmbuild_basedir, self.rpmbuild_basedir))


# Legacy class name for backward compatability:
class SatelliteBuilder(UpstreamBuilder):
    pass


class MeadBuilder(Builder):
    def __init__(self, name=None, tag=None, build_dir=None,
        config=None, user_config=None, args=None, **kwargs):

        Builder.__init__(self, name=name, tag=tag, build_dir=build_dir,
            config=config, user_config=user_config, args=args, **kwargs)

        self.ran_maven = False
        self.deploy_dir = mkdtemp(dir=self.rpmbuild_basedir, prefix="maven-deploy-%s" % self.project_name)
        self.maven_clone_dir = mkdtemp(dir=self.rpmbuild_basedir, prefix="maven-clone-%s" % self.project_name)

        # People calling `tito build` will almost certainly want to do a maven build locally.
        # But with a `tito release` we want the Mead stuff to happen on the build system
        self.local_build = args.setdefault('local', [True])

        self.maven_properties = []
        if 'maven_property' in args:
            self.maven_properties = args['maven_property']
        else:
            # Generally people aren't going to want to run their tests during
            # a build.  If they do, they can set maven_properties=''
            self.maven_properties.append("maven.test.skip=true")

        self.maven_args = ['-B']
        if 'maven_arg' in args:
            self.maven_args.extend(args['maven_arg'])

    def _find_tarball(self):
        for directory, unused, filenames in os.walk(self.deploy_dir):
            for f in filenames:
                name, ext = os.path.splitext(f)
                if ext == ".gz" and name.startswith("%s-%s" % (self.project_name, self.spec_version)):
                    return os.path.join(self.deploy_dir, directory, f)
        return None

    def cleanup(self):
        """
        Remove all temporary files and directories.
        """
        if not self.no_cleanup:
            for d in [self.rpmbuild_dir, self.deploy_dir, self.maven_clone_dir]:
                debug("Cleaning up %s" % d)
                shutil.rmtree(d)
        else:
            warn_out("Leaving rpmbuild files in: %s" % self.rpmbuild_dir)

    def tgz(self):
        destination_file = os.path.join(self.rpmbuild_basedir, self.tgz_filename)
        formatted_properties = ["-D%s" % x for x in self.maven_properties]

        run_command("git clone --no-hardlinks %s %s" % (find_git_root(), self.maven_clone_dir))
        with chdir(self.maven_clone_dir):
            run_command("git checkout %s" % self.git_commit_id)

            try:
                info_out("Running Maven build...")
                # We always want to deploy to a tito controlled location during local builds
                local_properties = formatted_properties + [
                    "-DaltDeploymentRepository=local-output::default::file://%s" % self.deploy_dir]
                run_command("mvn %s %s deploy" % (
                    " ".join(self.maven_args),
                    " ".join(local_properties)))
            except RunCommandException as e:
                error_out("Maven build failed! %s" % e.output)

        self._create_build_dirs()

        full_path = self._find_tarball()
        if full_path:
            fh = gzip.open(full_path, 'rb')
            fixed_tar = os.path.join(os.path.splitext(full_path)[0])
            fixed_tar_fh = open(fixed_tar, 'wb')
            timestamp = get_commit_timestamp(self.git_commit_id)
            try:
                tarfixer = TarFixer(fh, fixed_tar_fh, timestamp, self.git_commit_id, maven_built=True)
                tarfixer.fix()
            finally:
                fixed_tar_fh.close()

            # It's a pity we can't use Python's gzip, but it doesn't offer an equivalent of -n
            run_command("gzip -n -c < %s > %s" % (fixed_tar, destination_file))
        else:
            warn_out([
                "No Maven generated tarball found.",
                "Please set up the assembly plugin in your pom.xml to generate a .tar.gz"])
            full_path = os.path.join(self.rpmbuild_sourcedir, self.tgz_filename)
            create_tgz(self.git_root, self.tgz_dir, self.git_commit_id, self.relative_project_dir, full_path)
            print("Creating %s from git tag: %s..." % (self.tgz_filename, self.build_tag))
            shutil.copy(full_path, destination_file)

        debug("Copying git source to: %s" % self.rpmbuild_gitcopy)
        shutil.copy(destination_file, self.rpmbuild_gitcopy)

        # Extract the source so we can get at the spec file, etc.
        with chdir(self.rpmbuild_gitcopy):
            run_command("tar --strip-components=1 -xvf %s" % os.path.join(self.rpmbuild_gitcopy, self.tgz_filename))

        if self.local_build:
            artifacts = {}
            all_artifacts = []
            all_artifacts_with_path = []

            for directory, unused, filenames in os.walk(self.deploy_dir):
                for f in filenames:
                    artifacts.setdefault(os.path.splitext(f)[1], []).append(f)
                dir_artifacts_with_path = [os.path.join(directory, f) for f in filenames]

                # Place the Maven artifacts in the SOURCES directory for rpmbuild to use
                for artifact in dir_artifacts_with_path:
                    shutil.copy(artifact, self.rpmbuild_sourcedir)

                dir_artifacts_with_path = map(lambda x: os.path.relpath(x, self.deploy_dir), dir_artifacts_with_path)
                all_artifacts_with_path.extend(dir_artifacts_with_path)
                all_artifacts.extend([os.path.basename(f) for f in filenames])

            cheetah_input = {
                'name': self.project_name,
                'version': self.spec_version,
                'release': self.spec_release,
                'epoch': None,  # TODO: May need to support this at some point
                'artifacts': artifacts,
                'all_artifacts': all_artifacts,
                'all_artifacts_with_path': all_artifacts_with_path,
            }
            debug("Cheetah input: %s" % cheetah_input)
            render_cheetah(find_cheetah_template_file(self.start_dir), self.rpmbuild_gitcopy, cheetah_input)
            self.spec_file_name = find_spec_file(self.rpmbuild_gitcopy)
        else:
            self.spec_file_name = find_cheetah_template_file(self.rpmbuild_gitcopy)

        # NOTE: The spec file we actually use is the one exported by git
        # archive into the temp build directory. This is done so we can
        # modify the version/release on the fly when building test rpms
        # that use a git SHA1 for their version.
        self.spec_file = os.path.join(self.rpmbuild_gitcopy, self.spec_file_name)

        info_out("Wrote: %s" % destination_file)
        self.sources.append(destination_file)
        self.artifacts.append(destination_file)
        self.ran_tgz = True

    def _setup_test_specfile(self):
        if self.test and not self.ran_setup_test_specfile:
            # If making a test rpm we need to get a little crazy with the spec
            # file we're building off. (note that this is a temp copy of the
            # spec) Swap out the actual release for one that includes the git
            # SHA1 we're building for our test package:
            self.build_version += ".git." + str(self.commit_count) + "." + str(self.git_commit_id[:7])
            replace_spec_release(self.spec_file, self.spec_release)
            self.ran_setup_test_specfile = True


class MockBuilder(Builder):
    """
    Uses the mock tool to create a chroot for building packages for a different
    OS version than you may be currently using.
    """
    REQUIRED_ARGS = ['mock']

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        # Mock builders need to use the packages normally configured builder
        # to get at a proper SRPM:
        self.normal_builder = create_builder(
            name, tag, config, build_dir, user_config, args,
            builder_class="tito.builder.Builder",
            **kwargs)

        # TODO This is certainly not optimal. There are many more mock-related
        # arguments that should be covered but I don't want to do that right
        # now. It is really bad idea to let each *Builder to read the [builder]
        # section of the tito.props config and decide how to handle its options.
        # Besides here, we do it also in FetchBuilder and maybe somewhere else.
        # We need to unify that, and do it for all (recognized) options, not
        # only the hardcoded ones.
        if ("mock" not in args
            and "builder" in config
            and "mock" in config["builder"]
            ):
            args["mock"] = [config.get("builder", "mock")]

        Builder.__init__(self, name=name, tag=tag,
                build_dir=build_dir, config=config,
                user_config=user_config,
                args=args, **kwargs)

        self.mock_tag = args['mock'][0]
        self.mock_cmd_args = ""
        if 'mock_config_dir' in args:
            mock_config_dir = args['mock_config_dir'][0]
            if not mock_config_dir.startswith("/"):
                # If not an absolute path, assume below git root:
                mock_config_dir = os.path.join(self.git_root, mock_config_dir)
            if not os.path.exists(mock_config_dir):
                raise TitoException("No such mock config dir: %s" % mock_config_dir)
            self.mock_cmd_args = "%s --configdir=%s" % (self.mock_cmd_args, mock_config_dir)

        # Optional argument which will skip mock --init and add --no-clean
        # and --no-cleanup-after:
        self.speedup = False
        if 'speedup' in args:
            self.speedup = True
            self.mock_cmd_args = "%s --no-clean --no-cleanup-after" % \
                    (self.mock_cmd_args)

        if 'mock_args' in args:
            self.mock_cmd_args = "%s %s" % (self.mock_cmd_args, args['mock_args'][0])

        # TODO: error out if mock package is not installed

        # TODO: error out if user does not have mock group

    def srpm(self, dist=None):
        """
        Build a source RPM.

        MockBuilder will use an instance of the normal builder for a package
        internally just so we can generate a SRPM correctly before we pass it
        into mock.
        """
        self.normal_builder.srpm(dist)
        self.srpm_location = self.normal_builder.srpm_location
        self.artifacts.append(self.srpm_location)

    def rpm(self):
        """
        Uses the SRPM
        Override the base builder rpm method.
        """

        print("Creating rpms for %s-%s in mock: %s" % (
            self.project_name, self.display_version, self.mock_tag))
        if not self.srpm_location:
            self.srpm()
        print("Using srpm: %s" % self.srpm_location)
        self._build_in_mock()

    def cleanup(self):
        if self.normal_builder:
            self.normal_builder.cleanup()

    def _build_in_mock(self):
        run_command_func = run_command if self.quiet else run_command_print
        if not self.speedup:
            print("Initializing mock...")
            run_command_func("mock %s -r %s --init" % (self.mock_cmd_args, self.mock_tag))
        else:
            print("Skipping mock --init due to speedup option.")

        print("Building RPMs in mock...")
        run_command_func('mock %s -r %s --rebuild %s' %
                (self.mock_cmd_args, self.mock_tag, self.srpm_location))
        mock_output_dir = os.path.join(self.rpmbuild_dir, "mockoutput")
        run_command_func("mock %s -r %s --copyout /builddir/build/RPMS/ %s" %
                (self.mock_cmd_args, self.mock_tag, mock_output_dir))

        # Copy everything mock wrote out to /tmp/tito:
        files = os.listdir(mock_output_dir)
        for rpm in files:
            shutil.copy2(os.path.join(mock_output_dir, rpm), self.rpmbuild_basedir)
        print
        info_out("Wrote:")
        for rpm in files:
            rpm_path = os.path.join(self.rpmbuild_basedir, rpm)
            print("  %s" % rpm_path)
            self.artifacts.append(rpm_path)
        print


class BrewDownloadBuilder(Builder):
    """
    A special case builder which uses pre-existing Brew builds and
    pulls down the resulting rpms locally. Useful in some cases when
    generating yum repositories during a release.
    """
    REQUIRED_ARGS = ['disttag']

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        Builder.__init__(self, name=name, tag=tag,
                build_dir=build_dir, config=config,
                user_config=user_config,
                args=args, **kwargs)

        self.dist_tag = args['disttag'][0]

    def rpm(self):
        """
        Uses the SRPM
        Override the base builder rpm method.
        """

        print("Fetching rpms for %s.%s from brew:" % (
            self.build_tag, self.dist_tag))
        self._fetch_from_brew()

    def _fetch_from_brew(self):
        brew_nvr = "%s.%s" % (self.build_tag, self.dist_tag)
        debug("Brew NVR: %s" % brew_nvr)
        os.chdir(self.rpmbuild_dir)
        run_command("brew download-build %s" % brew_nvr)

        # Wipe out the src rpm for now:
        run_command("rm *.src.rpm")

        # Copy everything brew downloaded out to /tmp/tito:
        files = os.listdir(self.rpmbuild_dir)
        run_command("cp -v %s/*.rpm %s" %
                (self.rpmbuild_dir, self.rpmbuild_basedir))
        print
        info_out("Wrote:")
        for rpm in files:
            # Just incase anything slips into the build dir:
            if not rpm.endswith(".rpm"):
                continue
            rpm_path = os.path.join(self.rpmbuild_basedir, rpm)
            print("  %s" % rpm_path)
            self.artifacts.append(rpm_path)
        print


class GitAnnexBuilder(NoTgzBuilder):
    """
    Builder for packages with existing tarballs checked in using git-annex,
    e.g. referencing an external source (web remote).  This builder will
    "unlock" the source files to get the real contents, include them in the
    SRPM, then restore the automatic git-annex symlinks on completion.
    """

    def _setup_sources(self):
        super(GitAnnexBuilder, self)._setup_sources()

        self.old_cwd = os.getcwd()
        os.chdir(os.path.join(self.old_cwd, self.relative_project_dir))

        # NOTE: 'which' may not be installed... (docker containers)
        (status, output) = getstatusoutput("which git-annex")
        if status != 0:
            msg = "Please run '%s' as root." % self.package_manager.install(["git-annex"])
            error_out('%s' % msg)

        run_command("git-annex lock")
        annexed_files = run_command("git-annex find --include='*'").splitlines()
        run_command("git-annex get")
        run_command("git-annex unlock")
        debug("  Annex files: %s" % annexed_files)

        for annex in annexed_files:
            debug("Copying unlocked file %s" % annex)
            os.remove(os.path.join(self.rpmbuild_gitcopy, annex))
            shutil.copy(annex, self.rpmbuild_gitcopy)

        self._lock()
        os.chdir(self.old_cwd)

    def cleanup(self):
        if hasattr(self, 'old_cwd'):
            os.chdir(self.old_cwd)
        self._lock()
        super(GitAnnexBuilder, self).cleanup()

    def _lock(self):
        if self._lock_force_supported(self._get_annex_version()):
            run_command("git-annex lock --force")
        else:
            run_command("git-annex lock")

    def _get_annex_version(self):
        # git-annex needs to support --force when locking files.
        ga_version = run_command('git-annex version').split('\n')
        if ga_version[0].startswith('git-annex version'):
            return ga_version[0].split()[-1]
        else:
            return 0

    def _lock_force_supported(self, version):
        return compare_version(version, '5.20131213') >= 0


class GitLfsBuilder(NoTgzBuilder):
    """
    Builder class for Git LFS support.
    """

    def _setup_sources(self):
        super(GitLfsBuilder, self)._setup_sources()

        self.old_cwd = os.getcwd()
        os.chdir(os.path.join(self.old_cwd, self.relative_project_dir))
        debug("learning %s" % self.relative_project_dir)
        (status, output) = getstatusoutput("which git-lfs")
        if status != 0:
            msg = "Please run '%s' as root." % self.package_manager.install(["git-lfs"])
            error_out('%s' % msg)

        gitlfs_files = run_command("git-lfs ls-files").splitlines()
        run_command("git-lfs fetch")
        debug("  Lfs files: %s" % gitlfs_files)
        for gfile in gitlfs_files:
            m = re.search('(?<=' + self.relative_project_dir + ')(.*)', gfile)
            if m:
                filterfile = m.groups(0)
                mstr = filterfile[0]
                debug("Copying file %s " % mstr)
                debug("To %s " % self.rpmbuild_gitcopy)
                os.remove(os.path.join(self.rpmbuild_gitcopy, mstr))
                shutil.copy(mstr, self.rpmbuild_gitcopy)

        os.chdir(self.old_cwd)

    def cleanup(self):
        if hasattr(self, 'old_cwd'):
            os.chdir(self.old_cwd)
        super(GitLfsBuilder, self).cleanup()


def package_manager():
    if os.path.isfile("/usr/bin/dnf"):
        return Dnf()
    if os.path.isfile("/usr/bin/yum"):
        return Yum()
    return Rpm()


class Rpm(object):
    def install(self, packages, escalate=True, **kwargs):
        escalation_cmd = "sudo" if escalate else ""
        return "%s rpm -U --force %s" % (escalation_cmd, ' '.join(packages))

    def builddep(self, spec):
        raise NotImplementedError

    def is_installed(self, package, version):
        q = self.query(package)
        if not q:
            return False

        if isinstance(q.version, bytes):
            iv = "%s-%s" % (q.version.decode("utf-8"), q.release.decode("utf-8"))
        else:
            iv = "%s-%s" % (q.version, q.release)
        iv_short = ".".join(iv.split(".")[:-1])
        return version == iv_short

    def query(self, package):
        ts = rpm.TransactionSet()
        results = list(ts.dbMatch("name", package))
        return results[0] if results else None


class Dnf(Rpm):
    def install(self, packages, reinstall=False, auto=False, offline=False, escalate=True, **kwargs):
        action = "reinstall" if reinstall else "install"
        args = list(filter(lambda x: x, [
            "-C" if offline else None,
            "-y" if auto else None,
        ]))
        escalation_cmd = "sudo" if escalate else ""
        cmd = "%s dnf %s %s" % (escalation_cmd, action, " ".join(args + packages))
        return " ".join(cmd.split())

    def builddep(self, spec):
        return "dnf builddep %s" % spec


class Yum(Rpm):
    def install(self, packages, **kwargs):
        # Not the sexiest implementation, but very short
        return Dnf().install(packages, **kwargs).replace("dnf", "yum")

    def builddep(self, spec):
        return "yum-builddep %s" % spec
