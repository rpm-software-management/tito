import os
import re
from bugzilla.rhbugzilla import RHBugzilla
from tito.common import debug, error_out
from tito.exception import TitoException
from tito.compat import xmlrpclib


class MissingBugzillaCredsException(TitoException):
    pass


class BugzillaExtractor(object):
    """
    Parses output of a dist-git commit diff looking for changelog
    entries that look like they reference bugzilla commits.

    Optionally can check bugzilla for required flags on each bug.
    """
    def __init__(self, diff_output, required_flags=None,
        placeholder_bz=None):

        self.diff_output = diff_output
        self.required_flags = required_flags
        self.placeholder_bz = placeholder_bz

        # Tuples of bugzilla ID + commit message we extracted:
        self.bzs = []

    def extract(self):

        self.bzs = self._extract_bzs()

        if self.required_flags:
            self._check_for_bugzilla_creds()
            self.bzs = self._filter_bzs_with_flags()

        return self._format_lines()

    def _check_for_bugzilla_creds(self):
        if not os.path.exists(os.path.expanduser("~/.bugzillarc")):
            raise MissingBugzillaCredsException("Missing ~/.bugzillarc")
        else:
            debug("Found bugzilla credentials in ~/.bugzillarc")

    def _extract_bzs(self):
        """
        Parses the output of CVS diff or a series of git commit log entries,
        looking for new lines which look like a commit of the format:

        ######: Commit message

        Returns a list of lines of text similar to:

        Resolves: #XXXXXX - Commit message

        If the releaser specifies any required bugzilla flags we will
        check each bug found and see if it has all required flags. If not
        we skip it. If we end up with *no* bugs with the required flags
        our build is likely to fail, so we look for a placeholder bugzilla
        defined in relaser config and use that instead if possible, otherwise
        error out.

        Returns a list of lines to write to the commit message as is.
        """
        regex = re.compile(r"^- (\d*)\s?[:-]+\s?(.*)")
        diff_regex = re.compile(r"^(\+- )+(\d*)\s?[:-]+\s?(.*)")
        bzs = []
        for line in self.diff_output.split("\n"):
            match = re.match(regex, line)
            match2 = re.match(diff_regex, line)
            if match:
                bzs.append((match.group(1), match.group(2)))
            elif match2:
                bzs.append((match2.group(2), match2.group(3)))
        return bzs

    def _format_lines(self):
        output = []
        for bz in self.bzs:
            output.append("Resolves: #%s - %s" % (bz[0], bz[1]))
        if len(output) == 0 and self.required_flags:
            # No bugzillas had required flags, use a placeholder if
            # we have one, otherwise we have to error out.
            if self.placeholder_bz:
                print("No bugs with required flags were found, using placeholder: %s" % self.placeholder_bz)
                output.append("Related: #%s" % self.placeholder_bz)
            else:
                error_out("No bugzillas found with required flags: %s" %
                    self.required_flags)
        return output

    def _filter_bzs_with_flags(self):
        print("Checking flags on bugs: %s" % self.bzs)
        print("  required flags: %s" % self.required_flags)

        # TODO: Would be nice to load bugs in bulk here but for now we'll
        # keep it simple.
        filtered_bzs = []
        for bz_tuple in self.bzs:
            bug_id = bz_tuple[0]
            try:
                bug = self._load_bug(bug_id)
            except xmlrpclib.Fault:
                print("WARNING: Bug %s does not seem to exist." % bug_id)
                continue
            debug("Bug %s has flags: %s" % (bug_id, bug.flags))
            flags_missing = False
            for flag in self.required_flags:
                if bug.get_flag_status(flag[0:-1]) != flag[-1]:
                    print("WARNING: Bug %s missing required flag: %s" %
                        (bug_id, flag))
                    flags_missing = True
                    break
                else:
                    debug("Bug %s has required flag: %s" %
                        (bug_id, flag))
            if not flags_missing:
                filtered_bzs.append(bz_tuple)
        return filtered_bzs

    def _load_bug(self, bug_id):
        bugzilla = RHBugzilla(url='https://bugzilla.redhat.com/xmlrpc.cgi')
        return bugzilla.getbug(bug_id, include_fields=['id', 'flags'])
