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
Functional Tests for Tito's Tagger Module

NOTE: These tests require a makeshift git repository created in /tmp.
"""

import sys
import os
import os.path

import unittest

import tito.cli # prevents a circular import
from tito.common import *

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_DIR = '/tmp/titotests/'
SINGLE_GIT = os.path.join(TEST_DIR, 'single.git')
#MULTI_GIT = os.path.join(TEST_DIR, 'multi.git')

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

def tito(argstring):
    """ Run the tito script from source with given arguments. """
    bin_dir = os.environ['TITO_SRC_BIN_DIR']
    run_command("%s %s" % (os.path.join(bin_dir, 'tito'), argstring))

def cleanup_test_git_repos():
    """ Delete the test directory if it exists. """
    if os.path.exists(TEST_DIR):
        #error_out("Test Git repo already exists: %s" % TEST_DIR)
        run_command('rm -rf %s' % TEST_DIR)

def create_test_git_repo(multi_project=False):
    """ Create a test git repository. """
    cleanup_test_git_repos()

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


class TaggerTests(unittest.TestCase):

    def setUp(self):
        create_test_git_repo()

        # Probably already there but just to make sure:
        os.chdir(SINGLE_GIT)
        self.assertFalse(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        tito("init")
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "packages")))
        self.assertTrue(os.path.exists(os.path.join(SINGLE_GIT, "rel-eng",
            "tito.props")))

    def tearDown(self):
        os.chdir('/tmp') # anywhere but the git repo were about to delete
        cleanup_test_git_repos()

    def test_tag_new_package(self):
        #tito("tag")
        pass


