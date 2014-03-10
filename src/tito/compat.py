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
"""
Compatibility library for Python 2.4 up through Python 3.
"""
import sys
PY2 = sys.version_info[0] == 2
if PY2:
    import commands
    from ConfigParser import ConfigParser
    from ConfigParser import NoOptionError
    from ConfigParser import RawConfigParser
else:
    import subprocess
    from configparser import ConfigParser
    from configparser import NoOptionError
    from configparser import RawConfigParser


def getstatusoutput(cmd):
    """
    Returns (status, output) of executing cmd in a shell.
    Supports Python 2.4 and 3.x.
    """
    if PY2:
        return commands.getstatusoutput(cmd)
    else:
        return subprocess.getstatusoutput(cmd)


def getoutput(cmd):
    """
    Returns output of executing cmd in a shell.
    Supports Python 2.4 and 3.x.
    """
    return getstatusoutput(cmd)[1]
