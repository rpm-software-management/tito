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

# flake8: noqa

"""
Compatibility library for Python 2.4 up through Python 3.
"""
import os
import sys
ENCODING = sys.getdefaultencoding()
PY2 = sys.version_info[0] == 2
if PY2:
    import commands
    from ConfigParser import NoOptionError
    from ConfigParser import RawConfigParser
    from StringIO import StringIO
    import xmlrpclib
else:
    import subprocess
    from configparser import NoOptionError
    from configparser import RawConfigParser
    from io import StringIO
    import xmlrpc.client as xmlrpclib


def decode_bytes(x, source_encoding):
    if PY2:
        return x
    else:
        return x.decode(source_encoding)


def encode_bytes(x, destination_encoding):
    if PY2:
        return x
    else:
        return bytes(x, destination_encoding)


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


def dictionary_override(d1, d2):
    """
    Return a new dictionary object where
    d2 elements override d1 elements.
    """
    if PY2:
        overrides = d1.items() + d2.items()
    else:
        overrides = list(d1.items()) + list(d2.items())
    return dict(overrides)


def write(fd, str):
    """
    A version of os.write that
    supports Python 2.4 and 3.x.
    """
    if PY2:
        os.write(fd, str)
    else:
        os.write(fd, bytes(str, ENCODING))
