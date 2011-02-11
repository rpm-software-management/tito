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
import random
import commands
import ConfigParser

from optparse import OptionParser

from tito.common import DEFAULT_BUILD_DIR
from tito.common import (find_git_root, run_command, get_class_by_name,
        error_out, debug, get_project_name, get_relative_project_dir,
        check_tag_exists, get_latest_tagged_version, normalize_class_name)
from tito.exception import *

# Hack for Python 2.4, seems to require we import these so they get compiled
# before we try to dynamically import them based on a string name.
import tito.tagger
import tito.builder

BUILD_PROPS_FILENAME = "tito.props"
GLOBAL_BUILD_PROPS_FILENAME = "tito.props"
GLOBALCONFIG_SECTION = "globalconfig"
DEFAULT_BUILDER = "default_builder"
DEFAULT_TAGGER = "default_tagger"
ASSUMED_NO_TAR_GZ_PROPS = """
[buildconfig]
builder = tito.builder.NoTgzBuilder
tagger = tito.tagger.ReleaseTagger
"""

def read_user_config():
    config = {}
    file_loc = os.path.expanduser("~/.spacewalk-build-rc")
    try:
        f = open(file_loc)
    except:
        file_loc = os.path.expanduser("~/.titorc")
        try:
            f = open(file_loc)
        except:
            # File doesn't exist but that's ok because it's optional.
            return config

    for line in f.readlines():
        if line.strip() == "":
            continue
        tokens = line.split("=")
        if len(tokens) != 2:
            raise Exception("Error parsing ~/.spacewalk-build-rc: %s" % line)
        config[tokens[0]] = tokens[1].strip()
    return config


def lookup_build_dir(user_config):
    """
    Read build_dir in from ~/.spacewalk-build-rc if it exists, otherwise
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
        if len(argv) < 1 or not argv[0] in CLI_MODULES.keys():
            self._usage()
            sys.exit(1)

        module_class = CLI_MODULES[argv[0]]
        module = module_class()
        return module.main(argv)

    def _usage(self):
        print("Usage: tito MODULENAME --help")
        print("Supported modules:")
        print("   tag      - Tag package releases.")
        print("   build    - Build packages.")
        print("   report   - Display various reports on the repo.")
        print("   init     - Initialize directory for use by tito.")


class BaseCliModule(object):
    """ Common code used amongst all CLI modules. """

    def __init__(self, usage):
        self.parser = OptionParser(usage)
        self.global_config = None
        self.options = None
        self.pkg_config = None
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
        (self.options, args) = self.parser.parse_args(argv)

        self._validate_options()

        if len(argv) < 1:
            print(self.parser.error("Must supply an argument. "
                "Try -h for help."))

        self.global_config = self._read_global_config()
        if self.global_config.has_option(GLOBALCONFIG_SECTION,
                "offline"):
            self.options.offline = True

        if self.options.debug:
            os.environ['DEBUG'] = "true"

        # Check if global config defines a custom lib dir:
        if self.global_config.has_option(GLOBALCONFIG_SECTION,
                "lib_dir"):
            lib_dir = self.global_config.get(GLOBALCONFIG_SECTION, 
                    "lib_dir")
            if lib_dir[0] != '/':
                # Looks like a relative path, assume from the git root:
                lib_dir = os.path.join(find_git_root(), lib_dir)

            if os.path.exists(lib_dir):
                sys.path.append(lib_dir)
                debug("Added lib dir to PYTHONPATH: %s" % lib_dir)
            else:
                print("WARNING: lib_dir specified but does not exist: %s" %
                        lib_dir)


    def _read_global_config(self):
        """
        Read global build.py configuration from the rel-eng dir of the git
        repository we're being run from.
        """
        rel_eng_dir = os.path.join(find_git_root(), "rel-eng")
        filename = os.path.join(rel_eng_dir, GLOBAL_BUILD_PROPS_FILENAME)
        if not os.path.exists(filename):
            # HACK: Try the old filename location, pre-tito rename:
            oldfilename = os.path.join(rel_eng_dir, "global.build.py.props")
            if not os.path.exists(oldfilename):
                error_out("Unable to locate branch configuration: %s"
                    "\nPlease run 'tito init'" % filename)
        config = ConfigParser.ConfigParser()
        config.read(filename)

        # Verify the config contains what we need from it:
        required_global_config = [
                (GLOBALCONFIG_SECTION, DEFAULT_BUILDER),
                (GLOBALCONFIG_SECTION, DEFAULT_TAGGER),
        ]
        for section, option in required_global_config:
            if not config.has_section(section) or not \
                config.has_option(section, option):
                    error_out("%s missing required config: %s %s" % (
                        filename, section, option))

        return config

    def _read_project_config(self, project_name, build_dir, tag, no_cleanup):
        """
        Read and return project build properties if they exist.

        How to describe this process... we're looking for a tito.props or
        build.py.props (legacy name) file in the project directory.

        If we're operating on a specific tag, we're looking for these same
        file's contents back at the time the tag was created. (which we write
        out to a temp file and use instead of the current file contents)

        To accomodate older tags prior to build.py, we also check for
        the presence of a Makefile with NO_TAR_GZ, and include a hack to
        assume build properties in this scenario.

        If no project specific config can be found, settings come from the
        global tito.props in rel-eng/.
        """
        debug("Determined package name to be: %s" % project_name)

        properties_file = None
        wrote_temp_file = False

        # Use the properties file in the current project directory, if it
        # exists:
        current_props_file = os.path.join(os.getcwd(), BUILD_PROPS_FILENAME)
        if (os.path.exists(current_props_file)):
            properties_file = current_props_file
        else:
            # HACK: Check for legacy build.py.props naming, needed to support
            # older tags:
            current_props_file = os.path.join(os.getcwd(), 
                    "build.py.props")
            if (os.path.exists(current_props_file)):
                properties_file = current_props_file

        # Check for a build.py.props back when this tag was created and use it
        # instead. (if it exists)
        if tag:
            relative_dir = get_relative_project_dir(project_name, tag)

            cmd = "git show %s:%s%s" % (tag, relative_dir,
                    BUILD_PROPS_FILENAME)
            debug(cmd)
            (status, output) = commands.getstatusoutput(cmd)
            if status > 0:
                # Give it another try looking for legacy props filename:
                cmd = "git show %s:%s%s" % (tag, relative_dir,
                        "build.py.props")
                debug(cmd)
                (status, output) = commands.getstatusoutput(cmd)

            temp_filename = "%s-%s" % (random.randint(1, 10000),
                    BUILD_PROPS_FILENAME)
            temp_props_file = os.path.join(build_dir, temp_filename)

            if status == 0:
                properties_file = temp_props_file
                f = open(properties_file, 'w')
                f.write(output)
                f.close()
                wrote_temp_file = True
            else:
                # HACK: No build.py.props found, but to accomodate packages
                # tagged before they existed, check for a Makefile with
                # NO_TAR_GZ defined and make some assumptions based on that.
                cmd = "git show %s:%s%s | grep NO_TAR_GZ" % \
                        (tag, relative_dir, "Makefile")
                debug(cmd)
                (status, output) = commands.getstatusoutput(cmd)
                if status == 0 and output != "":
                    properties_file = temp_props_file
                    debug("Found Makefile with NO_TAR_GZ")
                    f = open(properties_file, 'w')
                    f.write(ASSUMED_NO_TAR_GZ_PROPS)
                    f.close()
                    wrote_temp_file = True

        config = ConfigParser.ConfigParser()
        if properties_file != None:
            debug("Using build properties: %s" % properties_file)
            config.read(properties_file)
        else:
            debug("Unable to locate custom build properties for this package.")
            debug("   Using global.tito.props")

        # TODO: Not thrilled with this:
        if wrote_temp_file and not no_cleanup:
            # Delete the temp properties file we created.
            run_command("rm %s" % properties_file)

        return config

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
                help="Install any binary rpms being built. (WARNING: " + \
                    "uses sudo rpm -Uvh --force)")
        self.parser.add_option("--dist", dest="dist", metavar="DISTTAG",
                help="Dist tag to apply to srpm and/or rpm. (i.e. .el5)")

        self.parser.add_option("--test", dest="test", action="store_true",
                help="use current branch HEAD instead of latest package tag")
        self.parser.add_option("--no-cleanup", dest="no_cleanup",
                action="store_true",
                help="do not clean up temporary build directories/files")
        self.parser.add_option("--tag", dest="tag", metavar="PKGTAG",
                help="build a specific tag instead of the latest version " +
                    "(i.e. spacewalk-java-0.4.0-1)")

        self.parser.add_option("--release", dest="release",
                action="store_true", help="%s %s %s" % (
                    "Release package according to repo configuration.",
                    "(import into CVS and submit to build system, or create ",
                    "src.rpm's and submit directly to koji)",
                ))
        self.parser.add_option("--dry-run", dest="dry_run",
                action="store_true", default=False,
                help="Do not actually commit/push anything during --release.",
                )

        self.parser.add_option("--cvs-release", dest="cvs_release",
                action="store_true",
                help="Release package only in CVS. (if possible)",
                )
        self.parser.add_option("--git-release", dest="git_release",
                action="store_true",
                help="Release package only in git based build system. "
                    "(i.e. Fedora)",
                )
        self.parser.add_option("--koji-release", dest="koji_release",
                action="store_true",
                help="Release package only in Koji. (if possible)",
                )
        self.parser.add_option("--list-tags", dest="list_tags",
                action="store_true",
                help="List tags for which we build this package",
                )
        self.parser.add_option("--only-tags", dest="only_tags",
                action="append", metavar="KOJITAG",
                help="Build in koji only for specified tags",
                )
        self.parser.add_option("--upload-new-source", dest="cvs_new_sources",
                action="append",
                help=("Upload a new source tarball to CVS lookaside. "
                    "(i.e. runs 'make new-sources') Must be "
                    "used until 'sources' file is committed to CVS."))

        self.parser.add_option("--rpmbuild-options", dest='rpmbuild_options',
                default='',
                metavar="OPTIONS", help="Options to pass to rpmbuild.")
        self.parser.add_option("--scratch", dest="scratch",
                action="store_true",
                help="Do scratch build (only for --koji-release)",
                )

    def main(self, argv):
        BaseCliModule.main(self, argv)

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        package_name = get_project_name(tag=self.options.tag)

        build_tag = None
        build_version = None
        # Determine which package version we should build:
        if self.options.tag:
            build_tag = self.options.tag
            build_version = build_tag[len(package_name + "-"):]
        else:
            build_version = get_latest_tagged_version(package_name)
            if build_version == None:
                error_out(["Unable to lookup latest package info.",
                        "Perhaps you need to tag first?"])
            build_tag = "%s-%s" % (package_name, build_version)

        if not self.options.test:
            check_tag_exists(build_tag, offline=self.options.offline)

        self.pkg_config = self._read_project_config(package_name, build_dir,
                self.options.tag, self.options.no_cleanup)

        builder = self._create_builder(package_name, build_tag,
                build_version, self.options, self.pkg_config,
                build_dir)
        return builder.run(self.options)

    def _create_builder(self, package_name, build_tag, build_version, options,
            pkg_config, build_dir):
        """
        Create (but don't run) the builder class. Builder object may be
        used by other objects without actually having run() called.
        """

        builder_class = None
        if pkg_config.has_option("buildconfig", "builder"):
            builder_class = get_class_by_name(pkg_config.get("buildconfig",
                "builder"))
        else:
            builder_class = get_class_by_name(self.global_config.get(
                GLOBALCONFIG_SECTION, DEFAULT_BUILDER))
        debug("Using builder class: %s" % builder_class)

        # Instantiate the builder:
        builder = builder_class(
                name=package_name,
                version=build_version,
                tag=build_tag,
                build_dir=build_dir,
                pkg_config=pkg_config,
                global_config=self.global_config,
                user_config=self.user_config,
                options = options)
        return builder

    def _validate_options(self):
        if self.options.srpm and self.options.rpm:
            error_out("Cannot combine --srpm and --rpm")
        if self.options.test and self.options.tag:
            error_out("Cannot build test version of specific tag.")
        if (self.options.srpm or self.options.rpm) and self.options.release:
            error_out("Cannot combine --srpm/--rpm with --release.")

        if self.options.release and (self.options.cvs_release or
                self.options.koji_release):
            error_out([
                "Cannot combine --cvs-release/--koji-release with --release.",
                "(--release includes both)"])
        if self.options.release and self.options.test:
            error_out("Cannot combine --release with --test.")


class TagModule(BaseCliModule):

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog tag [options]")

        # Options for tagging new package releases:
        # NOTE: deprecated and no longer needed:
        self.parser.add_option("--tag-release", dest="tag_release",
                action="store_true",
                help="Deprecated, no longer required.")
        self.parser.add_option("--keep-version", dest="keep_version",
                action="store_true",
                help=("Use spec file version/release exactly as "
                    "specified in spec file to tag package."))

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

        self.parser.add_option("--undo", "-u", dest="undo", action="store_true",
                help="Undo the most recent (un-pushed) tag.")

    def main(self, argv):
        BaseCliModule.main(self, argv)

        if self.global_config.has_option(GLOBALCONFIG_SECTION,
                "block_tagging"):
            debug("block_tagging defined in tito.props")
            error_out("Tagging has been disabled in this git branch.")

        build_dir = os.path.normpath(os.path.abspath(self.options.output_dir))
        package_name = get_project_name(tag=None)

        self.pkg_config = self._read_project_config(package_name, build_dir,
                None, None)

        tagger_class = None
        if self.pkg_config.has_option("buildconfig", "tagger"):
            tagger_class = get_class_by_name(self.pkg_config.get("buildconfig",
                "tagger"))
        else:
            tagger_class = get_class_by_name(self.global_config.get(
                GLOBALCONFIG_SECTION, DEFAULT_TAGGER))
        debug("Using tagger class: %s" % tagger_class)

        tagger = tagger_class(global_config=self.global_config,
		user_config=self.user_config,
                keep_version=self.options.keep_version,
                offline=self.options.offline)

        try:
            return tagger.run(self.options)
        except TitoException, e:
            error_out(e.message)



class InitModule(BaseCliModule):
    """ CLI Module for initializing a project for use with tito. """

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog init [options]")

    def main(self, argv):
        # DO NOT CALL BaseCliModule.main(self)
        # we are initializing tito to work in this module and
        # calling main will result in a configuration error.
        should_commit = False

        rel_eng_dir = os.path.join(find_git_root(), "rel-eng")
        print("Creating tito metadata in: %s" % rel_eng_dir)

        propsfile = os.path.join(rel_eng_dir, GLOBAL_BUILD_PROPS_FILENAME)
        if not os.path.exists(propsfile):
            if not os.path.exists(rel_eng_dir):
                commands.getoutput("mkdir -p %s" % rel_eng_dir)
                print("   - created %s" % rel_eng_dir)

            # write out tito.props
            out_f = open(propsfile, 'w')
            out_f.write("[globalconfig]\n")
            out_f.write("default_builder = %s\n" % 'tito.builder.Builder')
            out_f.write(
                "default_tagger = %s\n" % 'tito.tagger.VersionTagger')
            out_f.write("changelog_do_not_remove_cherrypick = 0\n")
            out_f.write("changelog_with_email = 1\n")
            out_f.close()
            print("   - wrote %s" % GLOBAL_BUILD_PROPS_FILENAME)

            commands.getoutput('git add %s' % propsfile)
            should_commit = True

        # prep the packages metadata directory
        pkg_dir = os.path.join(rel_eng_dir, "packages")
        readme = os.path.join(pkg_dir, '.readme')

        if not os.path.exists(readme):
            if not os.path.exists(pkg_dir):
                commands.getoutput("mkdir -p %s" % pkg_dir)
                print("   - created %s" % pkg_dir)

            # write out readme file explaining what pkg_dir is for
            readme = os.path.join(pkg_dir, '.readme')
            out_f = open(readme, 'w')
            out_f.write("the rel-eng/packages directory contains metadata files\n")
            out_f.write("named after their packages. Each file has the latest tagged\n")
            out_f.write("version and the project's relative directory.\n")
            out_f.close()
            print("   - wrote %s" % readme)

            commands.getoutput('git add %s' % readme)
            should_commit = True

        if should_commit:
            commands.getoutput('git commit -m "Initialized to use tito. "')
            print("   - committed to git")

        print("Done!")
        return []


class ReportModule(BaseCliModule):
    """ CLI Module For Various Reports. """

    def __init__(self):
        BaseCliModule.__init__(self, "usage: %prog report [options]")

        self.parser.add_option("--untagged-diffs", dest="untagged_report",
                action="store_true",
                help= "%s %s %s" % (
                    "Print out diffs for all packages with changes between",
                    "their most recent tag and HEAD. Useful for determining",
                    "which packages are in need of a re-tag.",
                ))
        self.parser.add_option("--untagged-commits", dest="untagged_commits",
                action="store_true",
                help= "%s %s %s" % (
                    "Print out the list for all packages with changes between",
                    "their most recent tag and HEAD. Useful for determining",
                    "which packages are in need of a re-tag.",
                ))

    def main(self, argv):
        BaseCliModule.main(self, argv)

        if self.options.untagged_report:
            self._run_untagged_report(self.global_config)
            sys.exit(1)

        if self.options.untagged_commits:
            self._run_untagged_commits(self.global_config)
            sys.exit(1)
        return []

    def _run_untagged_commits(self, global_config):
        """
        Display a report of all packages with differences between HEAD and
        their most recent tag, as well as a patch for that diff. Used to
        determine which packages are in need of a rebuild.
        """
        print("Scanning for packages that may need to be tagged...")
        print("")
        git_root = find_git_root()
        rel_eng_dir = os.path.join(git_root, "rel-eng")
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
                self._print_log(global_config, md_file, version, project_dir)

    def _run_untagged_report(self, global_config):
        """
        Display a report of all packages with differences between HEAD and
        their most recent tag, as well as a patch for that diff. Used to
        determine which packages are in need of a rebuild.
        """
        print("Scanning for packages that may need to be tagged...")
        print("")
        git_root = find_git_root()
        rel_eng_dir = os.path.join(git_root, "rel-eng")
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
                self._print_diff(global_config, md_file, version, project_dir,
                        relative_dir)

    def _print_log(self, global_config, package_name, version, project_dir):
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

    def _print_diff(self, global_config, package_name, version,
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
    "report": ReportModule,
    "init": InitModule,
}


