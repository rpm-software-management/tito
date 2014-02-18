#
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

import os
import unittest

import git
import tempfile

from tito.cli import CLI
from tito.common import run_command

# NOTE: No Name in test spec file as we re-use it for several packages.
# Name must be written first.
TEST_SPEC = """
%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Version:        0.0.1
Release:        1%{?dist}
Summary:        Tito test package.
URL:            https://example.com
Group:          Applications/Internet
License:        GPLv2
BuildRoot:      %{_tmppath}/%{name}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python-devel
BuildRequires:  python-setuptools
Source0:        %{name}-%{version}.tar.gz

%description
Nobody cares.

%prep
#nothing to do here
%setup -q -n %{name}-%{version}

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT
rm -f $RPM_BUILD_ROOT%{python_sitelib}/*egg-info/requires.txt

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root)
#%dir %{python_sitelib}/%{name}
%{python_sitelib}/%{name}-*.egg-info

%changelog
"""

TEST_SETUP_PY = """
from setuptools import setup, find_packages

setup(
    name="%s",
    version='1.0',
    description='tito test project',
    author='Nobody Knows',
    author_email='tito@example.com',
    url='http://rm-rf.ca/tito',
    license='GPLv2+',

    package_dir={
        '%s': 'src/',
    },
    packages = find_packages('src'),
    include_package_data = True,

    classifiers = [
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Programming Language :: Python'
    ],
)
"""

TEST_PYTHON_SRC = """
class Empty(object):
    pass
"""


def tito(argstring):
    """ Run Tito from source with given arguments. """
    return CLI().main(argstring.split(' '))


class TitoGitTestFixture(unittest.TestCase):
    """
    Fixture providing setup/teardown and utilities for all tests requiring
    an actual git repository.
    """
    def setUp(self):
        # Create a temporary directory for our test git repository:
        self.repo_dir = tempfile.mkdtemp("-titotest")
        print
        print
        print("Testing in: %s" % self.repo_dir)
        print

        # GitPython calls os.login(), which throws OSError if there is no tty,
        # but GitPython allows to avoid the call if env var USER exists.
        try:
            os.getlogin()
        except OSError:
            os.environ['USER'] = 'nobody'

        # Initialize the repo:
        self.repo = git.Repo.init(path=self.repo_dir, mkdir=True, bare=False)

        # Next we tito init:
        os.chdir(self.repo_dir)
        tito("init")
        run_command('echo "offline = true" >> rel-eng/tito.props')
        index = self.repo.index
        index.add(['rel-eng/tito.props'])
        index.commit('Setting offline.')

    def write_file(self, path, contents):
        print path
        out_f = open(path, 'w')
        out_f.write(contents)
        out_f.close()

    def create_project(self, pkg_name, pkg_dir=''):
        """
        Create a test project at the given location, assumed to be within
        our test repo, but possibly within a sub-directory.
        """
        full_pkg_dir = os.path.join(self.repo_dir, pkg_dir)
        run_command('mkdir -p %s' % full_pkg_dir)
        os.chdir(full_pkg_dir)

        # TODO: Test project needs work, doesn't work in some scenarios
        # like UpstreamBuilder:
        filename = os.path.join(full_pkg_dir, "a.txt")
        out_f = open(filename, 'w')
        out_f.write("BLERG\n")
        out_f.close()

        # Write the test spec file:
        filename = os.path.join(full_pkg_dir, "%s.spec" % pkg_name)
        out_f = open(filename, 'w')
        out_f.write("Name: %s" % pkg_name)
        out_f.write(TEST_SPEC)
        out_f.close()

        # Write test setup.py:
        filename = os.path.join(full_pkg_dir, "setup.py")
        out_f = open(filename, 'w')
        out_f.write(TEST_SETUP_PY % (pkg_name, pkg_name))
        out_f.close()

        # Write test source:
        run_command('mkdir -p %s' % os.path.join(full_pkg_dir, "src"))
        filename = os.path.join(full_pkg_dir, "src", "module.py")
        out_f = open(filename, 'w')
        out_f.write(TEST_PYTHON_SRC)
        out_f.close()

        index = self.repo.index
        files = [os.path.join(pkg_dir, 'a.txt'),
                os.path.join(pkg_dir, 'setup.py'),
                os.path.join(pkg_dir, '%s.spec' % pkg_name),
                os.path.join(pkg_dir, 'src/module.py')
        ]
        index.add(files)
        index.commit('Initial commit.')

        tito('tag --keep-version --debug --accept-auto-changelog')
