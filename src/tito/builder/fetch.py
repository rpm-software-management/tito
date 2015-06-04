# Copyright (c) 2008-2014 Red Hat, Inc.
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

import re
import os.path
import shutil

from tito.builder.main import BuilderBase
from tito.config_object import ConfigObject
from tito.common import error_out, debug, get_spec_version_and_release, \
    get_class_by_name


class FetchBuilder(ConfigObject, BuilderBase):
    """
    A separate Builder class for projects whose source is not in git. Source
    is fetched via a configurable strategy, which also determines what version
    and release to insert into the spec file.

    Cannot build past tags.
    """
    # TODO: test only for now, setup a tagger to fetch sources and store in git annex,
    # then we can do official builds as well.
    REQUIRED_ARGS = []

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            args=None, **kwargs):

        BuilderBase.__init__(self, name=name, build_dir=build_dir,
                config=config,
                user_config=user_config, args=args, **kwargs)

        if tag:
            error_out("FetchBuilder does not support building specific tags.")

        if not config.has_option("builder",
                "fetch_strategy"):
            print("WARNING: no fetch_strategy specified in tito.props"
                    ", assuming ArgSourceStrategy.")
            if not config.has_section("builder"):
                config.add_section("builder")
            config.set('builder', 'fetch_strategy',
                    'tito.builder.fetch.ArgSourceStrategy')

        self.build_tag = '%s-%s' % (self.project_name,
                get_spec_version_and_release(self.start_dir, '%s.spec' % self.project_name))

    def tgz(self):
        self.ran_tgz = True
        self._create_build_dirs()

        print("Fetching sources...")
        source_strat_class = get_class_by_name(self.config.get(
            'builder', 'fetch_strategy'))
        source_strat = source_strat_class(self)
        source_strat.fetch()
        self.sources = source_strat.sources
        self.spec_file = source_strat.spec_file

    def _get_rpmbuild_dir_options(self):
        return ('--define "_topdir %s" --define "_sourcedir %s" --define "_builddir %s" '
            '--define "_srcrpmdir %s" --define "_rpmdir %s" ' % (
                self.rpmbuild_dir,
                self.rpmbuild_sourcedir, self.rpmbuild_builddir,
                self.rpmbuild_basedir, self.rpmbuild_basedir))


class SourceStrategy(object):
    """
    Base class for source strategies. These are responsible for fetching the
    sources the builder will use, and determining what version/release we're
    building.

    This is created and run in the tgz step of the builder. It will be passed
    a reference to the builder calling it, which will be important for accessing
    a lot of required information.

    Ideally sources and the spec file to be used should be copied into
    builder.rpmbuild_sourcedir, which will be cleaned up automatically after
    the builder runs.
    """
    def __init__(self, builder):
        """
        Defines fields that should be set when a sub-class runs fetch.
        """
        self.builder = builder

        # Full path to the spec file we'll actually use to build, should be a
        # copy, never a live spec file in a git repo as sometimes it will be
        # modified:
        self.spec_file = None

        # Will contain the full path to each source we gather:
        self.sources = []

        # The version we're building:
        self.version = None

        # The release we're building:
        self.release = None

    def fetch(self):
        raise NotImplementedError()


class ArgSourceStrategy(SourceStrategy):
    """
    Assumes the builder was passed an explicit argument specifying which source
    file(s) to use.
    """
    def fetch(self):

        # Assuming we're still in the start directory, get the absolute path
        # to all sources specified:
        # TODO: support passing of multiple sources here.
        # TODO: error out if not present
        manual_sources = [self.builder.args['source'][0]]
        debug("Got sources: %s" % manual_sources)

        # Copy the live spec from our starting location. Unlike most builders,
        # we are not using a copy from a past git commit.
        self.spec_file = os.path.join(self.builder.rpmbuild_sourcedir,
                    '%s.spec' % self.builder.project_name)
        shutil.copyfile(
            os.path.join(self.builder.start_dir, '%s.spec' %
                self.builder.project_name),
            self.spec_file)
        print("  %s.spec" % self.builder.project_name)

        # TODO: Make this a configurable strategy:
        i = 0
        replacements = []
        for s in manual_sources:
            base_name = os.path.basename(s)
            dest_filepath = os.path.join(self.builder.rpmbuild_sourcedir,
                    base_name)
            shutil.copyfile(s, dest_filepath)
            self.sources.append(dest_filepath)

            # Add a line to replace in the spec for each source:
            source_regex = re.compile("^(source%s:\s*)(.+)$" % i, re.IGNORECASE)
            new_line = "Source%s: %s\n" % (i, base_name)
            replacements.append((source_regex, new_line))

        # Replace version and release in spec:
        version_regex = re.compile("^(version:\s*)(.+)$", re.IGNORECASE)
        release_regex = re.compile("^(release:\s*)(.+)$", re.IGNORECASE)

        (self.version, self.release) = self._get_version_and_release()
        print("Building version: %s" % self.version)
        print("Building release: %s" % self.release)
        replacements.append((version_regex, "Version: %s\n" % self.version))
        replacements.append((release_regex, "Release: %s\n" % self.release))

        self.replace_in_spec(replacements)

    def _get_version_and_release(self):
        """
        Get the version and release from the builder.
        Sources are configured at this point.
        """
        # Assuming source0 is a tar.gz we can extract a version and possibly
        # release from:
        base_name = os.path.basename(self.sources[0])
        debug("Extracting version/release from: %s" % base_name)

        # usually a source tarball won't have a release, that is an RPM concept.
        # Don't forget dist!
        release = "1%{?dist}"

        # Example filename: tito-0.4.18.tar.gz:
        simple_version_re = re.compile(".*-(.*).(tar.gz|tgz|zip|bz2)")
        match = re.search(simple_version_re, base_name)
        if match:
            version = match.group(1)
        else:
            error_out("Unable to determine version from file: %s" % base_name)

        return (version, release)

    def replace_in_spec(self, replacements):
        """
        Replace lines in the spec file using the given replacements.

        Replacements are a tuple of a regex to look for, and a new line to
        substitute in when the regex matches.

        Replaces all lines with one pass through the file.
        """
        in_f = open(self.spec_file, 'r')
        out_f = open(self.spec_file + ".new", 'w')
        for line in in_f.readlines():
            for line_regex, new_line in replacements:
                match = re.match(line_regex, line)
                if match:
                    line = new_line
            out_f.write(line)

        in_f.close()
        out_f.close()
        shutil.move(self.spec_file + ".new", self.spec_file)
