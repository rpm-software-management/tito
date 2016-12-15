import re
import os

from tito.common import debug, run_command


class CargoBump:
    """
    Cargo is package manager for the Rust programming
    language: http://doc.crates.io/manifest.html
    It uses Cargo.toml file as its configuration file.
    XXX: I'm not including a Toml parser, because I
    don't want to introduce new dependencies.
    """

    @staticmethod
    def tag_new_version(project_path, new_version_release):
        """
        Find the line with version number  and change
        it to contain the new version.
        """
        file_name = "Cargo.toml"
        config_file = os.path.join(project_path, file_name)

        if not os.path.exists(config_file):
            debug('Cargo.toml file not found, this is probably not a Rust project')
            return

        debug("Found Cargo.toml file, attempting to update the version.")
        # We probably don't want version-release in config file as
        # release is an RPM concept
        new_version = new_version_release.split('-')[0]
        file_buffer = []

        # Read file line by line and replace version when found
        with open(config_file, 'r') as cfgfile:
            file_buffer = CargoBump.process_cargo_toml(cfgfile, new_version)

        # Write the buffer back into the file
        with open(config_file, 'w') as cfgfile:
            cfgfile.writelines(map(lambda x: x + "\n", file_buffer))

        # Add Cargo.toml into git index
        run_command("git add %s" % file_name)

    @staticmethod
    def process_cargo_toml(input_string, new_version):
        file_buffer = []
        pkg_label = re.compile('^\[package\]$')
        label = re.compile('^\[.*\]$')
        version = re.compile('(^version\s*=\s*)["\'](.+)["\'](.*$)')
        lines = [line.rstrip('\n') for line in input_string]
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
                    file_buffer.append(v[1] + '"' + new_version + '"' + v[3])
                    state = 3
                else:
                    file_buffer.append(line)
                # if we found another label before version, it's probably not there
                if re.match(label, line):
                    state = 3
            # Just copy the rest of the file into the buffer
            else:
                file_buffer.append(line)

        return file_buffer
