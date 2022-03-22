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
import contextlib
ENCODING = sys.getdefaultencoding()
PY2 = sys.version_info[0] == 2
if PY2:
    import commands
    from ConfigParser import NoOptionError
    from ConfigParser import RawConfigParser
    from StringIO import StringIO
    from urlparse import urlparse
    from urlparse import urlretrieve
    import xmlrpclib
    text_type = unicode
    binary_type = str
else:
    import subprocess
    from configparser import NoOptionError
    from configparser import RawConfigParser
    from io import StringIO
    from urllib.parse import urlparse
    from urllib.request import urlretrieve
    from contextlib import redirect_stdout
    import xmlrpc.client as xmlrpclib
    text_type = str
    binary_type = bytes


def ensure_text(x, encoding="utf8"):
    if isinstance(x, binary_type):
        return x.decode(encoding)
    elif isinstance(x, text_type):
        return x
    else:
        raise TypeError("Not expecting type '%s'" % type(x))


def ensure_binary(x, encoding="utf8"):
    if isinstance(x, text_type):
        return x.encode(encoding)
    elif isinstance(x, binary_type):
        return x
    else:
        raise TypeError("Not expecting type '%s'" % type(x))


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


if PY2:
    @contextlib.contextmanager
    def redirect_stdout(target):
        original = sys.stdout
        try:
            sys.stdout = target
            yield
        finally:
            sys.stdout = original
