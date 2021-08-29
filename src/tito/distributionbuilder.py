import os

from tito.builder import UpstreamBuilder
from tito.common import debug, run_command, error_out
from tito.compat import getstatusoutput


class DistributionBuilder(UpstreamBuilder):
    """ This class is used for building packages for distributions.
    Parent class UpstreamBuilder build one big patch from upstream and create e.g.:
      Patch0: foo-1.2.13-1-to-foo-1.2.13-3-sat.patch
    This class create one patch per each release. E.g.:
      Patch0: foo-1.2.13-1-to-foo-1.2.13-2-sat.patch
      Patch1: foo-1.2.13-2-to-foo-1.2.13-3-sat.patch
    """
    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None, args=None, **kwargs):
        UpstreamBuilder.__init__(self, name, tag, build_dir, config,
                user_config, args, **kwargs)
        self.patch_files = []

    def patch_upstream(self):
        """ Create one patch per each release """
        ch_dir = self.git_root
        if self.relative_project_dir != "/":
            ch_dir = os.path.join(self.git_root,
                    self.relative_project_dir)
        os.chdir(ch_dir)
        debug("Running generate-patches.pl -d %s %s %s-1 %s %s"
               % (self.rpmbuild_gitcopy, self.project_name, self.upstream_version, self.build_version, self.git_commit_id))
        output = run_command("generate-patches.pl -d %s %s %s-1 %s %s"
               % (self.rpmbuild_gitcopy, self.project_name, self.upstream_version, self.build_version, self.git_commit_id))
        self.patch_files = output.split("\n")
        for p_file in self.patch_files:
            (status, output) = getstatusoutput(
                "grep 'Binary files .* differ' %s/%s " % (self.rpmbuild_gitcopy, p_file))
            if status == 0 and output != "":
                print(output)
                error_out("You are doomed. Diff contains binary files. You can not use this builder")

            run_command("cp %s/%s %s" % (self.rpmbuild_gitcopy, p_file, self.rpmbuild_sourcedir))

        (patch_number, patch_insert_index, patch_apply_index, lines) = self._patch_upstream()

        for patch in self.patch_files:
            lines.insert(patch_insert_index, "Patch%s: %s\n" % (patch_number, patch))
            lines.insert(patch_apply_index, "%%patch%s -p1\n" % (patch_number))
            patch_number += 1
            patch_insert_index += 1
            patch_apply_index += 2
        self._write_spec(lines)
