import re
from tito.common import run_command
from tito.tagger import ReleaseTagger


class RHELTagger(ReleaseTagger):
    """
    Tagger which is based on ReleaseTagger and use Red Hat Enterprise Linux
    format of Changelog:
    - Resolves: #1111 - description
    or
    - Related: #1111 - description
    if BZ number was already mentioned in this changelog

    Used for:
        - Red Hat Enterprise Linux

    If you want it put in tito.pros:
    [buildconfig]
    tagger = tito.rheltagger.RHELTagger
    """

    def _generate_default_changelog(self, last_tag):
        """
        Run git-log and will generate changelog, which still can be edited by user
        in _make_changelog.
        use format:
        - Resolves: #1111 - description
        """
        patch_command = "git log --pretty='format:%%s%s'" \
                         " --relative %s..%s -- %s" % (self._changelog_format(), last_tag, "HEAD", ".")
        output = run_command(patch_command)
        BZ = {}
        result = None
        for line in reversed(output.split('\n')):
            line = self._changelog_remove_cherrypick(line)
            line = line.replace('%', '%%')

            # prepend Related/Resolves if subject contains BZ number
            m = re.match("(\d+)\s+-\s+(.*)", line)
            if m:
                bz_number = m.group(1)
                if bz_number in BZ:
                    line = "Related: #%s - %s" % (bz_number, m.group(2))
                else:
                    line = "Resolves: #%s - %s" % (bz_number, m.group(2))
                    BZ[bz_number] = 1
            if result:
                result = line + "\n" + result
            else:
                result = line
        return result
