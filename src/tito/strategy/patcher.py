# Copyright (c) 2008-2010 Red Hat, Inc.
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
Tito strategies for patching upstream projects.
"""

import re
import os.path

from tito.common import (debug, run_command)

class DefaultPatcher(object):
    """
    Default Patcher

    Simple generates a single patch by diffing the upstream git tag with the 
    tag being build.
    """

    def __init__(self, builder):
        self.builder = builder

    def run(self):
        patch_filename = "%s-to-%s-%s.patch" % (self.builder.upstream_tag,
                self.builder.project_name, self.builder.build_version)
        patch_file = os.path.join(self.builder.rpmbuild_gitcopy,
                patch_filename)
        patch_dir = self.builder.git_root
        if self.builder.relative_project_dir != "/":
            patch_dir = os.path.join(self.builder.git_root, 
                    self.builder.relative_project_dir)
        os.chdir(patch_dir)
        debug("patch dir = %s" % patch_dir)
        print("Generating patch [%s]" % patch_filename)
        debug("Patch: %s" % patch_file)
        patch_command = "git diff --relative %s..%s > %s" % \
                (self.builder.upstream_tag, self.builder.git_commit_id, 
                        patch_file)
        debug("Generating patch with: %s" % patch_command)
        output = run_command(patch_command)
        print(output)
        # Creating two copies of the patch here in the temp build directories
        # just out of laziness. Some builders need sources in SOURCES and
        # others need them in the git copy. Being lazy here avoids one-off
        # hacks and both copies get cleaned up anyhow.
        run_command("cp %s %s" % (patch_file, self.builder.rpmbuild_sourcedir))

        # Insert patches into the spec file we'll be building:
        f = open(self.builder.spec_file, 'r')
        lines = f.readlines()

        patch_pattern = re.compile('^Patch(\d+):')
        source_pattern = re.compile('^Source\d+:')

        # Find the largest PatchX: line, or failing that SourceX:
        patch_number = 0 # What number should we use for our PatchX line
        patch_insert_index = 0 # Where to insert our PatchX line in the list
        patch_apply_index = 0 # Where to insert our %patchX line in the list
        array_index = 0 # Current index in the array
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
                patch_apply_index = array_index + 2 # already added a line

            array_index += 1

        debug("patch_insert_index = %s" % patch_insert_index)
        debug("patch_apply_index = %s" % patch_apply_index)
        if patch_insert_index == 0 or patch_apply_index == 0:
            error_out("Unable to insert PatchX or %patchX lines in spec file")

        lines.insert(patch_insert_index, "Patch%s: %s\n" % (patch_number,
            patch_filename))
        lines.insert(patch_apply_index, "%%patch%s -p1\n" % (patch_number))
        f.close()

        # Now write out the modified lines to the spec file copy:
        f = open(self.builder.spec_file, 'w')
        for line in lines:
            f.write(line)
        f.close()




