import os
import tempfile
import unittest

from tito.cli import CLI
from tito.common import run_command
from tito.compat import getoutput

TEST_SPEC = """
Name:           hello_tito
Version:        0.1.7
Release:        1%{?dist}
Summary:        testing package

License:        Public Domain
Source0:        hello_tito-%{version}.tar.gz

%description


%prep
%autosetup


%build

%install

%files

%changelog
"""


def tito(argstring):
    """ Run Tito from source with given arguments. """
    return CLI().main(argstring.split(' '))


class VersionTaggerTest(unittest.TestCase):
    """
    Test 'VersionTagger' class.
    """

    def setUp(self):
        self.repo_dir = tempfile.mkdtemp("-titouserspecifiedtag")
        print("Testing in: %s" % self.repo_dir)
        os.chdir(self.repo_dir)

        self.full_pkg_dir = os.path.join(self.repo_dir, "hello_tito")
        run_command('mkdir -p %s' % self.full_pkg_dir)

        # Initialize the repo:
        os.chdir(self.full_pkg_dir)
        run_command('git init')

        # Next we tito init:
        tito("init")
        run_command('sed -i "s;tagger.*;tagger = tito.tagger.VersionTagger;g" .tito/tito.props')
        run_command('echo "offline = true" >> .tito/tito.props')
        run_command('echo "tag_format = {component}-v{version}" >> .tito/tito.props')
        run_command('git add .tito/tito.props')
        run_command("git commit -m 'set offline in tito.props'")

        # Init RPM package
        self.create_rpm_package()

        # Run tito release
        tito("tag release --accept-auto-changelog")

    def write_file(self, path, contents):
        out_f = open(path, 'w')
        out_f.write(contents)
        out_f.close()

    def create_rpm_package(self):
        os.chdir(self.full_pkg_dir)
        self.write_file(os.path.join(self.full_pkg_dir, 'hello_tito.spec'), TEST_SPEC)
        run_command('git add hello_tito.spec')
        run_command("git commit -m 'add spec file'")

    def test_tag(self):
        """
        Check that the tag is correct
        """
        latest_tag = getoutput("git describe --abbrev=0 --tags")
        assert latest_tag == 'hello_tito-v0.1.8'
