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

""" Pure unit tests for tito's common module. """

from tito.common import *

import unittest

class CommonTests(unittest.TestCase):

    def test_normalize_class_name(self):
        """ Test old spacewalk.releng namespace is converted to tito. """
        self.assertEquals("tito.builder.Builder", 
                normalize_class_name("tito.builder.Builder"))
        self.assertEquals("tito.builder.Builder", 
                normalize_class_name("spacewalk.releng.builder.Builder"))
        self.assertEquals("tito.tagger.VersionTagger", 
                normalize_class_name("spacewalk.releng.tagger.VersionTagger"))

