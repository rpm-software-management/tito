# Copyright (c) 2008-2009 Red Hat, Inc.
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
Tito's Command Line Interface
"""

import sys
import os
import errno

from optparse import OptionParser, SUPPRESS_HELP

from tito import __version__
from tito.common import find_git_root, error_out, debug, get_class_by_name, \
    DEFAULT_BUILDER, BUILDCONFIG_SECTION, DEFAULT_TAGGER, \
    create_builder, get_project_name, get_relative_project_dir, \
    DEFAULT_BUILD_DIR, run_command, tito_config_dir, warn_out, info_out, \
    read_user_config
from tito.compat import RawConfigParser, getstatusoutput, getoutput
from tito.exception import TitoException

# Hack for Python 2.4, seems to require we import these so they get compiled
# before we try to dynamically import them based on a string name.
import tito.tagger  # NOQA

PROGNAME = "tito"
TITO_PROPS = "tito.props"
RELEASERS_CONF_FILENAME = "releasers.conf"
ASSUMED_NO_TAR_GZ_PROPS = """
[buildconfig]
builder = tito.builder.NoTgzBuilder
tagger = tito.tagger.ReleaseTagger
"""


class FauxConfigFile(object):
    """ Allows us to read config from a string. """
    def __init__(self, config_str):
        # We'll re-add the newline when returned:
        self.lines = config_str.split("\n")

    def readline(self):
        if len(self.lines) > 0:
            # Pop a line off the front of the list:
            line = self.lines[0]
            self.lines = self.lines[1:]
            return line + "\n"
        else:
            # Indicates end of file:
            return ''


class ConfigLoader(object):
    """
    Responsible for the sometimes complicated process of loading the repo's
    tito.props, and overriding it with package specific tito.props, sometimes
    from a past tag to ensure build consistency.
    """

    def __init__(self, package_name, output_dir, tag):
        self.package_name = package_name
        self.output_dir = output_dir
        self.tag = tag

    def load(self):
        self.config = self._read_config()
        self._read_project_config()
        self._check_required_config(self.config)
        return self.config

    def _read_config(self):
        """
        Read global build.py configuration from the .tito dir of the git
        repository we're being run from.

        NOTE: We always load the latest config file, not tito.props as it
        was for the tag being operated on.
        """
        # List of filepaths to config files we'll be loading:
        rel_eng_dir = os.path.join(find_git_root(), tito_config_dir())
        filename = os.path.join(rel_eng_dir, TITO_PROPS)
        if not os.path.exists(filename):
            error_out("Unable to locate branch configuration: %s"
                "\nPlease run 'tito init'" % filename)

        # Load the global config. Later, when we know what tag/package we're
        # building, we may also load that and potentially override some global
        # settings.
        config = RawConfigParser()
        config.read(filename)

        self._check_legacy_globalconfig(config)
        return config

    def _check_legacy_globalconfig(self, config):
        # globalconfig renamed to buildconfig for better overriding in per-package
        # tito.props. If we see globalconfig, automatically rename it after
        # loading and warn the user.
        if config.has_section('globalconfig'):
            if not config.has_section('buildconfig'):
                config.add_section('buildconfig')
            warn_out("Please rename [globalconfig] to [buildconfig] in "
                "tito.props")
            for k, v in config.items('globalconfig'):
                if k == 'default_builder':
                    warn_out("please rename 'default_builder' to "
                        "'builder' in tito.props")
                    config.set('buildconfig', 'builder', v)
                elif k == 'default_tagger':
                    warn_out("please rename 'default_tagger' to "
                        "'tagger' in tito.props")
                    config.set('buildconfig', 'tagger', v)
                else:
                    config.set('buildconfig', k, v)
            config.remove_section('globalconfig')

    def _check_required_config(self, config):
        # Verify the config contains what we need from it:
        required_global_config = [
            (BUILDCONFIG_SECTION, DEFAULT_BUILDER),
            (BUILDCONFIG_SECTION, DEFAULT_TAGGER),
        ]
        for section, option in required_global_config:
            if not config.has_section(section) or not \
                config.has_option(section, option):
                    error_out("tito.props missing required config: %s %s" % (
                        section, option))

    def _read_project_config(self):
        """
        Read project specific tito config if it exists.

        If no tag is specified we use tito.props from the current HEAD.
        If a tag is specified, we try to load a tito.props from that
        tag.
        """
        debug("Determined package name to be: %s" % self.package_name)

        # Use the properties file in the current project directory, if it
        # exists:
        current_props_file = os.path.join(os.getcwd(), TITO_PROPS)
        if (os.path.exists(current_props_file)):
            self.config.read(current_props_file)
            print("Loaded package specific tito.props overrides")

        # Check for a tito.props back when this tag was created and use it
        # instead. (if it exists)
        if self.tag:
            relative_dir = get_relative_project_dir(self.package_name, self.tag)
            debug("Relative project dir: %s" % relative_dir)

            cmd = "git show %s:%s%s" % (self.tag, relative_dir,
                    TITO_PROPS)
            debug(cmd)
            (status, output) = getstatusoutput(cmd)

            if status == 0:
                faux_config_file = FauxConfigFile(output)
                self.config.read_fp(faux_config_file)
                print("Loaded package specific tito.props overrides from %s" %
                    self.tag)
                return

        debug("Unable to locate package specific config for this package.")


def lookup_build_dir(user_config):
    """
    Read build_dir user config if it exists, otherwise
    return the current working directory.
    """
    build_dir = DEFAULT_BUILD_DIR

    if 'RPMBUILD_BASEDIR' in user_config:
        build_dir = user_config["RPMBUILD_BASEDIR"]

    return build_dir


class CLI(object):
    """
    Parent command line interface class.

    Simply delegated to sub-modules which group appropriate command line
    options together.
    """

    def main(self, argv):
        if "--version" in sys.argv:
            print(" ".join([PROGNAME, __version__]))
            sys.exit(0)

        if len(argv) < 1 or not argv[0] in CLI_MODULES.keys():
            self._usage()
            sys.exit(1)

        module_class = CLI_MODULES[argv[0]]
        module = module_class()
        return module.main(argv)

    def _usage(self):
        print("Usage: tito MODULENAME --help")
        print("Supported modules:")
        print("   build    - Build packages.")
        print("   init     - Initialize directory for use by tito.")
        print("   release  - Build and release to yum repos")
        print("   report   - Display various reports on the repo.")
        print("   tag      - Tag package releases.")


class BaseCliModule(object):
    """ Common code used amongst all CLI modules. """

    def __init__(self, usage):
        self.parser = OptionParser(usage)
        self.config = None
        self.options = None
        self.user_config = read_user_config()

        self._add_common_options()

    def _add_common_options(self):
        """
        Add options to the command line parser which are relevant to all
        modules.
        """
        # Options used for many different activities:
        self.parser.add_option("--debug", dest="debug", action="store_true",
                help="print debug messages", default=False)
        self.parser.add_option("--offline", dest="offline",
            action="store_true",
            help="do not attempt any remote communication (avoid using " +
                "this please)",
            default=False)

        default_output_dir = lookup_build_dir(self.user_config)
        self.parser.add_option("-o", "--output", dest="output_dir",
                metavar="OUTPUTDIR", default=default_output_dir,
                help="Path to write temp files, tarballs and rpms to. "
                    "(default %s)"
                    % default_output_dir)

    def main(self, argv):
        (self.options, self.args) = self.parser.parse_args(argv)

        self._validate_options()

        if len(argv) < 1:
            print(self.parser.error("Must supply an argument. "
                "Try -h for help."))

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        print("Creating output directory: %s" % build_dir)
        try:
            os.makedirs(build_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    def load_config(self, package_name, build_dir, tag):
        self.config = ConfigLoader(package_name, build_dir, tag).load()

        if self.config.has_option(BUILDCONFIG_SECTION,
                "offline"):
            self.options.offline = True

        if self.config.has_option(BUILDCONFIG_SECTION, "fetch_sources"):
            self.options.fetch_sources = self.config.get(BUILDCONFIG_SECTION, "fetch_sources")

        # TODO: Not ideal:
        if self.options.debug:
            os.environ['DEBUG'] = "true"

        # Check if config defines a custom lib dir, if so we add it
        # to the python path allowing users to specify custom builders/taggers
        # in their config:
        if self.config.has_option(BUILDCONFIG_SECTION,
                "lib_dir"):
            lib_dir = self.config.get(BUILDCONFIG_SECTION,
                    "lib_dir")
            if lib_dir[0] != '/':
                # Looks like a relative path, assume from the git root:
                lib_dir = os.path.join(find_git_root(), lib_dir)

            if os.path.exists(lib_dir):
                sys.path.append(lib_dir)
                debug("Added lib dir to PYTHONPATH: %s" % lib_dir)
            else:
                warn_out("lib_dir specified but does not exist: %s" % lib_dir)

    def _validate_options(self):
        """
        Subclasses can implement if they need to check for any
        incompatible cmd line options.
        """
        pass


class BuildModule(BaseCliModule):

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog build [options]")

        self.parser.add_option("--tgz", dest="tgz", action="store_true",
                help="Build .tar.gz")
        self.parser.add_option("--srpm", dest="srpm", action="store_true",
                help="Build srpm")
        self.parser.add_option("--rpm", dest="rpm", action="store_true",
                help="Build rpm")
        self.parser.add_option("-i", "--install", dest="auto_install",
                action="store_true", default=False,
                help="Install any binary rpms being built. (WARNING: " +
                    "uses sudo rpm -Uvh --force)")
        self.parser.add_option("--no-sudo", dest="escalate",
                action="store_false", default=True,
                help="Don't escalate privileges when installing. Use when " +
                "running this command with required privileges.")
        self.parser.add_option("--dist", dest="dist", metavar="DISTTAG",
                help="Dist tag to apply to srpm and/or rpm. (i.e. .el5)")

        self.parser.add_option("--test", dest="test", action="store_true",
                help="use current branch HEAD instead of latest package tag")
        self.parser.add_option("--no-cleanup", dest="no_cleanup",
                action="store_true",
                help="do not clean up temporary tito build directories/files, and disable rpmbuild %clean")
        self.parser.add_option("--tag", dest="tag", metavar="PKGTAG",
                help="build a specific tag instead of the latest version " +
                    "(i.e. spacewalk-java-0.4.0-1)")

        self.parser.add_option("--builder", dest="builder",
                help="Override the normal builder by specifying a full class "
                    "path or one of the pre-configured shortcuts.")

        self.parser.add_option("--arg", dest="builder_args",
                action="append",
                help="Custom arguments specific to a particular builder."
                    " (key=value)")

        self.parser.add_option("--quiet", dest="quiet", action="store_true",
                help="Suppress output from the build process.")
        self.parser.add_option("--verbose", dest="verbose", action="store_true",
                help="Expose more output from the build process.")

        self.parser.add_option("--rpmbuild-options", dest='rpmbuild_options',
                default='',
                metavar="OPTIONS", help="Options to pass to rpmbuild.")
        self.parser.add_option("--scl", dest='scl',
                default='',
                metavar="COLLECTION", help="Build package for software collection.")

        self.parser.add_option("--fetch-sources", dest='fetch_sources',
                               action="store_true",
                               help="Download sources from predefined Source<N> addresses to the SOURCE folder")

    def main(self, argv):
        BaseCliModule.main(self, argv)

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        package_name = get_project_name(tag=self.options.tag)

        build_tag = self.options.tag

        self.load_config(package_name, build_dir, self.options.tag)

        args = self._parse_builder_args()
        kwargs = {
            'dist': self.options.dist,
            'test': self.options.test,
            'offline': self.options.offline,
            'auto_install': self.options.auto_install,
            'rpmbuild_options': self.options.rpmbuild_options,
            'scl': self.options.scl,
            'quiet': self.options.quiet,
            'verbose': self.options.verbose,
            'fetch_sources': self.options.fetch_sources,
        }

        builder = create_builder(package_name, build_tag,
                self.config,
                build_dir, self.user_config, args,
                builder_class=self.options.builder, **kwargs)
        return builder.run(self.options)

    def _validate_options(self):
        if not any([self.options.rpm, self.options.srpm, self.options.tgz]):
            error_out("Need an artifact type to build.  Use --rpm, --srpm, or --tgz")
        if self.options.srpm and self.options.rpm:
            error_out("Cannot combine --srpm and --rpm")
        if self.options.test and self.options.tag:
            error_out("Cannot build test version of specific tag.")
        if self.options.quiet and self.options.verbose:
            error_out("Cannot set --quiet and --verbose at the same time.")

    def _parse_builder_args(self):
        """
        Builder args are sometimes needed for builders that require runtime
        data.

        On the CLI this is specified with multiple uses of:

            --arg key=value

        This method parses any --arg's given and splits the key/value
        pairs out into a *dictionary of lists*.  If you only expect one value
        for the argument, you would use args['my_key'][0].
        """
        args = {}
        if self.options.builder_args is None:
            return args

        for arg in self.options.builder_args:
            if '=' in arg:
                key, value = arg.split("=", 1)
            else:
                # Allow no value args such as 'myscript --auto'
                key = arg
                value = ''

            args.setdefault(key, []).append(value)
        return args


class ReleaseModule(BaseCliModule):

    # Maps a releaser key (used on CLI) to the actual releaser class to use.
    # Projects can point to their own releasers in their tito.props.

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog release [options] TARGET")

        self.parser.add_option("--no-cleanup", dest="no_cleanup",
                action="store_true",
                help="do not clean up temporary build directories/files")
        self.parser.add_option("--tag", dest="tag", metavar="PKGTAG",
                help="build a specific tag instead of the latest version " +
                    "(i.e. spacewalk-java-0.4.0-1)")

        self.parser.add_option("--dry-run", dest="dry_run",
                action="store_true", default=False,
                help="Do not actually commit/push anything during release.")

        self.parser.add_option("--all", action="store_true",
                help="Run all release targets configured.")

        self.parser.add_option("--test", action="store_true",
                help="use current branch HEAD instead of latest package tag")

        self.parser.add_option("-y", "--yes", dest="auto_accept", action="store_true",
                help="Do not require input, just accept commits and builds")

        self.parser.add_option("--all-starting-with", dest="all_starting_with",
                help="Run all release targets starting with the given string.")

        self.parser.add_option("-l", "--list", dest="list_releasers",
                action="store_true",
                help="List all configured release targets.")

        self.parser.add_option("--no-build", dest="no_build",
                action="store_true", default=False,
                help="Do not perform a build after a DistGit commit")

        self.parser.add_option("-s", "--scratch", dest="scratch",
                action="store_true",
                help="Perform a scratch build in Koji")
        self.parser.add_option("--arg", dest="builder_args",
                action="append",
                help="Custom arguments to pass to the builder."
                    " (key=value)")

    def _validate_options(self):

        if self.options.all and self.options.all_starting_with:
            error_out("Cannot combine --all and --all-starting-with.")

        if (self.options.all or self.options.all_starting_with) and \
                len(self.args) > 1:
            error_out("Cannot use explicit release targets with "
                    "--all or --all-starting-with.")

    def _read_releaser_config(self):
        """
        Read the releaser targets from .tito/releasers.conf.
        """
        rel_eng_dir = os.path.join(find_git_root(), tito_config_dir())
        filename = os.path.join(rel_eng_dir, RELEASERS_CONF_FILENAME)
        config = RawConfigParser()
        config.read(filename)
        return config

    def _legacy_builder_hack(self, releaser_config):
        """
        Support the old style koji builds when config is still in global
        tito.props, as opposed to the new releasers.conf.
        """
        # Handle koji:
        if self.config.has_section("koji") and not \
                releaser_config.has_section("koji"):
            warn_out("legacy 'koji' section in tito.props, please "
                    "consider creating a target in releasers.conf.")
            print("Simulating 'koji' release target for now.")
            releaser_config.add_section('koji')
            releaser_config.set('koji', 'releaser', 'tito.release.KojiReleaser')
            releaser_config.set('koji', 'autobuild_tags',
                    self.config.get('koji', 'autobuild_tags'))

            # TODO: find a way to get koji builds going through the new release
            # target config file, tricky as each koji tag gets it's own
            # section in tito.props. They should probably all get their own
            # target.

            # for opt in ["autobuild_tags", "disttag", "whitelist", "blacklist"]:
            #     if self.config.has_option("koji", opt):
            #         releaser_config.set('koji', opt, self.config.get(
            #             "koji", opt))

    def _print_releasers(self, releaser_config):
        print("Available release targets:")
        for section in releaser_config.sections():
            print("  %s" % section)

    def _calc_release_targets(self, releaser_config):
        targets = []
        if self.options.all_starting_with:
            for target in releaser_config.sections():
                if target.startswith(self.options.all_starting_with):
                    targets.append(target)
        elif self.options.all:
            for target in releaser_config.sections():
                targets.append(target)
        else:
            targets = self.args[1:]
        return targets

    def main(self, argv):
        BaseCliModule.main(self, argv)

        releaser_config = self._read_releaser_config()

        if self.options.list_releasers:
            self._print_releasers(releaser_config)
            sys.exit(1)

        # First arg is sub-command 'release', the rest should be our release
        # targets:
        if len(self.args) < 2 and (self.options.all_starting_with is None) and \
                (self.options.all is None):
            error_out("You must supply at least one release target.")

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        package_name = get_project_name(tag=self.options.tag)

        self.load_config(package_name, build_dir, self.options.tag)
        self._legacy_builder_hack(releaser_config)

        targets = self._calc_release_targets(releaser_config)
        print("Will release to the following targets: %s" % ", ".join(targets))

        orig_cwd = os.getcwd()

        # Create an instance of the releaser we intend to use:
        for target in targets:
            print("Releasing to target: %s" % target)
            if not releaser_config.has_section(target):
                error_out("No such releaser configured: %s" % target)
            releaser_class = get_class_by_name(releaser_config.get(target, "releaser"))
            debug("Using releaser class: %s" % releaser_class)

            builder_args = {}
            if self.options.builder_args and len(self.options.builder_args) > 0:
                for arg in self.options.builder_args:
                    if '=' in arg:
                        key, value = arg.split("=", 1)
                    else:
                        # Allow no value args such as 'myscript --auto'
                        key = arg
                        value = ''

                    debug("Passing builder arg: %s = %s" % (key, value))
                    builder_args.setdefault(key, []).append(value)
            kwargs = {
                'builder_args': builder_args,
                'offline': self.options.offline
            }

            releaser = releaser_class(
                name=package_name,
                tag=self.options.tag,
                build_dir=build_dir,
                config=self.config,
                user_config=self.user_config,
                target=target,
                releaser_config=releaser_config,
                no_cleanup=self.options.no_cleanup,
                test=self.options.test,
                auto_accept=self.options.auto_accept,
                **kwargs)

            try:
                try:
                    releaser.release(dry_run=self.options.dry_run,
                            no_build=self.options.no_build,
                            scratch=self.options.scratch)
                except KeyboardInterrupt:
                    print("Interrupted, cleaning up...")
            finally:
                releaser.cleanup()

            # Make sure we go back to where we started, otherwise multiple
            # builders gets very confused:
            os.chdir(orig_cwd)
            print


class TagModule(BaseCliModule):

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog tag [options]")

        # Options for tagging new package releases:
        # NOTE: deprecated and no longer needed:
        self.parser.add_option("--tag-release", dest="tag_release",
                action="store_true",
                help=SUPPRESS_HELP)
        self.parser.add_option("--keep-version", dest="keep_version",
                action="store_true",
                help=("Use spec file version/release exactly as "
                    "specified in spec file to tag package."))
        self.parser.add_option("--use-version", dest="use_version",
                help=("Update the spec file with the specified version."))
        self.parser.add_option("--use-release", dest="use_release",
                help=("Update the spec file with the specified release."))

        self.parser.add_option("--no-auto-changelog", action="store_true",
                default=False,
                help=("Don't automatically create a changelog "
                    "entry for this tag if none is found"))
        self.parser.add_option("--accept-auto-changelog", action="store_true",
                default=False,
                help=("Automatically accept the generated changelog."))

        self.parser.add_option("--auto-changelog-message",
                dest="auto_changelog_msg", metavar="MESSAGE",
                help=("Use MESSAGE as the default changelog message for "
                      "new packages"))

        self.parser.add_option("--changelog",
                dest="changelog", action="append",
                help=("Supply a custom changelog message to be used for this tag"))

        self.parser.add_option("--undo", "-u", dest="undo", action="store_true",
                help="Undo the most recent (un-pushed) tag.")

    def main(self, argv):
        BaseCliModule.main(self, argv)

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        package_name = get_project_name(tag=None)

        self.load_config(package_name, build_dir, None)
        if self.config.has_option(BUILDCONFIG_SECTION,
                "block_tagging"):
            debug("block_tagging defined in tito.props")
            error_out("Tagging has been disabled in this git branch.")

        tagger_class = get_class_by_name(self.config.get(
            BUILDCONFIG_SECTION, DEFAULT_TAGGER))
        debug("Using tagger class: %s" % tagger_class)

        tagger = tagger_class(config=self.config,
                user_config=self.user_config,
                keep_version=self.options.keep_version,
                offline=self.options.offline)

        try:
            return tagger.run(self.options)
        except TitoException:
            e = sys.exc_info()[1]
            error_out(e.message)

    def _validate_options(self):
        if self.options.keep_version and self.options.use_version:
            error_out("Cannot combine --keep-version and --use-version")


class InitModule(BaseCliModule):
    """ CLI Module for initializing a project for use with tito. """

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog init [options]")

    def main(self, argv):
        # DO NOT CALL BaseCliModule.main(self)
        # we are initializing tito to work in this module and
        # calling main will result in a configuration error.
        (self.options, self.args) = self.parser.parse_args(argv)
        should_commit = False

        rel_eng_dir = os.path.join(find_git_root(), '.tito')
        if not os.path.exists(rel_eng_dir):
            print("Creating tito metadata in: %s" % rel_eng_dir)
            os.makedirs(rel_eng_dir)
            print("   - created %s" % rel_eng_dir)
        else:
            print("Reinitializing existing tito metadata in %s" % rel_eng_dir)

        propsfile = os.path.join(rel_eng_dir, TITO_PROPS)
        if not os.path.exists(propsfile):
            # write out tito.props
            out_f = open(propsfile, 'w')
            out_f.write("[buildconfig]\n")
            out_f.write("builder = %s\n" % 'tito.builder.Builder')
            out_f.write(
                "tagger = %s\n" % 'tito.tagger.VersionTagger')
            out_f.write("changelog_do_not_remove_cherrypick = 0\n")
            out_f.write("changelog_format = %s (%ae)\n")
            out_f.close()
            print("   - wrote %s" % TITO_PROPS)

            getoutput('git add %s' % propsfile)
            should_commit = True

        # prep the packages metadata directory
        pkg_dir = os.path.join(rel_eng_dir, "packages")
        readme = os.path.join(pkg_dir, '.readme')

        if not os.path.exists(readme):
            if not os.path.exists(pkg_dir):
                os.makedirs(pkg_dir)
                print("   - created %s" % pkg_dir)

            # write out readme file explaining what pkg_dir is for
            readme = os.path.join(pkg_dir, '.readme')
            out_f = open(readme, 'w')
            out_f.write("the .tito/packages directory contains metadata files\n")
            out_f.write("named after their packages. Each file has the latest tagged\n")
            out_f.write("version and the project's relative directory.\n")
            out_f.close()
            print("   - wrote %s" % readme)

            getoutput('git add %s' % readme)
            should_commit = True

        if should_commit:
            getoutput('git commit -m "Initialized to use tito. "')
            print("   - committed to git")

        info_out("Done!")
        return []


class ReportModule(BaseCliModule):
    """ CLI Module For Various Reports. """

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog report [options]")

        self.parser.add_option("--untagged-diffs", dest="untagged_report",
                action="store_true",
                help="%s %s %s" % (
                    "Print out diffs for all packages with changes between",
                    "their most recent tag and HEAD. Useful for determining",
                    "which packages are in need of a re-tag.",
                ))
        self.parser.add_option("--untagged-commits", dest="untagged_commits",
                action="store_true",
                help="%s %s %s" % (
                    "Print out the list for all packages with changes between",
                    "their most recent tag and HEAD. Useful for determining",
                    "which packages are in need of a re-tag.",
                ))

    def main(self, argv):
        BaseCliModule.main(self, argv)

        if self.options.untagged_report:
            self._run_untagged_report(self.config)
            sys.exit(1)

        if self.options.untagged_commits:
            self._run_untagged_commits(self.config)
            sys.exit(1)
        return []

    def _run_untagged_commits(self, config):
        """
        Display a report of all packages with differences between HEAD and
        their most recent tag, as well as a patch for that diff. Used to
        determine which packages are in need of a rebuild.
        """
        print("Scanning for packages that may need to be tagged...")
        print("")
        git_root = find_git_root()
        rel_eng_dir = os.path.join(git_root, tito_config_dir())
        os.chdir(git_root)
        package_metadata_dir = os.path.join(rel_eng_dir, "packages")
        for root, dirs, files in os.walk(package_metadata_dir):
            for md_file in files:
                if md_file[0] == '.':
                    continue
                f = open(os.path.join(package_metadata_dir, md_file))
                (version, relative_dir) = f.readline().strip().split(" ")

                # Hack for single project git repos:
                if relative_dir == '/':
                    relative_dir = ""

                project_dir = os.path.join(git_root, relative_dir)
                self._print_log(config, md_file, version, project_dir)

    def _run_untagged_report(self, config):
        """
        Display a report of all packages with differences between HEAD and
        their most recent tag, as well as a patch for that diff. Used to
        determine which packages are in need of a rebuild.
        """
        print("Scanning for packages that may need to be tagged...")
        print("")
        git_root = find_git_root()
        rel_eng_dir = os.path.join(git_root, tito_config_dir())
        os.chdir(git_root)
        package_metadata_dir = os.path.join(rel_eng_dir, "packages")
        for root, dirs, files in os.walk(package_metadata_dir):
            for md_file in files:
                if md_file[0] == '.':
                    continue
                f = open(os.path.join(package_metadata_dir, md_file))
                (version, relative_dir) = f.readline().strip().split(" ")

                # Hack for single project git repos:
                if relative_dir == '/':
                    relative_dir = ""

                project_dir = os.path.join(git_root, relative_dir)
                self._print_diff(config, md_file, version, project_dir,
                        relative_dir)

    def _print_log(self, config, package_name, version, project_dir):
        """
        Print the log between the most recent package tag and HEAD, if
        necessary.
        """
        last_tag = "%s-%s" % (package_name, version)
        try:
            os.chdir(project_dir)
            patch_command = ("git log --pretty=oneline "
                "--relative %s..%s -- %s" % (last_tag, "HEAD", "."))
            output = run_command(patch_command)
            if (output):
                print("-" * (len(last_tag) + 8))
                print("%s..%s:" % (last_tag, "HEAD"))
                print(output)
        except:
            print("%s no longer exists" % project_dir)

    def _print_diff(self, config, package_name, version,
            full_project_dir, relative_project_dir):
        """
        Print a diff between the most recent package tag and HEAD, if
        necessary.
        """
        last_tag = "%s-%s" % (package_name, version)
        os.chdir(full_project_dir)
        patch_command = "git diff --relative %s..%s" % \
                (last_tag, "HEAD")
        output = run_command(patch_command)

        # If the diff contains 1 line then there is no diff:
        linecount = len(output.split("\n"))
        if linecount == 1:
            return

        name_and_version = "%s   %s" % (package_name, relative_project_dir)
        # Otherwise, print out info on the diff for this package:
        print("#" * len(name_and_version))
        print(name_and_version)
        print("#" * len(name_and_version))
        print("")
        print(patch_command)
        print("")
        print(output)
        print("")
        print("")
        print("")
        print("")
        print("")


CLI_MODULES = {
    "build": BuildModule,
    "tag": TagModule,
    "release": ReleaseModule,
    "report": ReportModule,
    "init": InitModule,
}


def main():
    """Command line's entry point."""
    try:
        CLI().main(sys.argv[1:])
    except TitoException:
        e = sys.exc_info()[1]
        error_out(e.message)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
