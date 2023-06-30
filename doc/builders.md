# Tito Builders

## tito.builder.MockBuilder

By default, Tito internally uses `rpmbuild` for building SRPM and RPM
packages. This imposes some requirements on the host system - all the
build dependencies need to be installed. Also, building RPM packages
can potentially be dangerous and a badly written spec file can cause
damage to the host system. If you prefer to use `mock` instead,
configure `.tito/tito.props` like this:

    [buildconfig]
    builder = tito.builder.MockBuilder

    [builder]
    mock = fedora-rawhide-x86_64

Alternatively, you can specify a mock chroot in the command line:

    tito build --rpm --arg=mock=fedora-rawhide-x86_64

It is possible to specify additional Mock parameters in the config or
in the command line:

    tito build --rpm --arg mock_args="--no-clean --no-cleanup-after"

## tito.builder.FetchBuilder

An unorthodox builder which can build packages for a git repo which does not actually have any tito footprint. The location of sources, and the version/release to assume we're building, come from a configurable strategy.

One strategy is currently included which parses a CLI argument to the build command which points to the source to use.

Configuration for FetchBuilder in .tito/tito.props would look like:

    [buildconfig]
    builder = tito.builder.FetchBuilder

    [builder]
    fetch_strategy = tito.builder.fetch.ArgSourceStrategy

Once configured a build can be run with:

  **tito build --rpm --arg=source=/home/username/extsrc-0.0.1.tar.gz**

Note that this does not require a tito tag to have been run, and technically the .tito/tito.props does not have to be committed to the git repo. This builder can be used on a repository you do not control or do not wish to push tito configuration into.

The ArgSourceStrategy has a simple mechanism where it will try to parse the version and release to build from the filename with a regular expression. If you need something more advanced, you can override any or all of this behaviour by implementing a custom strategy for the fetch builder. (see lib_dir in **man 5 tito.props**)

## tito.builder.GitAnnexBuilder

A builder for packages with existing tarballs checked in using git-annex, e.g. referencing an external source (web remote) or special remotes used in the same way as a lookaside cache.

This builder will "unlock" the source files to get the real contents, include them in the SRPM, then restore the automatic git-annex symlinks on completion.

To create a new git repository using git-annex and tito init, run:

    git init
    git annex init
    tito init

Add the spec file as normal, but add the tarball/source via git-annex instead:

    cp ~/tito.spec ~/tito-0.4.18.tar.gz .
    git add tito.spec
    git annex add tito-0.4.18.tar.gz
    git commit -m "add tito 0.4.18"

Edit .tito/tito.props to change the builder to the GitAnnexBuilder:

    [globalconfig]
    default_builder = tito.builder.GitAnnexBuilder

Then finally tag and build as normal:

    tito tag --keep-version
    tito build --rpm

Remotes and special remotes can be used now with git-annex to transfer file content elsewhere.  Special remotes can be used to sync bulky files to things other than git repositories, e.g. shared directories, S3, WebDAV etc.

    git annex initremote usbdrive type=directory directory=/media/usb encryption=none
    git annex copy --to=usbdrive

Then files can be dropped or fetched again into the local repository, which acts as a local cache.  tito's GitAnnexBuilder will automatically "get" files during the build process.

    git annex drop
    git annex get

Files can be added with the "web" remote, useful for RPM sources.  The downside is that like with other remotes, this configuration needs to be added to each git checkout but is also on a file-by-file basis, so a script may be required.

    git annex addurl --file tito-0.4.18.tar.gz http://pkgs.fedoraproject.org/repo/pkgs/tito/tito-0.4.18.tar.gz/318e6f546c9b331317c94ea5d178876a/tito-0.4.18.tar.gz

More information in the [git-annex walkthrough](http://git-annex.branchable.com/walkthrough/) and [special remotes](http://git-annex.branchable.com/special_remotes/) documentation.


## tito.builder.SubmoduleAwareBuilder

A builder for packages that use `git submodules`.  git submodules can be contensious, however, in some places they are in use, so this Builder attempts to help with that.
The SubmoduleAwareBuilder was written and tested with a single submodule at the root of the repo, and it might break in other scenarios.

This builder will collect the files that are in git submodules using  `git submodule--helper list` 

Configuration for SubmoduleAwareBuilder in .tito/tito.props would look like:

    [buildconfig]
    builder = tito.builder.SubmoduleAwareBuilder

The only noticeable difference over `tito.builder.Builder` is that the SRPM will contain the submodule directories, and that the spec file can now contain files that are within a submodule.
