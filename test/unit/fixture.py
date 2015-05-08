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
import os
import unittest

from tito.compat import *  # NOQA

UNIT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_DIR = os.path.join(UNIT_DIR, '..', '..')


class TitoUnitTestFixture(unittest.TestCase):
    """
    Fixture providing setup/teardown and utilities for unit tests.
    """
    def setUp(self):
        print
        print
        print("Testing in: %s" % REPO_DIR)
        print
