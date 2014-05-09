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

from tito.exception import TitoException


class BuildTargetParser(object):
    """
    Parses build targets from a string in the format of:
        <branch1>:<target> <branch2>:<target> ...

    Each target must be associated with a valid branch.
    """

    def __init__(self, releaser_config, release_target, valid_branches):
        self.releaser_config = releaser_config
        self.release_target = release_target
        self.valid_branches = valid_branches

    def get_build_targets(self):
        build_targets = {}
        if not self.releaser_config.has_option(self.release_target, "build_targets"):
            return build_targets

        defined_build_targets = self.releaser_config.get(self.release_target,
                                                         "build_targets").split(" ")
        for build_target in defined_build_targets:
            # Ignore any empty from multiple spaces in the file.
            if not build_target:
                continue

            branch, target = self._parse_build_target(build_target)
            build_targets[branch] = target

        return build_targets

    def _parse_build_target(self, build_target):
        """ Parses a string in the format of branch:target """
        if not build_target:
            raise TitoException("Invalid build_target: %s. Format: <branch>:<target>"
                                % build_target)

        parts = build_target.split(":")
        if len(parts) != 2:
            raise TitoException("Invalid build_target: %s. Format: <branch>:<target>"
                                % build_target)
        branch = parts[0]
        if branch not in self.valid_branches:
            raise TitoException("Invalid build_target: %s. Unknown branch reference."
                                % build_target)
        target = parts[1]
        if not target:
            raise TitoException("Invalid build_target: %s. Empty target" % build_target)

        return (branch, target)
