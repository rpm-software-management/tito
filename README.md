ABOUT
=====

Tito is a tool for managing RPM based projects using git for their source code
repository.

Tito offers the following features:

 - Tag new releases with incremented RPM version or release.
 - Auto-generate spec file changelog based on git history since last tag.
 - Create reliable tar.gz files with consistent checksums from any tag.
 - Build source and binary rpms off any tag.
 - Build source and binary "test" rpms off most recently committed code.
 - Build multiple source rpms with appropriate disttags for submission to the
   Koji build system
 - Build rpms via the "mock" tool.
 - On a per-branch basis in git:
   - Maintain concurrent version streams.
   - Vary the way packages are built/tagged.
 - Report on any diffs or commits messages missing since last tag.
 - Define release targets to publish your packages to yum repositories, or
   the Fedora build system.
 - Define custom builder/releaser implementations for your own project needs.
 - Build packages off an "upstream" git repository, where modifications in the
   "downstream" git repository will be applied as a patch in the source rpm.
 - Manage all of the above for a git repository with many disjoint packages
   within it.

RELATED PROJECTS
================

* `mockchain` from the [mock project](https://github.com/rpm-software-management/mock/wiki)
* `mock`'s built-in SCM support in `mock-scm`
* Fedora's [Koji](https://koji.fedoraproject.org/koji/) build engine and [fedpkg](https://fedorahosted.org/fedpkg/) tools
* The [OpenSUSE Build Service](https://build.opensuse.org/).
* See also [Fedora wiki page for layered build tools](https://fedoraproject.org/wiki/Layered_build_scripts_for_package_maintainers)

INSTALL
=======

From Fedora:

    dnf install tito

From CentOS / RHEL:

    # Enable EPEL https://fedoraproject.org/wiki/EPEL#How_can_I_use_these_extra_packages.3F
    yum install tito

From [PyPI](https://pypi.org/project/tito/):

    pip install tito

From git's `master` branch:

- First install Tito's dependencies for your architecture, i.e. `x86_64`:

      sudo dnf install --setopt=install_weak_deps=False \
          $(dnf repoquery --arch x86_64,noarch --requires tito --resolve -q)

  _NOTE: This will install Tito's dependencies from Tito's latest release for
  your system. If the `master` branch requires a new dependency, it will need to
  be installed manually._

- Then install Tito via so-called [User install](
  https://pip.pypa.io/en/stable/user_guide/#user-installs) (i.e. isolated to the
  current user):

      pip install --user https://github.com/rpm-software-management/tito/archive/master.tar.gz

To make an rpm of tito to install elsewhere

    sudo yum install python-devel asciidoc
    tito build --rpm
    # see what's in the package
    rpm -ql -p /tmp/tito/noarch/tito-*.noarch.rpm


GETTING STARTED
===============


From your git repository:

    tito init

This will create a top-level metadata directory called ".tito/" and commit it
to git. This directory will store tito's configuration and package metadata on
a per branch basis. It will be filtered out when creating .tar.gz files.


TAGGING PACKAGES
================

Before doing most everything you'll need to tag your package(s).

Before doing this you'll need to ensure that your package spec files are at the top of the relative source tree for that package.

For the most common case, a single project git repository has the spec file and
root of the project at the top level of the git repository:

    docs/
    mypackage.spec
    README
    .tito/
    src/
    test/

For a multi-project git repository, packages can be defined in various
sub-directories, provided they do not nest (i.e. walking up the tree, two spec
files will never be encountered):

    .tito/
    package1/
        docs/
        mypackage.spec
        README
        src/
        test/
    subdir/
        package2/
            anotherpkg.spec
            docs/
            README
            src/
            test/

The packages can be organized in any hierarchy you like and even be moved
around and re-tagged, we only need to have the spec file in the top level
directory for that package.

Tagging packages is normally done with:

    tito tag

This will:

 - bump the version or release in the spec file (use --keep-version to use whatever is defined in the spec file)
 - auto-generate a changelog from first line of each commit since last tag (use --no-auto-changelog if you do not want this)
 - open an editor allowing you a chance to edit that changelog
 - insert the changelog into your spec
 - commit these changes, and generate a git tag

By default if you omit --keep-version, tito will tag by bumping the rpm
version. (i.e. we bump the Z in X.Y.Z. If you'd prefer to bump the package
release instead (normally should just be used for changes to the spec file or
patches applied within it), you can change the 'tagger' class in
.tito/tito.props to ReleaseTagger. This will affect all packages in this git
branch, if you'd prefer to do this on a per-package basis you can do so in a
package specific tito.props. (see section below)

Once a package is tagged you will need to push both the auto-commit and the tag
to your remote git repository before tito will let you build it. (better
support for standalone git repositories is coming, for now --offline will help)

See "man tito" for more options.

BUILDING PACKAGES
=================

To build the most recent .tar.gz for a package, cd into that packages directory
and run:

    tito build --tgz

Note that this tarball will have a consistent checksum every time.

Likewise the --srpm and --rpm options allow you to build both binary and source
rpms.

Add in the --tag=TAG option to build any of the above for any past tag.

If you're working on something locally and would like to check that your
package is still building ok without pushing your changes to the remote
repository, add the --test option. This will build a test rpm from your most
recently committed work. (NOTE: does *not* include uncommitted changes)

TODO: Document the use of --release, which is complicated and untested against
Fedora's Koji.

See "man tito" for more options.


RELEASING PACKAGES
==================

Tito supports a mechanism where you can define multiple release targets.

In .tito/releasers.conf, create a section like:

    [yum-f15-x86_64]
    releaser = tito.release.YumRepoReleaser
    builder = tito.builder.MockBuilder
    builder.mock = fedora-15-x86_64
    rsync = fedorapeople.org:/srv/repos/dgoodwin/tito/fedora-15/x86_64/

You can define as many release targets as you like with various configurations.
To publish the most recently tagged build in your current branch you would run:

    tito release yum-f15-x86_64

You can specify multiple targets on the CLI.

See "man 8 releasers.conf" for more information on defining release targets.

See "man tito" for more information on CLI arguments to "tito release".



CUSTOM BUILDERS / TAGGERS / RELEASERS
=====================================

If the existing implementations Tito provides are not sufficient for
your needs, it is possible to define a lib_dir in tito.props buildconfig
section. This is a directory that tito will add to the python path during
execution, allowing you a place to define your own custom implementations of
builders, taggers, and releasers.

The process of actually writing a custom Builder/Tagger/Releaser is an exercise
left to the reader, but essentially you will want to work off the code in the
tito.builder module. Inherit from the base Builder, and override the methods
you need to.

Please note that if you store your custom implementations inside your source
tree, they will need to be kept in sync in all branches you are using for
consistent behavior. Also, there are no guarantees that tito will not change in
future releases, meaning that your custom implementations may occasionally need
to be updated.


TROUBLESHOOTING
===============

If you create a tag accidentally or that you wish to re-do, make sure you have
not git pushed the tag yet, the auto-commit is the most recent in your git
history, and run:

    git tag -d YOURNEWTAG
    git reset --hard HEAD^1

If your project is standalone (no remote reference you communicate with as
authoritative) you may wish to set offline = "true" in .tito/tito.props under
the buildconfig section, so you do not need to specify --offline with each
invocation.


CONFIGURATION
=============

See:

    man 5 tito.props

    man 5 releasers.conf

    man 5 titorc


COMMUNITY
=========

If you need an advice or want to chat with Tito developers, join us
on `#tito` channel at [irc.freenode.net](https://webchat.freenode.net/).


Projects managed with Tito
==========================

Here follows a list of projects managed with Tito. It is not trying to be a complete list
of every project using tito but rather a few examples that potential users can check out.

- [Mock](https://github.com/rpm-software-management/mock)
- [Copr](https://pagure.io/copr/copr)
- [Tito](https://github.com/dgoodwin/tito)
- [Dnf](https://github.com/rpm-software-management/dnf)
- [Candlepin](https://github.com/candlepin/candlepin)
- [dnf-plugins-core](https://github.com/rpm-software-management/dnf-plugins-core)
- [candlepin/subscription-manager](https://github.com/candlepin/subscription-manager)
- [rho](https://github.com/candlepin/rho)
- [sm-photo-tool](https://github.com/jmrodri/sm-photo-tool)
- [vim-fugitive-pagure](https://github.com/FrostyX/vim-fugitive-pagure)


If your project uses Tito, feel free to add it here.


EXTERNAL DOCS
=============

[How to create new release of RPM package in 5 seconds](
http://miroslav.suchy.cz/blog/archives/2013/12/17/how_to_create_new_release_of_rpm_package_in_5_seconds)

[How to build in Copr](
http://miroslav.suchy.cz/blog/archives/2013/12/29/how_to_build_in_copr)

[Building RHEL packages with Tito](http://frostyx.cz/posts/building-rhel-packages-with-tito)
