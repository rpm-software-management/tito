import os.path
import subprocess
import shutil

from tito.common import run_command, info_out, error_out, debug
from tito.release import Releaser

class LocalYumRepoReleaser(Releaser):
    """
    A releaser which will build the desired packages, copy them to a local
    Yum repository, and update the repodata.

    WARNING: This will not work in all situations, depending on the current OS,
    and other factors.
    """
    REQUIRED_CONFIG = ['repo_root_dir', 'builder', 'srpm_disttag' ]

    # Architecture mappings. Do not include the noarch or source pseudo-architectures.
    arch_map = {
        'i686' : 'i386',
        'amd64' : 'x86_64'
    }

    # Default list of file extensions to copy
    filetypes = [ 'rpm', 'srpm' ]

    # Default list of compiled architectures supported
    arches = [ 'i386', 'x86_64' ]

    # Default name of directory into which the compiled packages are to be placed.
    arch_packages_dir = 'Packages'

    # Default name of the directory for the source repo
    src_arch_dir    = 'Sources'

    # Default name of the directory into which source RPMs are placed
    src_packages_dir = 'SPackages'

    def __init__(self, name=None, tag=None, build_dir=None,
            config=None, user_config=None,
            target=None, releaser_config=None, no_cleanup=False,
            test=False, auto_accept=False, **kwargs):

        Releaser.__init__(self, name, tag, build_dir, config,
                user_config, target, releaser_config, no_cleanup, test,
                auto_accept, **kwargs)

        self.build_dir = build_dir

    def release(self, dry_run=False, no_build=False, scratch=False):
        """
        Do the actual post-build release process, which for this releaser involves:

        - Copy the files from the temporary build directory to the corresponding
          architecture directory in the repository.
        - Do any linking of noarch packages, if necessary, into the other
          architecture directories.
        - Run the specified createrepo command

        """

        self.dry_run = dry_run

        # Should this run?
        self.builder.no_cleanup = self.no_cleanup
        self.builder.tgz()

        # Check if the releaser specifies a srpm disttag:
        srpm_disttag = None
        if self.releaser_config.has_option(self.target, "srpm_disttag"):
            srpm_disttag = self.releaser_config.get(self.target, "srpm_disttag")
        self.builder.srpm(dist=srpm_disttag)

        # Check if the releaser specifies a repo root directory:
        repo_root_dir = None
        if self.releaser_config.has_option(self.target, "repo_root_dir"):
            repo_root_dir = self.releaser_config.get(self.target, "repo_root_dir")

        self.builder.rpm()
        self.builder.cleanup()

        self.copy_files_to_repo(repo_root_dir)
        self.process_packages(repo_root_dir)

    def copy_files_to_repo(self, repo_root_dir):
        """
        Copy the files which have been built to their respective directories in
        the Yum repository.

        The destination directory is determined by architecture of the resulting
        RPM, with provisions being made for mapping one architecture extention
        to another (e.g. '.i686.rpm' extension to the 'i386' architecture
        directory).  If the produced file is a '.noarch.rpm', it is copied to
        the noarch directory.
        """

        os.chdir(repo_root_dir)

        # overwrite default self.filetypes if filetypes option is specified in config
        if self.releaser_config.has_option(self.target, 'filetypes'):
            self.filetypes = self.releaser_config.get(self.target, 'filetypes').split(" ")

        for artifact in self.builder.artifacts:
            artifact_arch = self.src_arch_dir
            packages_subdir = self.src_packages_dir
            if artifact.endswith('.tar.gz'):
                artifact_type = 'tgz'
            elif artifact.endswith('src.rpm'):
                artifact_type = 'srpm'
            elif artifact.endswith('.rpm'):
                artifact_type = 'rpm'
                artifact_arch = artifact.split('.')[-2]
                if artifact_arch in self.arch_map and artifact_arch != 'noarch':
                    artifact_arch = self.arch_map[artifact_arch]
                packages_subdir = self.arch_packages_dir
            else:
                continue

            if artifact_type in self.filetypes:
                dest_dir = os.path.join(*(artifact_arch, packages_subdir))
                print("copy: %s > %s" % (artifact, dest_dir))
                shutil.copy(artifact, dest_dir)

    def process_packages(self, repo_root_dir):
        """
        no-op. This will be overloaded by a subclass if needed.
        """
        pass

    def cleanup(self):
        """
        No-op, we clean up during self.release()
        """
        pass
