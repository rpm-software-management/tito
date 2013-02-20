# Copyright (c) 2008-2011 Red Hat, Inc.
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
Shared code for builder and tagger class
"""

import os
from tito.common import find_git_root

class ConfigObject(object):
    """
    Perent class for Builder and Tagger with shared code
    """

    def __init__(self, pkg_config=None, global_config=None):
        """
        pkg_config - Package specific configuration.

        global_config - Global configuration from rel-eng/tito.props.
        """
        self.config = global_config
        
        # Override global configurations using local configurations
        for section in pkg_config.sections():
            for options in pkg_config.options(section):
                if not self.config.has_section(section):
                    self.config.add_section(section)
                self.config.set(section, options,
                        pkg_config.get(section, options))

        self.git_root = find_git_root()
        self.rel_eng_dir = os.path.join(self.git_root, "rel-eng")

