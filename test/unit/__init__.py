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

from contextlib import contextmanager
from mock import mock_open, patch
from StringIO import StringIO
from itertools import repeat

@contextmanager
def open_mock(content, **kwargs):
    """Mock's mock_open only supports read() and write() which is not very useful.
    This context manager adds support for getting the value of what was written out
    and for iterating through a file line by line."""
    content_out = StringIO()
    m = mock_open()
    with patch('__builtin__.open', m, create=True, **kwargs) as mo:
        stream = StringIO(content)
        rv = mo.return_value
        rv.write = lambda x: content_out.write(bytes(x, "utf-8"))
        rv.content_out = lambda: content_out.getvalue()
        rv.__iter__.return_value = iter(stream.readlines())
        rv.read.return_value = stream.read()
        yield rv