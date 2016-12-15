import os
import re
import tempfile
import unittest

from tito.cli import CLI
from tito.common import run_command
from tito.compat import getoutput

TEST_CARGO_TOML = """
[package]
name = "testing_pkg"
version = "0.0.1"
authors = ["Nobody <test@tito.com>"]

[dependencies]
"""

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


class CargoTagTest(unittest.TestCase):
    """
    Test 'CargoBump' class.
    """

    def setUp(self):
        self.repo_dir = tempfile.mkdtemp("-titocargotest")
        print("Testing in: %s" % self.repo_dir)
        os.chdir(self.repo_dir)

        self.full_pkg_dir = os.path.join(self.repo_dir, "hello_tito")
        run_command('mkdir -p %s' % self.full_pkg_dir)

        # Initialize the repo:
        os.chdir(self.full_pkg_dir)
        run_command('git init')

        # Next we tito init:
        tito("init")
        run_command('echo "offline = true" >> .tito/tito.props')
        run_command('git add .tito/tito.props')
        run_command("git commit -m 'set offline in tito.props'")

        # Init cargo project
        self.create_cargo_project()

        # Init RPM package
        self.create_rpm_package()

        # Run tito tag
        tito("tag --accept-auto-changelog")

    def write_file(self, path, contents):
        out_f = open(path, 'w')
        out_f.write(contents)
        out_f.close()

    def create_cargo_project(self):
        os.chdir(self.full_pkg_dir)
        self.write_file(os.path.join(self.full_pkg_dir, 'Cargo.toml'), TEST_CARGO_TOML)
        run_command('git add Cargo.toml')
        run_command("git commit -m 'add Cargo.toml'")

    def create_rpm_package(self):
        os.chdir(self.full_pkg_dir)
        self.write_file(os.path.join(self.full_pkg_dir, 'hello_tito.spec'), TEST_SPEC)
        run_command('git add hello_tito.spec')
        run_command("git commit -m 'add spec file'")

    def test_cargo_toml_tag(self):
        """
        Check that the version string in Cargo.toml file is the same as in spec file
        """
        changelog = getoutput("grep version Cargo.toml")
        re_version = re.compile(r'"(\d+\.\d+\.\d+)"')
        version = re_version.findall(changelog)
        assert version[0] == "0.1.8"

    def test_git_contains_cargo(self):
        """
        Check presence of the Cargo.toml file in the last commit (tag)
        """
        diff = getoutput("git diff HEAD^ -- Cargo.toml")
        assert diff.find("-version = \"0.0.1\"") != -1
        assert diff.find("+version = \"0.1.8\"") != -1
