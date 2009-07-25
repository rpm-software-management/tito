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
Executes all tests.
"""

import sys
import os
import os.path

import unittest

# Make sure we run from the source, this is tricky because the functional
# tests need to find both the location of the 'tito' executable script,
# and the internal tito code needs to know where to find our auxiliary Perl
# scripts. Adding an environment variable hack to the actual code to 
# accommodate this for now.

TEST_SCRIPT_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
SRC_DIR = os.path.normpath(os.path.join(TEST_SCRIPT_DIR, "src/"))
SRC_BIN_DIR = os.path.abspath(os.path.join(TEST_SCRIPT_DIR, "bin/"))

os.environ['TITO_SRC_DIR'] = SRC_DIR
os.environ['TITO_SRC_BIN_DIR'] = SRC_BIN_DIR

if __name__ == '__main__':
    print("Running tito tests.")

    import nose
    nose.main()

