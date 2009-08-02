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

from tito.common import check_tag_exists, commands, run_command, \
        get_latest_tagged_version


# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_DIR = '/tmp/titotests/'
SINGLE_GIT = os.path.join(TEST_DIR, 'single.git')
MULTI_GIT = os.path.join(TEST_DIR, 'multi.git')

TEST_PKG_1 = 'tito-test-pkg'
TEST_PKG_1_DIR = "%s/" % TEST_PKG_1

TEST_PKG_2 = 'tito-test-pkg2'
TEST_PKG_2_DIR = "%s/" % TEST_PKG_2

TEST_PKG_3 = 'tito-test-pkg3'
TEST_PKG_3_DIR = "blah/whatever/%s/" % TEST_PKG_3

TEST_PKGS = [
        (TEST_PKG_1, TEST_PKG_1_DIR),
        (TEST_PKG_2, TEST_PKG_2_DIR),
        (TEST_PKG_3, TEST_PKG_3_DIR)
]

# NOTE: No Name in test spec file as we re-use it for several packages.
# Name must be written first.
TEST_SPEC = """
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
    tito_cmd = "%s %s" % (tito_path, argstring)
    print("Running: %s" % tito_cmd)
    (status, output) = commands.getstatusoutput(tito_cmd)
    print output
    if status > 0:
        print "Tito command failed, output:"
        raise Exception()

def cleanup_temp_git():
    """ Delete the test directory if it exists. """
    if os.path.exists(TEST_DIR):
        #error_out("Test Git repo already exists: %s" % TEST_DIR)
        run_command('rm -rf %s' % TEST_DIR)

def create_single_project_git():
    """ 
    Create a test git repository with a single project, tito init, and create
    an initial package tag.
    
    Repository will have a functional spec file for a package named 
    tito-test-pkg, be tito initiliazed and have one 0.0.1-1 tag created.
    This is *ALL* you should count on in these tests.
    """

    run_command('mkdir -p %s' % TEST_DIR)
    run_command('mkdir -p %s' % SINGLE_GIT)
    os.chdir(SINGLE_GIT)
    run_command('git init')
    run_tito("init")
    run_command('echo "offline = true" >> rel-eng/tito.props')
    run_command('git add rel-eng/tito.props')
    run_command('git commit -m "Setting offline"')

    create_git_project(SINGLE_GIT, TEST_PKG_1)

def create_multi_project_git():
    """ 
    Create a test git repository with multiple projects, tito init, and
    create initial tags for each package.
    
    Repository will have a functional spec file for a package named 
    tito-test-pkg, be tito initiliazed and have one 0.0.1-1 tag created.
    This is *ALL* you should count on in these tests.
    """

    run_command('mkdir -p %s' % TEST_DIR)
    run_command('mkdir -p %s' % MULTI_GIT)
    os.chdir(MULTI_GIT)
    run_command('git init')
    run_tito("init")
    run_command('echo "offline = true" >> rel-eng/tito.props')
    run_command('git add rel-eng/tito.props')
    run_command('git commit -m "Setting offline"')

    for pkg_name, pkg_dir in TEST_PKGS:
        full_pkg_dir = os.path.join(MULTI_GIT, pkg_dir)
        create_git_project(full_pkg_dir, pkg_name)

    # For second test package, use a tito.props to override and use the 
    # ReleaseTagger:
    os.chdir(os.path.join(MULTI_GIT, TEST_PKG_2_DIR))
    filename = os.path.join(MULTI_GIT, TEST_PKG_2_DIR, "tito.props")
    out_f = open(filename, 'w')
    out_f.write("[buildconfig]\n")
    out_f.write("tagger = tito.tagger.ReleaseTagger\n")
    out_f.write("builder = tito.builder.Builder\n")
    out_f.close()
    run_command("git add tito.props")
    run_command('git commit -m "Adding tito.props."')

def create_git_project(full_pkg_dir, pkg_name):
    """
    Write out test files for a git project at the specified location and 
    commit them.
    """
    run_command('mkdir -p %s' % full_pkg_dir)
    os.chdir(full_pkg_dir)

    # Write some files to the test git repo:
    filename = os.path.join(full_pkg_dir, "a.txt")
    out_f = open(filename, 'w')
    out_f.write("BLERG")
    out_f.close()

    # Write the test spec file:
    filename = os.path.join(full_pkg_dir, "%s.spec" % pkg_name)
    out_f = open(filename, 'w')
    out_f.write("Name: %s" % pkg_name)
    out_f.write(TEST_SPEC)
    out_f.close()

    run_command('git add a.txt')
    run_command('git add %s.spec' % pkg_name)
    run_command('git commit -a -m "Initial commit for %s."' % pkg_name)

    # Create initial 0.0.1 tag:
    run_tito("tag --keep-version --accept-auto-changelog --debug")

def release_bumped(initial_version, new_version):
    first_release = initial_version.split('-')[-1]
    new_release = new_version.split('-')[-1]
    return new_release == str(int(first_release) + 1)

def setup_module():
    """ 
    Python Nose will run this once and only once for all tests in this 
    module. 
    """
    cleanup_temp_git()
    create_single_project_git()
    create_multi_project_git()

    os.chdir(SINGLE_GIT)

def teardown_module():
    os.chdir('/tmp') # anywhere but the git repo were about to delete
    #cleanup_temp_git()


class InitTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)
     
    def test_init(self):
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "tito.props")))


class SingleProjectTaggerTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)

    def test_initial_tag_keep_version(self):
        """ Create an initial package tag with --keep-version. """
        check_tag_exists("%s-0.0.1-1" % TEST_PKG_1, offline=True)
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, 
            "rel-eng/packages", TEST_PKG_1)))

    def test_initial_tag(self):
        """ Test creating an initial tag. """
        run_tito("tag --accept-auto-changelog --debug")
        check_tag_exists("%s-0.0.2-1" % TEST_PKG_1, offline=True)


class MultiProjectTaggerTests(unittest.TestCase):

    def setUp(self):
        os.chdir(MULTI_GIT)

    def test_initial_tag_keep_version(self):
        # Tags were actually created in setup code:
        for pkg_name, pkg_dir in TEST_PKGS:
            check_tag_exists("%s-0.0.1-1" % pkg_name, offline=True)
            self.assertTrue(os.path.exists(os.path.join(MULTI_GIT, 
                "rel-eng/packages", pkg_name)))

    def test_release_tagger(self):
        os.chdir(os.path.join(MULTI_GIT, TEST_PKG_2_DIR))
        start_ver = get_latest_tagged_version(TEST_PKG_2)
        run_tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertTrue(release_bumped(start_ver, new_ver))

    def test_release_tagger_legacy_props_file(self):
        # Test that build.py.props filename is still picked up:
        os.chdir(os.path.join(MULTI_GIT, TEST_PKG_2_DIR))
        start_ver = get_latest_tagged_version(TEST_PKG_2)

        run_command("git mv tito.props build.py.props")
        run_command('git commit -a -m "Rename to build.py.props"')

        run_tito('tag --debug --accept-auto-changelog')
        new_ver = get_latest_tagged_version(TEST_PKG_2)
        self.assertTrue(release_bumped(start_ver, new_ver))


class SingleProjectBuilderTests(unittest.TestCase):

    def setUp(self):
        os.chdir(SINGLE_GIT)

    def test_latest_tgz(self):
        run_tito("build --tgz -o %s" % SINGLE_GIT)

    def test_tag_tgz(self):
        run_tito("build --tgz --tag=%s-0.0.1-1 -o %s" % (TEST_PKG_1,
            SINGLE_GIT))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, 
            "%s-0.0.1.tar.gz" % TEST_PKG_1)))

    def test_latest_srpm(self):
        run_tito("build --srpm")

    def test_tag_srpm(self):
        run_tito("build --srpm --tag=%s-0.0.1-1 -o SINGLE_GIT" % TEST_PKG_1)

    def test_latest_rpm(self):
        run_tito("build --rpm -o %s" % SINGLE_GIT)

    def test_tag_rpm(self):
        run_tito("build --rpm --tag=%s-0.0.1-1 -o %s" % (TEST_PKG_1, 
            SINGLE_GIT))
