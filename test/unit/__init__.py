# Copyright (c) 2008-2015 Red Hat, Inc.
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

import sys

from contextlib import contextmanager
from mock import patch, MagicMock
from tito.compat import PY2, StringIO


# There is not many simple options to check on what distribution this is running.
# Fortunately, we only need to check for Fedora Rawhide and EPEL6, so we can
# determine it from python version. This is compatible for all distributions.
is_rawhide = sys.version_info[:2] >= (3, 8)
is_epel6 = sys.version_info[:2] == (2, 6)


if PY2:
    builtins = "__builtin__"
    builtins_open = "__builtin__.open"
    builtins_input = "__builtin__.raw_input"
else:
    builtins = "builtins"
    builtins_open = "builtins.open"
    builtins_input = "builtins.input"


file_spec = None


class Capture(object):
    class Tee(object):
        def __init__(self, stream, silent):
            self.buf = StringIO()
            self.stream = stream
            self.silent = silent

        def write(self, data):
            self.buf.write(data)
            if not self.silent:
                self.stream.write(data)

        def getvalue(self):
            return self.buf.getvalue()

        def isatty(self):
            return False

    def __init__(self, silent=False):
        self.silent = silent

    def __enter__(self):
        self.buffs = (self.Tee(sys.stdout, self.silent), self.Tee(sys.stderr, self.silent))
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        sys.stdout, sys.stderr = self.buffs
        return self

    @property
    def out(self):
        return self.buffs[0].getvalue()

    @property
    def err(self):
        return self.buffs[1].getvalue()

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self.stdout
        sys.stderr = self.stderr


@contextmanager
def open_mock(content, **kwargs):
    """Mock's mock_open only supports read() and write() which is not very useful.
    This context manager adds support for getting the value of what was written out
    and for iterating through a file line by line."""

    global file_spec
    if file_spec is None:
        # set on first use
        if PY2:
            file_spec = file
        else:
            import _io
            file_spec = list(set(dir(_io.TextIOWrapper)).union(set(dir(_io.BytesIO))))

    m = MagicMock(name='open', spec=open)

    handle = MagicMock(spec=file_spec)
    handle.__enter__.return_value = handle
    m.return_value = handle

    content_out = StringIO()

    with patch(builtins_open, m, create=True, **kwargs) as mo:
        stream = StringIO(content)
        rv = mo.return_value
        rv.write = lambda x: content_out.write(bytes(x, "utf-8"))
        rv.content_out = lambda: content_out.getvalue()
        rv.__iter__.return_value = iter(stream.readlines())
        rv.read.return_value = stream.read()
        yield rv
