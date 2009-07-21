#!/usr/bin/python

""" Tito Distutils Setup Script """

import os

from distutils.core import setup


setup(name="tito",
    version='1.0',
    description='A tool for managing rpm based git projects.',
    author='Devan Goodwin',
    author_email='dgoodwin@rm-rf.ca',
    url='http://rm-rf.ca/tito',
    license='GPL',
    packages=[
        'spacewalk',
        'spacewalk.releng',
    ],
    package_dir={
        'spacewalk': 'src/spacewalk',
        'spacewalk.releng': 'src/spacewalk/releng',
    },
    scripts=['bin/tito', 'bin/bump-version.pl', 'bin/tar-fixup-stamp-comment.pl',       'bin/test-setup-specfile.pl'],
)

print "tito installation complete"
