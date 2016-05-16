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

from tito.release import Releaser


class DummyReleaser(Releaser):

    def __init__(self, name=None, version=None, tag=None, build_dir=None,
            config=None, user_config=None):
        Releaser.__init__(self, name, version, tag, build_dir,
                config, user_config)
        pass

    def release(self, dry_run=False):
        print("DUMMY RELEASE!!!!!!!!!!!!!!!!!")
