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
Common operations.
"""
import os
import re
import sys
import subprocess
import shlex

from bugzilla.rhbugzilla import RHBugzilla

from tito.compat import xmlrpclib, getstatusoutput
from tito.exception import TitoException
from tito.exception import RunCommandException
from tito.tar import TarFixer, RECORD_SIZE

DEFAULT_BUILD_DIR = "/tmp/tito"
DEFAULT_BUILDER = "builder"
DEFAULT_TAGGER = "tagger"
BUILDCONFIG_SECTION = "buildconfig"
SHA_RE = re.compile(r'\b[0-9a-f]{30,}\b')

# Define some shortcuts to fully qualified Builder classes to make things
# a little more concise for CLI users. Mock is probably the only one this
# is relevant for at this time.
BUILDER_SHORTCUTS = {
    'mock': 'tito.builder.MockBuilder'
}


def extract_sources(spec_file_lines):
    """
    Returns a list of sources from the given spec file.

    Some of these will be URL's, which is fine they will be ignored.
    We're really just after relative filenames that might live in the same
    location as the spec file, mostly used with NoTgzBuilder packages.
    """
    filenames = []
    source_pattern = re.compile('^Source\d+?:\s*(.*)')
    for line in spec_file_lines:
        match = source_pattern.match(line)
        if match:
            filenames.append(match.group(1))
    return filenames


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


def error_out(error_msgs):
    """
    Print the given error message (or list of messages) and exit.
    """
    print
    if isinstance(error_msgs, list):
        for line in error_msgs:
            print("ERROR: %s" % line)
    else:
        print("ERROR: %s" % error_msgs)
    print
#    if 'DEBUG' in os.environ:
#        traceback.print_stack()
    sys.exit(1)


def create_builder(package_name, build_tag,
        config, build_dir, user_config, args,
        builder_class=None, **kwargs):
    """
    Create (but don't run) the builder class. Builder object may be
    used by other objects without actually having run() called.
    """

    # Allow some shorter names for builders for CLI users.
    if builder_class in BUILDER_SHORTCUTS:
        builder_class = BUILDER_SHORTCUTS[builder_class]

    if builder_class is None:
        debug("---- Builder class is None")
        if config.has_option("buildconfig", "builder"):
            builder_class = get_class_by_name(config.get("buildconfig",
                "builder"))
        else:
            debug("---- Global config")
            builder_class = get_class_by_name(config.get(
                BUILDCONFIG_SECTION, DEFAULT_BUILDER))
    else:
        # We were given an explicit builder class as a str, get the actual
        # class reference:
        builder_class = get_class_by_name(builder_class)
    debug("Using builder class: %s" % builder_class)

    # Instantiate the builder:
    builder = builder_class(
        name=package_name,
        tag=build_tag,
        build_dir=build_dir,
        config=config,
        user_config=user_config,
        args=args,
        **kwargs)
    return builder


def find_file_with_extension(in_dir=None, suffix=None):
    """ Find the file with given extension in the current directory. """
    if in_dir is None:
        in_dir = os.getcwd()
    file_name = None
    debug("Looking for %s in %s" % (suffix, in_dir))
    for f in os.listdir(in_dir):
        if f.endswith(suffix):
            if file_name is not None:
                error_out("At least two %s files in directory: %s and %s" % (suffix, file_name, f))
            file_name = f
            debug("Using file: %s" % f)
    if file_name is None:
        error_out("Unable to locate a %s file in %s" % (suffix, in_dir))
    else:
        return file_name


def find_spec_file(in_dir=None):
    """
    Find the first spec file in the current directory.

    Returns only the file name, rather than the full path.
    """
    return find_file_with_extension(in_dir, '.spec')


def find_gemspec_file(in_dir=None):
    """
    Find the first spec file in the current directory.

    Returns only the file name, rather than the full path.
    """
    return find_file_with_extension(in_dir, '.gemspec')


def find_git_root():
    """
    Find the top-level directory for this git repository.

    Returned as a full path.
    """
    (status, cdup) = getstatusoutput("git rev-parse --show-cdup")
    if status > 0:
        error_out(["%s does not appear to be within a git checkout." %
                os.getcwd()])

    if cdup.strip() == "":
        cdup = "./"
    return os.path.abspath(cdup)


def tito_config_dir():
    """ Returns "rel-eng" for old tito projects and ".tito" for
    recent projects.
    """
    tito_dir = os.path.join(find_git_root(), ".tito")
    if os.path.isdir(tito_dir):
        return ".tito"
    else:
        return "rel-eng"


def extract_sha1(output):
    match = SHA_RE.search(output)
    if match:
        return match.group(0)
    else:
        return ""


def run_command(command, print_on_success=False):
    """
    Run command.
    If command fails, print status code and command output.
    """
    (status, output) = getstatusoutput(command)
    if status > 0:
        sys.stderr.write("\n########## ERROR ############\n")
        sys.stderr.write("Error running command: %s\n" % command)
        sys.stderr.write("Status code: %s\n" % status)
        sys.stderr.write("Command output: %s\n" % output)
        raise RunCommandException(command, status, output)
    elif print_on_success:
        print("Command: %s\n" % command)
        print("Status code: %s\n" % status)
        print("Command output: %s\n" % output)
    return output


def run_command_print(command):
    """
    Simliar to run_command but prints each line of output on the fly.
    """
    output = []
    env = os.environ.copy()
    env['LC_ALL'] = 'C'
    p = subprocess.Popen(shlex.split(command),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        universal_newlines=True)
    for line in run_subprocess(p):
        line = line.rstrip('\n')
        print(line)
        output.append(line)
    print("\n"),
    if p.poll() > 0:
        raise RunCommandException(command, p.poll(), "\n".join(output))
    return '\n'.join(output)


def run_subprocess(p):
    while(True):
        retcode = p.poll()
        line = p.stdout.readline()
        if len(line) > 0:
            yield line
        if(retcode is not None):
            break


def tag_exists_locally(tag):
    (status, output) = getstatusoutput("git tag | grep %s" % tag)
    if status > 0:
        return False
    else:
        return True


def tag_exists_remotely(tag):
    """ Returns True if the tag exists in the remote git repo. """
    try:
        get_git_repo_url()
    except:
        sys.stderr.write('Warning: remote.origin do not exist. Assuming --offline, for remote tag checking.\n')
        return False
    sha1 = get_remote_tag_sha1(tag)
    debug("sha1 = %s" % sha1)
    if sha1 == "":
        return False
    return True


def get_local_tag_sha1(tag):
    tag_sha1 = run_command(
        "git ls-remote ./. --tag %s | awk '{ print $1 ; exit }'"
        % tag)
    tag_sha1 = extract_sha1(tag_sha1)
    return tag_sha1


def head_points_to_tag(tag):
    """
    Ensure the current git head is the same commit as tag.

    For some reason the git commands we normally use to fetch SHA1 for a tag
    do not work when comparing to the HEAD SHA1. Using a different command
    for now.
    """
    debug("Checking that HEAD commit is %s" % tag)
    head_sha1 = run_command("git rev-list --max-count=1 HEAD")
    tag_sha1 = run_command("git rev-list --max-count=1 %s" % tag)
    debug("   head_sha1 = %s" % head_sha1)
    debug("   tag_sha1 = %s" % tag_sha1)
    return head_sha1 == tag_sha1


def undo_tag(tag):
    """
    Executes git commands to delete the given tag and undo the most recent
    commit. Assumes you have taken necessary precautions to ensure this is
    what you want to do.
    """
    # Using --merge here as it appears to undo the changes in the commit,
    # but preserve any modified files:
    output = run_command("git tag -d %s && git reset --merge HEAD^1" % tag)
    print(output)


def get_remote_tag_sha1(tag):
    """
    Get the SHA1 referenced by this git tag in the remote git repo.
    Will return "" if the git tag does not exist remotely.
    """
    # TODO: X11 forwarding messages can appear in this output, find a better way
    repo_url = get_git_repo_url()
    print("Checking for tag [%s] in git repo [%s]" % (tag, repo_url))
    cmd = "git ls-remote %s --tag %s | awk '{ print $1 ; exit }'" % \
            (repo_url, tag)
    upstream_tag_sha1 = run_command(cmd)
    upstream_tag_sha1 = extract_sha1(upstream_tag_sha1)
    return upstream_tag_sha1


def check_tag_exists(tag, offline=False):
    """
    Check that the given git tag exists in a git repository.
    """
    if not tag_exists_locally(tag):
        error_out("Tag does not exist locally: [%s]" % tag)

    if offline:
        return

    tag_sha1 = get_local_tag_sha1(tag)
    debug("Local tag SHA1: %s" % tag_sha1)

    try:
        repo_url = get_git_repo_url()
    except:
        sys.stderr.write('Warning: remote.origin do not exist. Assuming --offline, for remote tag checking.\n')
        return
    upstream_tag_sha1 = get_remote_tag_sha1(tag)
    if upstream_tag_sha1 == "":
        error_out(["Tag does not exist in remote git repo: %s" % tag,
            "You must tag, then git push and git push --tags"])

    debug("Remote tag SHA1: %s" % upstream_tag_sha1)

    if upstream_tag_sha1 != tag_sha1:
        error_out("Tag %s references %s locally but %s upstream." % (tag,
            tag_sha1, upstream_tag_sha1))


def debug(text, cmd=None):
    """
    Print the text if --debug was specified.
    If cmd is specified, run the command and print its output after text.
    """
    if 'DEBUG' in os.environ:
        print(text)
        if cmd:
            run_command(cmd, True)


def get_spec_version_and_release(sourcedir, spec_file_name):
    command = ("""rpm -q --qf '%%{version}-%%{release}\n' --define """
        """"_sourcedir %s" --define 'dist %%undefined' --specfile """
        """%s 2> /dev/null | grep -e '^$' -v | head -1""" % (sourcedir, spec_file_name))
    return run_command(command)


def scl_to_rpm_option(scl, silent=None):
    """ Returns rpm option which disable or enable SC and print warning if needed """
    rpm_options = ""
    cmd = "rpm --eval '%scl'"
    output = run_command(cmd).rstrip()
    if scl:
        if (output != scl) and (output != "%scl") and not silent:
            print("Warning: Meta package of software collection %s installed, but --scl defines %s" % (output, scl))
            print("         Redefining scl macro to %s for this package." % scl)
        rpm_options += " --define 'scl %s'" % scl
    else:
        if (output != "%scl") and (not silent):
            print("Warning: Meta package of software collection %s installed, but --scl is not present." % output)
            print("         Undefining scl macro for this package.")
        # can be replaced by "--undefined scl" when el6 and fc17 is retired
        rpm_options += " --eval '%undefine scl'"
    return rpm_options


def get_project_name(tag=None, scl=None):
    """
    Extract the project name from the specified tag or a spec file in the
    current working directory. Error out if neither is present.
    """
    if tag is not None:
        p = re.compile('(.*?)-(\d.*)')
        m = p.match(tag)
        if not m:
            error_out("Unable to determine project name in tag: %s" % tag)
        return m.group(1)
    else:
        spec_file_path = os.path.join(os.getcwd(), find_spec_file())
        if not os.path.exists(spec_file_path):
            error_out("spec file: %s does not exist" % spec_file_path)

        output = run_command(
            "rpm -q --qf '%%{name}\n' %s --specfile %s 2> /dev/null | grep -e '^$' -v | head -1" %
            (scl_to_rpm_option(scl, silent=True), spec_file_path))
        if not output:
            error_out(["Unable to determine project name from spec file: %s" % spec_file_path,
                "Try rpm -q --specfile %s" % spec_file_path,
                "Try rpmlint -i %s" % spec_file_path])
        return output


def replace_version(line, new_version):
    """
    Attempts to replace common setup.py version formats in the given line,
    and return the modified line. If no version is present the line is
    returned as is.

    Looking for things like version="x.y.z" with configurable case,
    whitespace, and optional use of single/double quotes.
    """
    # Mmmmm pretty regex!
    ver_regex = re.compile("(\s*)(version)(\s*)(=)(\s*)(['\"])(.*)(['\"])(.*)",
            re.IGNORECASE)
    m = ver_regex.match(line)
    if m:
        result_tuple = list(m.group(1, 2, 3, 4, 5, 6))
        result_tuple.append(new_version)
        result_tuple.extend(list(m.group(8, 9)))
        new_line = "%s%s%s%s%s%s%s%s%s\n" % tuple(result_tuple)
        return new_line
    else:
        return line


def get_relative_project_dir(project_name, commit):
    """
    Return the project's sub-directory relative to the git root.

    This could be a different directory than where the project currently
    resides, so we export a copy of the project's metadata from
    .tito/packages/ at the point in time of the tag we are building.
    """
    cmd = "git show %s:%s/packages/%s" % (commit, tito_config_dir(),
            project_name)
    try:
        (status, pkg_metadata) = getstatusoutput(cmd)
    except:
        cmd = "git show %s:%s/packages/%s" % (commit, "rel-eng",
            project_name)
        (status, pkg_metadata) = getstatusoutput(cmd)
    tokens = pkg_metadata.strip().split(" ")
    debug("Got package metadata: %s" % tokens)
    if status != 0:
        return None
    return tokens[1]


def get_relative_project_dir_cwd(git_root):
    """
    Returns the patch to the project we're working with relative to the
    git root using the cwd.

    *MUST* be called before doing any os.cwd().

    i.e. java/, satellite/install/Spacewalk-setup/, etc.
    """
    current_dir = os.getcwd()
    relative = current_dir[len(git_root) + 1:] + "/"
    if relative == "/":
        relative = "./"
    return relative


def get_build_commit(tag, test=False):
    """ Return the git commit we should build. """
    if test:
        return get_latest_commit(".")
    else:
        tag_sha1 = run_command(
            "git ls-remote ./. --tag %s | awk '{ print $1 ; exit }'"
            % tag)
        tag_sha1 = extract_sha1(tag_sha1)
        commit_id = run_command('git rev-list --max-count=1 %s' % tag_sha1)
        return commit_id


def get_commit_count(tag, commit_id):
    """ Return the number of commits between the tag and commit_id"""
    # git describe returns either a tag-commitcount-gSHA1 OR
    # just the tag.
    #
    # so we need to pass in the tag as well.
    # output = run_command("git describe --match=%s %s" % (tag, commit_id))
    # if tag == output:
    #     return 0
    # else:
    #     parse the count from the output
    (status, output) = getstatusoutput(
        "git describe --match=%s %s" % (tag, commit_id))

    debug("tag - %s" % tag)
    debug("output - %s" % output)

    if status != 0:
        debug("git describe of tag %s failed (%d)" % (tag, status))
        return 0

    if tag != output:
        # tag-commitcount-gSHA1, we want the penultimate value
        cnt = output.split("-")[-2]
        return cnt

    return 0


def get_latest_commit(path="."):
    """ Return the latest git commit for the given path. """
    commit_id = run_command("git log --pretty=format:%%H --max-count=1 %s" % path)
    return commit_id


def get_commit_timestamp(sha1_or_tag):
    """
    Get the timestamp of the git commit or tag we're building. Used to
    keep the hash the same on all .tar.gz's we generate for a particular
    version regardless of when they are generated.
    """
    output = run_command(
        "git rev-list --timestamp --max-count=1 %s | awk '{print $1}'"
        % sha1_or_tag)
    return output


def create_tgz(git_root, prefix, commit, relative_dir,
    dest_tgz):
    """
    Create a .tar.gz from a projects source in git.
    """
    os.chdir(os.path.abspath(git_root))
    timestamp = get_commit_timestamp(commit)

    # Accomodate standalone projects with specfile i root of git repo:
    relative_git_dir = "%s" % relative_dir
    if relative_git_dir in ['/', './']:
        relative_git_dir = ""

    basename = os.path.splitext(dest_tgz)[0]
    initial_tar = "%s.initial" % basename

    # command to generate a git-archive
    git_archive_cmd = 'git archive --format=tar --prefix=%s/ %s:%s --output=%s' % (
        prefix, commit, relative_git_dir, initial_tar)
    run_command(git_archive_cmd)

    # Run git-archive separately if --debug was specified.
    # This allows us to detect failure early.
    # On git < 1.7.4-rc0, `git archive ... commit:./` fails!
    debug('git-archive fails if relative dir is not in git tree',
        '%s > /dev/null' % git_archive_cmd)

    fixed_tar = "%s.tar" % basename
    fixed_tar_fh = open(fixed_tar, 'wb')
    try:
        tarfixer = TarFixer(open(initial_tar, 'rb', RECORD_SIZE), fixed_tar_fh, timestamp, commit)
        tarfixer.fix()
    finally:
        fixed_tar_fh.close()

    # It's a pity we can't use Python's gzip, but it doesn't offer an equivalent of -n
    return run_command("gzip -n -c < %s > %s" % (fixed_tar, dest_tgz))


def get_git_repo_url():
    """
    Return the url of this git repo.

    Uses ~/.git/config remote origin url.
    """
    return run_command("git config remote.origin.url")


def get_latest_tagged_version(package_name):
    """
    Return the latest git tag for this package in the current branch.
    Uses the info in .tito/packages/package-name.

    Returns None if file does not exist.
    """
    git_root = find_git_root()
    rel_eng_dir = os.path.join(git_root, tito_config_dir())
    file_path = "%s/packages/%s" % (rel_eng_dir, package_name)
    debug("Getting latest package info from: %s" % file_path)
    if not os.path.exists(file_path):
        return None

    output = run_command("awk '{ print $1 ; exit }' %s" % file_path)
    if output is None or output.strip() == "":
        error_out("Error looking up latest tagged version in: %s" % file_path)

    return output


def normalize_class_name(name):
    """
    Just a hack to accomodate tito config files with builder/tagger
    classes referenced in the spacewalk.releng namespace, which has
    since been renamed to just tito.
    """
    look_for = "spacewalk.releng."
    if name.startswith(look_for):
        sys.stderr.write("Warning: spacewalk.releng.* namespace in tito.props is obsolete. Use tito.* instead.\n")
        name = "%s%s" % ("tito.", name[len(look_for):])
    return name


def get_script_path(scriptname):
    """
    Hack to accomodate functional tests running from source, rather than
    requiring tito to actually be installed. This variable is only set by
    test scripts, normally we assume scripts are on PATH.
    """
    # TODO: Would be nice to get rid of this hack.
    scriptpath = scriptname  # assume on PATH by default
    if 'TITO_SRC_BIN_DIR' in os.environ:
        bin_dir = os.environ['TITO_SRC_BIN_DIR']
        scriptpath = os.path.join(bin_dir, scriptname)
    return scriptpath


def get_class_by_name(name):
    """
    Get a Python class specified by it's fully qualified name.

    NOTE: Does not actually create an instance of the object, only returns
    a Class object.
    """
    name = normalize_class_name(name)
    # Split name into module and class name:
    tokens = name.split(".")
    class_name = tokens[-1]
    module = '.'.join(tokens[0:-1])

    debug("Importing %s" % name)
    mod = __import__(module, globals(), locals(), [class_name])
    return getattr(mod, class_name)


def increase_version(version_string):
    regex = re.compile(r"^(%.*)|(.+\.)?([0-9]+)(\..*|_.*|%.*|$)")
    match = re.match(regex, version_string)
    if match:
        matches = list(match.groups())
        # Increment the number in the third match group, if there is one
        if matches[2]:
            matches[2] = str(int(matches[2]) + 1)
        # Join everything back up, skipping match groups with None
        return "".join([x for x in matches if x])

    # If no match, return the original string
    return version_string


def reset_release(release_string):
    regex = re.compile(r"(^|\.)([.0-9]+)(\.|%|$)")
    return regex.sub(r"\g<1>1\g<3>", release_string)


def increase_zstream(release_string):
    # If we do not have zstream, create .0 and then bump the version
    regex = re.compile(r"^(.*%{\?dist})$")
    bumped_string = regex.sub(r"\g<1>.0", release_string)
    return increase_version(bumped_string)


def find_wrote_in_rpmbuild_output(output):
    """
    Parse the output from rpmbuild looking for lines beginning with
    "Wrote:". Return a list of file names for each path found.
    """
    paths = []
    look_for = "Wrote: "
    for line in output.split('\n'):
        if line.startswith(look_for):
            paths.append(line[len(look_for):])
            debug("Found wrote line: %s" % paths[-1])
    if not paths:
        error_out("Unable to locate 'Wrote: ' lines in rpmbuild output: '%s'" % output)
    return paths


def compare_version(version1, version2):
    """
    Compare two version strings, returning negative if version1 is < version2,
    zero when equal and positive when version1 > version2.
    """
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]
    a = normalize(version1)
    b = normalize(version2)
    return (a > b) - (a < b)
