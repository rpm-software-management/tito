# Copyright (c) 2012-2016 SUSE Linux Products GmbH
# Copyright (c) 2018 Neal Gompa.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
"""
Code for tagging packages in SUSE Style.
"""
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from tito.common import (debug, run_command, get_latest_tagged_version)
from tito.compat import write, StringIO
from tito.tagger import VersionTagger

from time import strftime


class SUSETagger(VersionTagger):
    """
    Tagger which is based on VersionTagger and use SUSE format of Changelog
    and SUSE specific changes file:

    If you want it put in tito.pros (global) or localy in build.py.props:
    [buildconfig]
    tagger = tito.susetagger.SUSETagger
    """

    def __init__(self, config=None, keep_version=False, offline=False, user_config=None):
        VersionTagger.__init__(self, config=config, keep_version=keep_version,
                               offline=offline, user_config=user_config)
        self.today = strftime("%a %b %d %T %Z %Y")
        self.changes_file_name = self.spec_file_name.replace('.spec', '.changes')
        self.changes_file = os.path.join(self.full_project_dir,
                self.changes_file_name)
        self._new_changelog_msg = "Initial package release"
        self.changelog_regex = re.compile('^\s%s\s%s(\s<%s>)?' % (self.today,
            self.git_user, self.git_email.replace("+", "\+").replace(".", "\.")))

    def _make_changelog(self):
        """
        Create a new changelog entry in the changes, with line items from git
        """
        if self._no_auto_changelog:
            debug("Skipping changelog generation.")
            return

        # Attempt to open the file if it exists, but create it if it doesn't
        try:
            in_f = open(self.changes_file, 'r')
        except FileNotFoundError:
            new_in_f = open(self.changes_file, 'w')
            new_in_f.close()
            in_f = open(self.changes_file, 'r')

        out_f = open(self.changes_file + ".new", 'w')

        old_version = get_latest_tagged_version(self.project_name)

        # don't die if this is a new package with no history
        if old_version is not None:
            last_tag = "%s-%s" % (self.project_name, old_version)
            output = self._generate_default_changelog(last_tag)
        else:
            output = self._new_changelog_msg

        fd, name = tempfile.mkstemp()
        write(fd, "# Create your changelog entry below:\n")
        header = "-------------------------------------------------------------------\n"
        if self.git_email is None or (('HIDE_EMAIL' in self.user_config) and
                (self.user_config['HIDE_EMAIL'] not in ['0', ''])):
            header = header + "%s - %s\n\n" % (self.today, self.git_user)
        else:
            header = header + "%s - %s <%s>\n\n" % (self.today, self.git_user,
                                                        self.git_email)

        write(fd, header)

        for cmd_out in output.split("\n"):
            write(fd, "- ")
            write(fd, "\n  ".join(textwrap.wrap(cmd_out, 77)))
            write(fd, "\n")

        write(fd, "\n")

        if not self._accept_auto_changelog:
            write(fd, "###################################################\n")
            write(fd, "# These are the already existing changelog entries:\n")
            write(fd, "###################################################\n")
            for line in in_f.readlines():
                write(fd, "#" + line)
            in_f.seek(0, 0)

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

        for line in in_f.readlines():
            out_f.write(line)

        in_f.close()
        out_f.close()

        shutil.move(self.changes_file + ".new", self.changes_file)

    def _update_changelog(self, new_version):
        """
        Update the changelog with the new version.
        """
        # Not thrilled about having to re-read the file here but we need to
        # check for the changelog entry before making any modifications, then
        # bump the version, then update the changelog.
        f = open(self.changes_file, 'r')
        buf = StringIO()
        found_match = False
        done = False
        empty_line_regex = re.compile('^\s*$')

        for line in f.readlines():
            if not done and not found_match and self.changelog_regex.match(line):
                buf.write(line)
                found_match = True
            elif not done and found_match and empty_line_regex.match(line):
                buf.write("\n- version %s\n" % new_version)
                done = True
            else:
                buf.write(line)
        f.close()

        # Write out the new file contents with our modified changelog entry:
        f = open(self.changes_file, 'w')
        f.write(buf.getvalue())
        f.close()
        buf.close()

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
        if not self._no_auto_changelog:
            run_command("git add %s" % os.path.join(self.full_project_dir,
                self.changes_file_name))

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
        print("   Push: git push origin HEAD && git push origin %s" % new_tag)
        print("or Push: git push origin HEAD && git push origin --tags")
