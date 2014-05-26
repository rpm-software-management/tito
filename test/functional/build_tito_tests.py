#
# Copyright (c) 2008-2014 Red Hat, Inc.
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
'''
Functional tests to build tito with tito.
This can catch indirect omissions within tito itself.
'''

import os
import shutil
import tempfile
import unittest

from functional.fixture import tito
from glob import glob
from os.path import join


class BuildTitoTests(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        'Run tito build before _all_ tests in this class.'
        self.output_dir = tempfile.mkdtemp("-titotestoutput")
        os.chdir(os.path.abspath(join(__file__, '..', '..', '..')))
        self.artifacts = tito(
            'build --rpm --test --output=%s --offline --no-cleanup --debug' %
            self.output_dir
        )

    @classmethod
    def tearDownClass(self):
        'Clean up after _all_ tests in this class unless any test fails.'
        shutil.rmtree(self.output_dir)

    def test_build_tito(self):
        'Tito creates three artifacts'
        self.assertEqual(3, len(self.artifacts))

    def test_find_srpm(self):
        'One artifact is an SRPM'
        srpms = glob(join(self.output_dir, 'tito-*src.rpm'))
        self.assertEqual(1, len(srpms))

    def test_find_rpm(self):
        'One artifact is a noarch RPM'
        rpms = glob(join(self.output_dir, 'noarch', 'tito-*noarch.rpm'))
        self.assertEqual(1, len(rpms))

    def test_find_tgz(self):
        'One artifact is a tarball'
        tgzs = glob(join(self.output_dir, 'tito-*tar.gz'))
        self.assertEqual(1, len(tgzs))
