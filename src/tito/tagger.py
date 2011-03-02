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
import commands
import StringIO
import shutil
import subprocess
import tempfile
import textwrap
import sys

from time import strftime

from tito.common import (debug, error_out, run_command, find_git_root,
        find_spec_file, get_project_name, get_latest_tagged_version,
        get_script_path, get_spec_version_and_release, replace_version,
        tag_exists_locally, tag_exists_remotely, head_points_to_tag, undo_tag)
from tito.exception import TitoException


class VersionTagger(object):
    """
    Standard Tagger class, used for tagging packages built from source in
    git. (as opposed to packages which commit a tarball directly into git).

    Releases will be tagged by incrementing the package version,
    and the actual RPM "release" will always be set to 1.
    """

    def __init__(self, global_config=None, keep_version=False, offline=False, user_config=None):
        self.git_root = find_git_root()
        self.rel_eng_dir = os.path.join(self.git_root, "rel-eng")
        self.config = global_config
	self.user_config = user_config

        self.full_project_dir = os.getcwd()
        self.spec_file_name = find_spec_file()
        self.project_name = get_project_name(tag=None)

        self.relative_project_dir = self._get_relative_project_dir(
                self.git_root) # i.e. java/

        self.spec_file = os.path.join(self.full_project_dir,
                self.spec_file_name)
        self.keep_version = keep_version

        self.today = strftime("%a %b %d %Y")
        (self.git_user, self.git_email) = self._get_git_user_info()
        git_email = self.git_email
        if git_email is None:
            git_email = ''
        self.changelog_regex = re.compile('\\*\s%s\s%s(\s<%s>)?' % (self.today,
            self.git_user, git_email.replace("+", "\+").replace(".", "\.")))

        self._no_auto_changelog = False
        self._accept_auto_changelog = False
        self._new_changelog_msg = "new package built with tito"
        self.offline = offline

    def run(self, options):
        """
        Perform the actions requested of the tagger.

        NOTE: this method may do nothing if the user requested no build actions
        be performed. (i.e. only release tagging, etc)
        """
        if options.tag_release:
            print("WARNING: --tag-release option no longer necessary,"
                " 'tito tag' will accomplish the same thing.")
        if options.no_auto_changelog:
            self._no_auto_changelog=True
        if options.accept_auto_changelog:
            self._accept_auto_changelog=True
        if options.auto_changelog_msg:
            self._new_changelog_msg = options.auto_changelog_msg

        # Only two paths through the tagger module right now:
        if options.undo:
            self._undo()
        else:
            self._tag_release()

    def _tag_release(self):
        """
        Tag a new version of the package. (i.e. x.y.z+1)
        """
        self._make_changelog()
        new_version = self._bump_version()
        self._check_tag_does_not_exist(self._get_new_tag(new_version))
        self._update_changelog(new_version)
        self._update_setup_py(new_version)
        self._update_package_metadata(new_version)

    def _undo(self):
        """
        Undo the most recent tag.

        Tag commit must be the most recent commit, and the tag must not
        exist in the remote git repo, otherwise we report and error out.
        """
        tag = "%s-%s" % (self.project_name, 
                get_latest_tagged_version(self.project_name))
        print("Undoing tag: %s" % tag)
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

    def _changelog_remove_cherrypick(self, line):
        """
        remove text "(cherry picked from commit ..." from line unless
        changelog_do_not_remove_cherrypick is specified in [globalconfig]
        """
        if not (self.config.has_option("globalconfig", "changelog_do_not_remove_cherrypick") 
            and self.config.get("globalconfig", "changelog_do_not_remove_cherrypick")):
            m = re.match("(.+)(\(cherry picked from .*\))", line)
            if m:
                line = m.group(1)
        return line

    def _changelog_email(self):
        """
        if you have set changelog_with_email in [globalconfig] set to 1, it will return 
        string '(%ae)'
        """
        result = ''
        if (self.config.has_option("globalconfig", "changelog_with_email")
            and self.config.get("globalconfig", "changelog_with_email")) or \
            not self.config.has_option("globalconfig", "changelog_with_email"):
            result = ' (%ae)'
        return result

    def _generate_default_changelog(self, last_tag):
        """
        Run git-log and will generate changelog, which still can be edited by user
        in _make_changelog.
        """
        patch_command = "git log --pretty='format:%%s%s'" \
                         " --relative %s..%s -- %s" % (self._changelog_email(), last_tag, "HEAD", ".")
        output = run_command(patch_command)
        result = []
        for line in output.split('\n'):
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

                # don't die if this is a new package with no history
                if old_version != None:
                    last_tag = "%s-%s" % (self.project_name, old_version)
                    output = self._generate_default_changelog(last_tag)
                else:
                    output = self._new_changelog_msg

                fd, name = tempfile.mkstemp()
                os.write(fd, "# Create your changelog entry below:\n")
		if self.git_email is None or (('HIDE_EMAIL' in self.user_config) and (self.user_config['HIDE_EMAIL'])):
			header = "* %s %s\n" % (self.today, self.git_user)
		else:
			header = "* %s %s <%s>\n" % (self.today, self.git_user,
				self.git_email)

                os.write(fd, header)

                for cmd_out in output.split("\n"):
                    os.write(fd, "- ")
                    os.write(fd, "\n  ".join(textwrap.wrap(cmd_out, 77)))
                    os.write(fd, "\n")

                os.write(fd, "\n")

                if not self._accept_auto_changelog:
                    # Give the user a chance to edit the generated changelog:
                    editor = 'vi'
                    if "EDITOR" in os.environ:
                        editor = os.environ["EDITOR"]
                    subprocess.call([editor, name])

                os.lseek(fd, 0, 0)
                file = os.fdopen(fd)

                for line in file.readlines():
                    if not line.startswith("#"):
                        out_f.write(line)

                output = file.read()

                file.close()
                os.unlink(name)

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
        buf = StringIO.StringIO()
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
        setup_file = os.path.join(self.full_project_dir, "setup.py")
        if not os.path.exists(setup_file):
            return

        debug("Found setup.py, attempting to update version.")

        # We probably don't want version-release in setup.py as release is 
        # an rpm concept. Hopefully this assumption on 
        py_new_version = new_version.split('-')[0]

        f = open(setup_file, 'r')
        buf = StringIO.StringIO()
        for line in f.readlines():
            buf.write(replace_version(line, py_new_version))
        f.close()

        # Write out the new setup.py file contents:
        f = open(setup_file, 'w')
        f.write(buf.getvalue())
        f.close()
        buf.close()

        run_command("git add %s" % setup_file)

    def _get_relative_project_dir(self, git_root):
        """
        Returns the patch to the project we're working with relative to the
        git root.

        *MUST* be called before doing any os.cwd().

        i.e. java/, satellite/install/Spacewalk-setup/, etc.
        """
        current_dir = os.getcwd()
        relative = current_dir[len(git_root) + 1:] + "/"
        return relative

    def _bump_version(self, release=False, zstream=False):
        """
        Bump up the package version in the spec file.

        Set release to True to bump the package release instead.

        Checks for the keep version option and if found, won't actually
        bump the version or release.
        """
        old_version = get_latest_tagged_version(self.project_name)
        if old_version == None:
            old_version = "untagged"
        # TODO: Do this here instead of calling out to an external Perl script:
        if not self.keep_version:
            bump_type = "bump-version"
            if release:
                bump_type = "bump-release"
            elif zstream:
                bump_type = "bump-zstream"

            script_path = get_script_path("bump-version.pl")
            cmd = "%s %s --specfile %s" % \
                    (script_path, bump_type, self.spec_file)
            run_command(cmd)

        new_version = self._get_spec_version_and_release()
        if new_version.strip() == "":
            msg = "Error getting bumped package version, try: \n"
            msg = msg + "  'rpm -q --specfile %s'" % self.spec_file
            error_out(msg)
        print("Tagging new version of %s: %s -> %s" % (self.project_name,
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
        We track package metadata in the rel-eng/packages/ directory. Each
        file here stores the latest package version (for the git branch you
        are on) as well as the relative path to the project's code. (from the
        git root)
        """
        self._clear_package_metadata()

        suffix = ""
        # If global config specifies a tag suffix, use it:
        if self.config.has_option("globalconfig", "tag_suffix"):
            suffix = self.config.get("globalconfig", "tag_suffix")

        new_version_w_suffix = "%s%s" % (new_version, suffix)
        # Write out our package metadata:
        metadata_file = os.path.join(self.rel_eng_dir, "packages",
                self.project_name)
        f = open(metadata_file, 'w')
        f.write("%s %s\n" % (new_version_w_suffix, self.relative_project_dir))
        f.close()

        # Git add it (in case it's a new file):
        run_command("git add %s" % metadata_file)
        run_command("git add %s" % os.path.join(self.full_project_dir,
            self.spec_file_name))

        run_command('git commit -m "Automatic commit of package ' +
                '[%s] %s [%s]."' % (self.project_name, self.release_type(),
                    new_version_w_suffix))

        tag_msg = "Tagging package [%s] version [%s] in directory [%s]." % \
                (self.project_name, new_version_w_suffix,
                        self.relative_project_dir)

        new_tag = self._get_new_tag(new_version)
        run_command('git tag -m "%s" %s' % (tag_msg, new_tag))
        print
        print("Created tag: %s" % new_tag)
        print("   View: git show HEAD")
        print("   Undo: tito tag -u")
        print("   Push: git push && git push --tags")

    def _check_tag_does_not_exist(self, new_tag):
        status, output = commands.getstatusoutput(
            'git tag | grep %s' % new_tag)
        if status == 0:
            raise Exception("Tag %s already exists!" % new_tag)

    def _clear_package_metadata(self):
        """
        Remove all rel-eng/packages/ files that have a relative path
        matching the package we're tagging a new version of. Normally
        this just removes the previous package file but if we were
        renaming oldpackage to newpackage, this would git rm
        rel-eng/packages/oldpackage and add
        rel-eng/packages/spacewalk-newpackage.
        """
        metadata_dir = os.path.join(self.rel_eng_dir, "packages")
        for filename in os.listdir(metadata_dir):
            metadata_file = os.path.join(metadata_dir, filename) # full path

            if os.path.isdir(metadata_file) or filename.startswith("."):
                continue

            temp_file = open(metadata_file, 'r')
            (version, relative_dir) = temp_file.readline().split(" ")
            relative_dir = relative_dir.strip() # sometimes has a newline

            if relative_dir == self.relative_project_dir:
                debug("Found metadata for our prefix: %s" %
                        metadata_file)
                debug("   version: %s" % version)
                debug("   dir: %s" % relative_dir)
                if filename == self.project_name:
                    debug("Updating %s with new version." %
                            metadata_file)
                else:
                    print("WARNING: %s also references %s" % (filename,
                            self.relative_project_dir))
                    print("Assuming package has been renamed and removing it.")
                    run_command("git rm %s" % metadata_file)

    def _get_git_user_info(self):
        """ Return the user.name and user.email git config values. """
	try:
		name = run_command('git config --get user.name')
	except:
		sys.stderr.write('Warning: user.name in ~/.gitconfig not set.')
		name = 'Unknown name'
	try:
		email = run_command('git config --get user.email')
	except:
		sys.stderr.write('Warning: user.email in ~/.gitconfig not set.')
		email = None
	return (name, email)

    def _get_spec_version_and_release(self):
        """ Get the package version from the spec file. """
        return get_spec_version_and_release(self.full_project_dir,
                self.spec_file_name)

    def _get_new_tag(self, new_version):
        """ Returns the actual tag we'll be creating. """
        suffix = ""
        # If global config specifies a tag suffix, use it:
        if self.config.has_option("globalconfig", "tag_suffix"):
            suffix = self.config.get("globalconfig", "tag_suffix")
        return "%s-%s%s" % (self.project_name, new_version, suffix)


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
        new_version = self._bump_version(release=True)

        self._check_tag_does_not_exist(self._get_new_tag(new_version))
        self._update_changelog(new_version)
        self._update_package_metadata(new_version)

    def release_type(self):
        """ return short string "minor release" """
        return "minor release"
