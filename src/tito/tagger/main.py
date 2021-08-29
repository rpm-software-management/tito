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
Code for tagging Spacewalk/Satellite packages.
"""

import os
import re
import rpm
import shutil
import subprocess
import sys
import tempfile
import textwrap

try:
    from shlex import quote
except ImportError:
    from pipes import quote

from string import Template

from time import strftime

from tito.common import (debug, error_out, run_command,
        find_spec_like_file, get_project_name, get_latest_tagged_version,
        get_spec_version_and_release, replace_version,
        tag_exists_locally, tag_exists_remotely, head_points_to_tag, undo_tag,
        increase_version, reset_release, increase_zstream, warn_out,
        BUILDCONFIG_SECTION, get_relative_project_dir_cwd, info_out,
        get_git_user_info)
from tito.compat import write, StringIO, getstatusoutput
from tito.exception import TitoException
from tito.config_object import ConfigObject
from tito.tagger.cargobump import CargoBump


class VersionTagger(ConfigObject):
    """
    Standard Tagger class, used for tagging packages built from source in
    git. (as opposed to packages which commit a tarball directly into git).

    Releases will be tagged by incrementing the package version,
    and the actual RPM "release" will always be set to 1.
    """

    def __init__(self, config=None, keep_version=False, offline=False, user_config=None):
        ConfigObject.__init__(self, config=config)
        self.user_config = user_config

        self.full_project_dir = os.getcwd()
        self.spec_file_name = find_spec_like_file()
        self.project_name = get_project_name(tag=None)

        self.relative_project_dir = get_relative_project_dir_cwd(
            self.git_root)  # i.e. java/

        self.spec_file = os.path.join(self.full_project_dir,
                self.spec_file_name)
        self.keep_version = keep_version

        self.today = self._changelog_date()
        (self.git_user, self.git_email) = get_git_user_info()
        git_email = self.git_email
        if git_email is None:
            git_email = ''
        self.changelog_regex = re.compile('\\*\s%s\s%s(\s<%s>)?' % (self.today,
            self.git_user, git_email.replace("+", "\+").replace(".", "\.")))

        self._no_auto_changelog = False
        self._accept_auto_changelog = False
        self._new_changelog_msg = "new package built with tito"
        self._changelog = None
        self.offline = offline

    def run(self, options):
        """
        Perform the actions requested of the tagger.

        NOTE: this method may do nothing if the user requested no build actions
        be performed. (i.e. only release tagging, etc)
        """
        if options.tag_release:
            warn_out("--tag-release option no longer necessary,"
                " 'tito tag' will accomplish the same thing.")
        if options.no_auto_changelog:
            self._no_auto_changelog = True
        if options.accept_auto_changelog:
            self._accept_auto_changelog = True
        if options.auto_changelog_msg:
            self._new_changelog_msg = options.auto_changelog_msg
        if options.use_version:
            self._use_version = options.use_version
        if options.use_release:
            self._use_release = options.use_release
        if options.changelog:
            self._changelog = options.changelog

        self.check_tag_precondition()

        # Only two paths through the tagger module right now:
        if options.undo:
            self._undo()
        else:
            self._tag_release()

    def check_tag_precondition(self):
        if self.config.has_option("tagconfig", "require_package"):
            packages = self.config.get("tagconfig", "require_package").split(',')
            ts = rpm.TransactionSet()
            missing_packages = []
            for p in packages:
                p = p.strip()
                mi = ts.dbMatch('name', p)
                if not mi:
                    missing_packages.append(p)
            if missing_packages:
                raise TitoException("To tag this package, you must first install: %s" %
                    ', '.join(missing_packages))

    def _tag_release(self):
        """
        Tag a new version of the package. (i.e. x.y.z+1)
        """
        self._make_changelog()
        new_version = self._bump_version()
        self._check_tag_does_not_exist(self._get_new_tag(new_version))
        self._update_changelog(new_version)
        CargoBump.tag_new_version(self.full_project_dir, new_version)
        self._update_setup_py(new_version)
        self._update_pom_xml(new_version)
        self._update_package_metadata(new_version)

    def _undo(self):
        """
        Undo the most recent tag.

        Tag commit must be the most recent commit, and the tag must not
        exist in the remote git repo, otherwise we report and error out.
        """
        tag = self._get_tag_for_version(get_latest_tagged_version(self.project_name))
        info_out("Undoing tag: %s" % tag)
        if not tag_exists_locally(tag):
            raise TitoException(
                "Cannot undo tag that does not exist locally.")
        if not self.offline and tag_exists_remotely(tag):
            raise TitoException("Cannot undo tag that has been pushed.")

        # Tag must be the most recent commit.
        if not head_points_to_tag(tag):
            raise TitoException("Cannot undo if tag is not the most recent commit.")

        # Everything looks good:
        print
        undo_tag(tag)

    def _changelog_date(self):
        option = (BUILDCONFIG_SECTION, "changelog_date_with_time")
        if self.config.has_option(*option) and self.config.getboolean(*option):
            return strftime("%a %b %d %T %Z %Y")
        return strftime("%a %b %d %Y")

    def _changelog_remove_cherrypick(self, line):
        """
        remove text "(cherry picked from commit ..." from line unless
        changelog_do_not_remove_cherrypick is specified in [BUILDCONFIG_SECTION]
        """
        if not (self.config.has_option(BUILDCONFIG_SECTION, "changelog_do_not_remove_cherrypick")
            and self.config.get(BUILDCONFIG_SECTION, "changelog_do_not_remove_cherrypick")
            and self.config.get(BUILDCONFIG_SECTION, "changelog_do_not_remove_cherrypick").strip() != '0'):
            m = re.match("(.+)(\(cherry picked from .*\))", line)
            if m:
                line = m.group(1)
        return line

    def _changelog_format(self):
        """
        If you have set changelog_format in [BUILDCONFIG_SECTION], it will return
        that string.  Otherwise, return one of two defaults:

        - '%s (%ae)', if changelog_with_email is unset or evaluates to True
        - '%s', if changelog_with_email is set and evaluates to False
        """
        result = ''
        if self.config.has_option(BUILDCONFIG_SECTION, "changelog_format"):
            result = self.config.get(BUILDCONFIG_SECTION, "changelog_format")
        else:
            with_email = ''
            if (self.config.has_option(BUILDCONFIG_SECTION, "changelog_with_email")
                and (self.config.get(BUILDCONFIG_SECTION, "changelog_with_email")) not in ['0', '']) or \
                not self.config.has_option(BUILDCONFIG_SECTION, "changelog_with_email"):
                with_email = ' (%ae)'
            result = "%%s%s" % with_email
        return result

    def _generate_default_changelog(self, last_tag):
        """
        Run git-log and will generate changelog, which still can be edited by user
        in _make_changelog.
        """
        patch_command = "git log"
        if self.config.has_option(BUILDCONFIG_SECTION, "keep_merge_commits"):
            keep = self.config.get(BUILDCONFIG_SECTION, "keep_merge_commits")
            if not keep or keep.strip().lower() not in ['1', 'true']:
                patch_command += " --no-merges"
        else:
            patch_command += " --no-merges"
        patch_command += " --pretty='format:%s' --relative %s..%s -- %s" % (
            self._changelog_format(), last_tag, "HEAD", ".")
        output = run_command(patch_command)
        result = []
        for line in output.split('\n'):
            line = line.replace('%', '%%')
            result.extend([self._changelog_remove_cherrypick(line)])
        return '\n'.join(result)

    def _make_changelog(self):
        """
        Create a new changelog entry in the spec, with line items from git
        """
        if self._no_auto_changelog:
            debug("Skipping changelog generation.")
            return

        in_f = open(self.spec_file, 'r')
        out_f = open(self.spec_file + ".new", 'w')

        found_changelog = False
        for line in in_f.readlines():
            out_f.write(line)

            if not found_changelog and line.startswith("%changelog"):
                found_changelog = True

                old_version = get_latest_tagged_version(self.project_name)

                fd, name = tempfile.mkstemp()
                write(fd, "# Create your changelog entry below:\n")
                if self.git_email is None or (('HIDE_EMAIL' in self.user_config) and
                        (self.user_config['HIDE_EMAIL'] not in ['0', ''])):
                    header = "* %s %s\n" % (self.today, self.git_user)
                else:
                    header = "* %s %s <%s>\n" % (self.today, self.git_user,
                       self.git_email)

                write(fd, header)

                # don't die if this is a new package with no history
                if self._changelog is not None:
                    for entry in self._changelog:
                        if not entry.startswith('-'):
                            entry = '- ' + entry
                        write(fd, entry)
                        write(fd, "\n")
                else:
                    if old_version is not None:
                        last_tag = self._get_new_tag(old_version)
                        output = self._generate_default_changelog(last_tag)
                    else:
                        output = self._new_changelog_msg

                    for cmd_out in output.split("\n"):
                        write(fd, "- ")
                        write(fd, "\n  ".join(textwrap.wrap(cmd_out, 77)))
                        write(fd, "\n")

                write(fd, "\n")

                if not self._accept_auto_changelog:
                    # Give the user a chance to edit the generated changelog:
                    editor = 'vi'
                    if "EDITOR" in os.environ:
                        editor = os.environ["EDITOR"]
                    subprocess.call(editor.split() + [name])

                os.lseek(fd, 0, 0)
                f = os.fdopen(fd)

                for line in f.readlines():
                    if not line.startswith("#"):
                        out_f.write(line)

                output = f.read()

                f.close()
                os.unlink(name)

        if not found_changelog:
            warn_out("no %changelog section find in spec file. Changelog entry was not appended.")

        in_f.close()
        out_f.close()

        shutil.move(self.spec_file + ".new", self.spec_file)

    def _update_changelog(self, new_version):
        """
        Update the changelog with the new version.
        """
        # Not thrilled about having to re-read the file here but we need to
        # check for the changelog entry before making any modifications, then
        # bump the version, then update the changelog.
        f = open(self.spec_file, 'r')
        buf = StringIO()
        found_match = False
        for line in f.readlines():
            match = self.changelog_regex.match(line)
            if match and not found_match:
                buf.write("%s %s\n" % (match.group(), new_version))
                found_match = True
            else:
                buf.write(line)
        f.close()

        # Write out the new file contents with our modified changelog entry:
        f = open(self.spec_file, 'w')
        f.write(buf.getvalue())
        f.close()
        buf.close()

    def _update_setup_py(self, new_version):
        """
        If this project has a setup.py, attempt to update it's version.
        """
        self._update_version_file(new_version)

        setup_file = os.path.join(self.full_project_dir, "setup.py")
        if not os.path.exists(setup_file):
            return

        debug("Found setup.py, attempting to update version.")

        # We probably don't want version-release in setup.py as release is
        # an rpm concept. Hopefully this assumption on
        py_new_version = new_version.split('-')[0]

        f = open(setup_file, 'r')
        buf = StringIO()
        for line in f.readlines():
            buf.write(replace_version(line, py_new_version))
        f.close()

        # Write out the new setup.py file contents:
        f = open(setup_file, 'w')
        f.write(buf.getvalue())
        f.close()
        buf.close()

        run_command("git add %s" % setup_file)

    def _update_pom_xml(self, new_version):
        """
        If this project uses Maven, attempt to update the version in pom.xml
        """
        # Remove the release since Maven doesn't understand that really

        pom_file = os.path.join(self.full_project_dir, "pom.xml")
        if not os.path.exists(pom_file):
            return

        mvn_new_version = new_version.split('-')[0]

        maven_args = ['-B']
        if 'MAVEN_ARGS' in self.user_config:
            maven_args.append(self.user_config['MAVEN_ARGS'])
        else:
            maven_args.append('-q')

        run_command("mvn %s versions:set -DnewVersion=%s -DgenerateBackupPoms=false" % (
            " ".join(maven_args),
            mvn_new_version))
        run_command("git add %s" % pom_file)

    def _bump_version(self, release=False, zstream=False):
        """
        Bump up the package version in the spec file.

        Set release to True to bump the package release instead.

        Checks for the keep version option and if found, won't actually
        bump the version or release.
        """
        old_version = get_latest_tagged_version(self.project_name)
        if old_version is None:
            old_version = "untagged"
        if not self.keep_version:
            version_regex = re.compile("^(version:\s*)(.+)$", re.IGNORECASE)
            release_regex = re.compile("^(release:\s*)(.+)$", re.IGNORECASE)

            in_f = open(self.spec_file, 'r')
            out_f = open(self.spec_file + ".new", 'w')

            for line in in_f.readlines():
                version_match = re.match(version_regex, line)
                release_match = re.match(release_regex, line)

                if version_match and not zstream and not release:
                    current_version = version_match.group(2)
                    if hasattr(self, '_use_version'):
                        updated_content = self._use_version
                    else:
                        updated_content = increase_version(current_version)

                    line = "".join([version_match.group(1), updated_content, "\n"])

                elif release_match:
                    current_release = release_match.group(2)
                    if hasattr(self, '_use_release'):
                        updated_content = self._use_release
                    elif release:
                        updated_content = increase_version(current_release)
                    elif zstream:
                        updated_content = increase_zstream(current_release)
                    else:
                        updated_content = reset_release(current_release)

                    line = "".join([release_match.group(1), updated_content, "\n"])

                out_f.write(line)

            in_f.close()
            out_f.close()
            shutil.move(self.spec_file + ".new", self.spec_file)

        new_version = get_spec_version_and_release(self.full_project_dir,
                self.spec_file_name)
        if new_version.strip() == "":
            msg = "Error getting bumped package version, try: \n"
            msg = msg + "  'rpm -q --specfile %s'" % self.spec_file
            error_out(msg)
        info_out("Tagging new version of %s: %s -> %s" % (self.project_name,
            old_version, new_version))
        return new_version

    def release_type(self):
        """ return short string which explain type of release.
            e.g. 'minor release
            Child classes probably want to override this.
        """
        return "release"

    def _update_package_metadata(self, new_version):
        """
        We track package metadata in the .tito/packages/ directory. Each
        file here stores the latest package version (for the git branch you
        are on) as well as the relative path to the project's code. (from the
        git root)
        """
        self._clear_package_metadata()

        new_version_w_suffix = self._get_suffixed_version(new_version)
        # Write out our package metadata:
        metadata_file = os.path.join(self.rel_eng_dir, "packages",
                self.project_name)

        with open(metadata_file, 'w') as f:
            f.write("%s %s\n" % (new_version_w_suffix, self.relative_project_dir))

        # Git add it (in case it's a new file):
        run_command("git add %s" % metadata_file)
        run_command("git add %s" % os.path.join(self.full_project_dir,
            self.spec_file_name))

        fmt = ('Automatic commit of package '
               '[%(name)s] %(release_type)s [%(version)s].')
        if self.config.has_option(BUILDCONFIG_SECTION, "tag_commit_message_format"):
            fmt = self.config.get(BUILDCONFIG_SECTION, "tag_commit_message_format")
        new_version_w_suffix = self._get_suffixed_version(new_version)
        try:
            msg = fmt % {
                'name': self.project_name,
                'release_type': self.release_type(),
                'version': new_version_w_suffix,
            }
        except KeyError:
            exc = sys.exc_info()[1]
            raise TitoException('Unknown placeholder %s in tag_commit_message_format'
                                % exc)

        run_command('git commit -m {0} -m {1} -m {2}'.format(
            quote(msg), quote("Created by command:"), quote(" ".join(sys.argv[:]))))

        new_tag = self._get_new_tag(new_version)
        tag_msg = "Tagging package [%s] version [%s] in directory [%s]." % \
                (self.project_name, new_tag,
                        self.relative_project_dir)

        # Optionally gpg sign the tag
        sign_tag = ""
        if self.config.has_option(BUILDCONFIG_SECTION, "sign_tag"):
            if self.config.getboolean(BUILDCONFIG_SECTION, "sign_tag"):
                sign_tag = "-s "

        run_command('git tag %s -m "%s" %s' % (sign_tag, tag_msg, new_tag))
        print
        info_out("Created tag: %s" % new_tag)
        print("   View: git show HEAD")
        print("   Undo: tito tag -u")
        print("   Push: git push --follow-tags origin")

    def _check_tag_does_not_exist(self, new_tag):
        status, output = getstatusoutput(
            'git tag -l %s|grep ""' % new_tag)
        if status == 0:
            raise Exception("Tag %s already exists!" % new_tag)

    def _clear_package_metadata(self):
        """
        Remove all .tito/packages/ files that have a relative path
        matching the package we're tagging a new version of. Normally
        this just removes the previous package file but if we were
        renaming oldpackage to newpackage, this would git rm
        .tito/packages/oldpackage and add
        .tito/packages/spacewalk-newpackage.
        """
        metadata_dir = os.path.join(self.rel_eng_dir, "packages")
        for filename in os.listdir(metadata_dir):
            metadata_file = os.path.join(metadata_dir, filename)  # full path

            if os.path.isdir(metadata_file) or filename.startswith("."):
                continue

            temp_file = open(metadata_file, 'r')
            (version, relative_dir) = temp_file.readline().split(" ")
            relative_dir = relative_dir.strip()  # sometimes has a newline

            if relative_dir == self.relative_project_dir:
                debug("Found metadata for our prefix: %s" %
                        metadata_file)
                debug("   version: %s" % version)
                debug("   dir: %s" % relative_dir)
                if filename == self.project_name:
                    debug("Updating %s with new version." %
                            metadata_file)
                else:
                    warn_out("%s also references %s" % (filename, self.relative_project_dir))
                    print("Assuming package has been renamed and removing it.")
                    run_command("git rm %s" % metadata_file)

    def _get_new_tag(self, version_and_release):
        """ Returns the actual tag we'll be creating. """
        suffixed_version = self._get_suffixed_version(self._get_version(version_and_release))
        release = self._get_release(version_and_release)
        return self._get_tag_for_version(suffixed_version, release)

    def _get_release(self, version_and_release):
        return version_and_release.split('-')[-1]

    def _get_version(self, version_and_release):
        return version_and_release.split('-')[-2]

    def _get_suffixed_version(self, version):
        """ If global config specifies a tag suffix, use it """
        suffix = ""
        if self.config.has_option(BUILDCONFIG_SECTION, "tag_suffix"):
            suffix = self.config.get(BUILDCONFIG_SECTION, "tag_suffix")
        return "{0}{1}".format(version, suffix)

    def _get_tag_for_version(self, version, release=''):
        """
        Determine what the tag will look like for a given version.
        Can be overridden when custom taggers override counterpart,
        tito.Builder._get_tag_for_version().
        """
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

    def _update_version_file(self, new_version):
        """
        land this new_version in the designated file
        and stages that file for a git commit
        """
        version_file = self._version_file_path()
        if not version_file:
            debug("No destination version file found, skipping.")
            return

        debug("Found version file to write: %s" % version_file)
        version_file_template = self._version_file_template()
        if version_file_template is None:
            error_out("Version file specified but without corresponding template.")

        t = Template(version_file_template)
        f = open(version_file, 'w')
        (new_ver, new_rel) = new_version.split('-')
        f.write(t.safe_substitute(
            version=new_ver,
            release=new_rel))
        f.close()

        run_command("git add %s" % version_file)

    def _version_file_template(self):
        """
        provide a configuration in tito.props to a file that is a
        python string.Template conforming blob, like
            [version_template]
            template_file = ./.tito/templates/my_java_properties

        variables defined inside the template are $version and $release

        see also http://docs.python.org/2/library/string.html#template-strings
        """
        if self.config.has_option("version_template", "template_file"):
            f = open(os.path.join(self.git_root,
                self.config.get("version_template", "template_file")), 'r')
            buf = f.read()
            f.close()
            return buf
        return None

    def _version_file_path(self):
        """
        provide a version file to write in tito.props, like
            [version_template]
            destination_file = ./foo.rb
        """
        if self.config.has_option("version_template", "destination_file"):
            return self.config.get("version_template", "destination_file")
        return None


class ReleaseTagger(VersionTagger):
    """
    Tagger which increments the spec file release instead of version.

    Used for:
      - Packages we build from a tarball checked directly into git.
      - Satellite packages built on top of Spacewalk tarballs.
    """

    def _tag_release(self):
        """
        Tag a new release of the package. (i.e. x.y.z-r+1)
        """
        self._make_changelog()
        # the user might have passed --use-version
        # so let's just bump the release if they did not
        bump_release = not hasattr(self, '_use_version')
        new_version = self._bump_version(release=bump_release)

        self._check_tag_does_not_exist(self._get_new_tag(new_version))
        self._update_changelog(new_version)
        self._update_package_metadata(new_version)

    def release_type(self):
        """ return short string "minor release" """
        return "minor release"


class ForceVersionTagger(VersionTagger):
    """
    Legacy Tagger which is chosen when a user passes the `--use-version`
    flag in on the command line. This implementation has been merged with
    the default `VersionTagger`, and remains only for backward compatibility
    for users that were overriding this class with a custom implementation.
    TODO: remove this class in a future release
    """
