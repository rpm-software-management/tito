import re
import os

from tito.common import debug


class CargoBump:
    """
    Cargo is package manager for the Rust programming
    language: http://doc.crates.io/manifest.html
    It uses Cargo.toml file as its configuration file.
    XXX: I'm not including a Toml parser, because I
    don't want to introduce new dependencies.
    """

    @staticmethod
    def tag_new_version(new_version, config_file):
        """
        Find the line with version number  and change
        it to contain the new version.
        """
        if not os.path.exists(config_file):
            debug('Config file was not found.')
            return

        debug("Found config file, attempting to update version.")
        # We probably don't want version-release in config file as
        # release is an RPM concept
        rust_new_version = new_version.split('-')[0]
        file_buffer = []

        with open(config_file, 'r') as cfgfile:
            pkg_label = re.compile('^\[package\]$')
            label = re.compile('^\[.*\]$')
            version = re.compile('(^version\s*=\s*)["\'](.+)["\'](.*$)')
            lines = [line.rstrip('\n') for line in cfgfile]
            state = 1
            for line in lines:
                # Looking for [package] label
                if state == 1:
                    file_buffer.append(line)
                    if re.match(pkg_label, line):
                        state = 2
                elif state == 2:
                    # Looking for version = "x.x.x" line
                    if re.match(version, line):
                        v = re.split(version, line)
                        file_buffer.append(v[1] + '"' + rust_new_version + '"' + v[3])
                        state = 3
                    else:
                        file_buffer.append(line)
                    # if we found another label before version, it's probably not there
                    if re.match(label, line):
                        state = 3
                # Just copy the rest of the file into the buffer
                else:
                    file_buffer.append(line)

        with open(config_file, 'w') as cfgfile:
            cfgfile.writelines(map(lambda x: x + "\n", file_buffer))
