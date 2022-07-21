#!/usr/bin/env python
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
Tito Setup Script
"""

from io import open
from setuptools import setup, find_packages


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="tito",
    version='0.6.21',
    description='A tool for managing rpm based git projects.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='rpm-software-management',
    url='https://github.com/rpm-software-management/tito',
    license='GPLv2+',

    # tell distutils packages are under src directory
    package_dir={
        '': 'src',
    },
    packages=find_packages('src'),
    include_package_data=True,
    install_requires=[
        'blessed'
    ],

    # automatically create console scripts
    entry_points={
        'console_scripts': [
            'tito = tito.cli:main',
        ],
    },

    # non-python scripts go here
    scripts=[
        'bin/generate-patches.pl'
    ],

    classifiers=[
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Programming Language :: Python'
    ],
)


# XXX: this will also print on non-install targets
print("tito target is complete")
