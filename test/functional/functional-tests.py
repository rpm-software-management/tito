#
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
Functional Tests for Tito at the CLI level.

NOTE: These tests require a makeshift git repository created in /tmp.
"""

import os

import unittest

from tito.common import check_tag_exists, commands, run_command

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_DIR = '/tmp/titotests/'
SINGLE_GIT = os.path.join(TEST_DIR, 'single.git')
#MULTI_GIT = os.path.join(TEST_DIR, 'multi.git')

TEST_PKG_NAME = 'tito-test-pkg'
TEST_SPEC = """
Name:           tito-test-pkg
Version:        0.0.1
Release:        1%{?dist}
Summary:        Tito test package.
URL:            https://example.com
Group:          Applications/Internet
License:        GPLv2
BuildRoot:      %{_tmppath}/%{name}-root-%(%{__id_u} -n)
BuildArch:      noarch

%description
Nobody cares.

%prep
#nothing to do here

%build
#nothing to do here

%install
rm -rf $RPM_BUILD_ROOT

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root)

%changelog
"""

def run_tito(argstring):
    """ Run the tito script from source with given arguments. """
    tito_path = 'tito' # assume it's on PATH by default
    if 'TITO_SRC_BIN_DIR' in os.environ:
        bin_dir = os.environ['TITO_SRC_BIN_DIR']
        tito_path = os.path.join(bin_dir, 'tito')
    (status, output) = commands.getstatusoutput("%s %s" % (tito_path, 
        argstring))
    if status > 0:
        print "Tito command failed, output:"
        print output
        raise Exception()

def cleanup_temp_git():
    """ Delete the test directory if it exists. """
    if os.path.exists(TEST_DIR):
        #error_out("Test Git repo already exists: %s" % TEST_DIR)
        run_command('rm -rf %s' % TEST_DIR)

def create_temp_git(multi_project=False):
    """ 
    Create a test git repository. 
    
    Repository will have a functional spec file for a package named 
    tito-test-pkg, be tito initiliazed and have one 0.0.1-1 tag created.
    This is *ALL* you should count on in these tests.
    """
    cleanup_temp_git()

    run_command('mkdir -p %s' % TEST_DIR)
    run_command('mkdir -p %s' % SINGLE_GIT)
#    run_command('mkdir -p %s' % MULTI_GIT)
    os.chdir(SINGLE_GIT)

    # Write some files to the test git repo:
    filename = os.path.join(SINGLE_GIT, "a.txt")
    out_f = open(filename, 'w')
    out_f.write("BLERG")
    out_f.close()

    # Write the test spec file:
    filename = os.path.join(SINGLE_GIT, "tito-test-pkg.spec")
    out_f = open(filename, 'w')
    out_f.write(TEST_SPEC)
    out_f.close()

    run_command('git init')
    run_command('git add a.txt')
    run_command('git add tito-test-pkg.spec')
    run_command('git commit -a -m "Initial commit."')

def setup_module():
    """ 
    Python Nose will run this once and only once for all tests in this 
    module. 
    """
    create_temp_git()

    os.chdir(SINGLE_GIT)
    run_tito("init")

    run_command('echo "offline = true" >> rel-eng/tito.props')
    run_command('git add rel-eng/tito.props')
    run_command('git commit -m "Setting offline"')

    # Create initial 0.0.1 tag:
    run_tito("tag --keep-version --accept-auto-changelog --debug")

def teardown_module():
    os.chdir('/tmp') # anywhere but the git repo were about to delete
    cleanup_temp_git()


class InitTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)
     
    def test_init(self):
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "tito.props")))


class TaggerTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)

    def test_initial_tag_keep_version(self):
        """ Create an initial package tag with --keep-version. """
        check_tag_exists("%s-0.0.1-1" % TEST_PKG_NAME, offline=True)
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, 
            "rel-eng/packages", TEST_PKG_NAME)))

    def test_initial_tag(self):
        """ Test creating an initial tag. """
        run_tito("tag --accept-auto-changelog --debug")
        check_tag_exists("%s-0.0.2-1" % TEST_PKG_NAME, offline=True)


class BuilderTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)

    def test_latest_tgz(self):
        run_tito("build --tgz")

    def test_tag_tgz(self):
        run_tito("build --tgz --tag=%s-0.0.1-1" % TEST_PKG_NAME)

    def test_latest_srpm(self):
        run_tito("build --srpm")

    def test_tag_srpm(self):
        run_tito("build --srpm --tag=%s-0.0.1-1" % TEST_PKG_NAME)

    def test_latest_rpm(self):
        run_tito("build --rpm")

    def test_tag_rpm(self):
        run_tito("build --rpm --tag=%s-0.0.1-1" % TEST_PKG_NAME)
