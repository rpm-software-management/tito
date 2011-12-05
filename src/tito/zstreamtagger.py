from tito.tagger import VersionTagger


class zStreamTagger(VersionTagger):
    """
    Tagger which increments the spec file zstream number instead of version.

    Used for:
        - Red Hat Service Packs (zstream)
    """

    def _tag_release(self):
        """
        Tag a new zstream of the package. (i.e. x.y.z-r%{dist}.Z+1)
        """
        self._make_changelog()
        new_version = self._bump_version(release=True)

        self._check_tag_does_not_exist(self._get_new_tag(new_version))
        self._update_changelog(new_version)
        self._update_package_metadata(new_version)

    def release_type(self):
        """ return short string "zstream release" """
        return "zstream release"
