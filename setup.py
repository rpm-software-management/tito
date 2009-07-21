#!/usr/bin/env python
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
Tito Distutils Setup Script
"""

import os

from setuptools import setup, find_packages


setup(
    name="tito",
    version='1.0',
    description='A tool for managing rpm based git projects.',
    author='Devan Goodwin',
    author_email='dgoodwin@rm-rf.ca',
    url='http://rm-rf.ca/tito',
    license='GPLv2+',

    package_dir={
        'spacewalk': 'src/spacewalk',
        'spacewalk.releng': 'src/spacewalk/releng',
    },
    packages = find_packages('src'),
    include_package_data = True,

    # non-python scripts go here
    scripts = [
        'bin/bump-version.pl',
        'bin/tar-fixup-stamp-comment.pl',
        'bin/test-setup-specfile.pl',
    ],

    entry_points = {
        'console_scripts':
            ['tito = spacewalk.releng.cli:main'],
    },

    classifiers = [
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Programming Language :: Python'
    ],
)


# XXX: this will also print on non-install targets
print("tito target is complete")
