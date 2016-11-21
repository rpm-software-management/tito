
class CargoTagger():
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
        pass