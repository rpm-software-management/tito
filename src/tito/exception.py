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
Tito Exceptions
"""


class TitoException(Exception):
    """
    Base Tito exception.

    Does nothing but indicate that this is a custom Tito error.
    """

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return "%s" % self.message


class RunCommandException(Exception):
    """ Raised by run_command() """
    def __init__(self, command, status, output):
        Exception.__init__(self, "Error running command: %s" % command)
        self.command = command
        self.status = status
        self.output = output


class ConfigException(TitoException):
    """
    Exception thrown when the user has specified invalid configuration.
    """
    pass
