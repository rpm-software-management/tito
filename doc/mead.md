## Introduction
Mead is a Maven-based build system for Koji.  It works by building your
project via Maven, rendering a RPM spec file from a template, and then
packaging everything as an RPM with the rendered spec file.

Tito has support for Mead in its tagging, building, and releasing capacities.

## Setup
For a Maven project, Tito needs two things: a `pom.xml` and a `.tmpl` file.
The POM file should already be present since Maven itself requires one.  The
`.tmpl` file is a [Cheetah](http://www.cheetahtemplate.org/) template of your
RPM spec file that Mead fills in when it is building.

## Tagging
Tito will increase the version in the `pom.xml` for you when you tag.
However, it **does not** set the new version to a `-SNAPSHOT`
version as is the convention in many Maven projects.

Tito uses the maven-version plugin to increase the version.

## Building
Tito attempts to mimic the Mead build process although it is not perfect.
Mead offers the ability to descend into different directories and run the
build from there.  Tito does not do this.  Instead, Tito ascends to the root
of the SCM checkout and runs a `maven deploy` against the top-level POM file.
The artifacts are deployed to a temporary Maven repository under `/tmp/tito`.
Tito then attempts to render the `.tmpl` file for the package.  The following
variables are available (these values are also provided by Mead when Koji
runs a build):

* `$artifacts` - A hash of the Maven generated artifacts with the file
  extensions as keys.  For example: `{'.md5': 'my_project.jar.md5', '.jar':
  my_project.jar'}
* `$all_artifacts` - All Maven generated artifacts in a list (including MD5
  sums, pom files, etc)
* `$all_artifacts_with_path` - All artifacts but with the full path to the
  artifact within the project
* `$version` - The version of the **top level** project
* `$revision` - The revision of the **top_level** project
* `$epoch` - Currently always set to `None`
* `$name` - The name of the **top_level** project

Note that the `name`, `version`, and `revision` variables are not very useful
as they receive their values from the top-level POM file.

Once the spec file is rendered, Tito proceeds with a standard RPM build.

### Assemblies
Tito attempts to use the maven-assembly plugin to build a project tarball so
its best if you have that plugin configured.  Tito will fall back to a `git
archive` command, but the assembly plugin is the best way.

### Builder Arguments
The Mead builder can take several arguments on the command line: `maven_arg`
and `maven_property`.  These arguments can be specified multiple times.  The
`maven_property` arguments are passed to Maven as `-D` style properties and
the `maven_arg` arguments are passed as command-line arguments.  For example:

```
$ tito build --rpm --arg "maven_property=maven.test.skip=true" --arg "maven_arg=-X" -arg "maven_arg=-fae"
```

### Other Cheetah Notes

* Dollar signs are meaningful in Cheetah.  If your spec file contains shell
  variables, you will need to surround the relevant block with `#raw` and
  `#end raw` tags.

```
#raw
for selinuxvariant in %{selinux_variants}
do
  make NAME=$selinuxvariant -f /usr/share/selinux/devel/Makefile
  mv %{modulename}.pp %{modulename}.pp.$selinuxvariant
  make NAME=$selinuxvariant -f /usr/share/selinux/devel/Makefile clean
done
#end raw
```
* Do not use line continuations (i.e. ending a line with `\`)!
  Cheetah doesn't like them for some reason.
* Do not use non-ASCII characters anywhere in the Cheetah template (including
  names with non-ASCII characters in the changelog.)  I ran into difficulties
  with the template failing to render when non-ASCII characters appeared in
  it.
* Always surround the entire `%changelog` section in `#raw` and `#end raw`
  tags so that people's changelog entries won't break the template.

## Releasing

### Configuring the `DistGitMeadReleaser`
The first thing to do is to create a section in your `releasers.conf` for the
mead releaser.  In addition to the releaser class and branch, you need to
provide values for `mead_scm` and `mead_push_url`.  Mead does not build from
tarballs located in the Koji lookaside cache.  Instead it builds from URLs
pointing to an SCM repository.

* `mead_scm` - The SCM URL used to checkout the code
* `mead_target` - The SCM URL that Tito will use to push a copy of its tags
  to.  A `MEAD_SCM_USERNAME` value set in `~/.titorc` can be used here.

For example:

```
[mead]
releaser = tito.release.DistGitMeadReleaser
branches = fedora-20
mead_scm = git://example.com/my_project.git
mead_push_url = git+ssh://MEAD_SCM_USERNAME@example.com/my_project.git
```

### Configuring the Koji Build Process
The `tito.release.DistGitMeadReleaser` releaser using Mead's `maven-chain`
functionality.  The top-level package directory (the same directory with the
`.tmpl` file) must have a `.chain` file.

The chain file is an INI style file with each section as a different link in
the chain.  The section title is in the "groupId-artifactId" format and
contains a value for `scmurl` which is a pointer to the SCM containing the
code and a pointer to the git ref to use.  For example

```
scmurl=git://example.com/my_project.git?app#app-1.2.3-1
```

Note that the SCM URL can be followed by a "?" and a subdirectory; and that
the git ref is placed at the end after a "#".

Other options:

* `buildrequires` - a space delimited list of all sections that must be built
  beforehand
* `type` - set this to `wrapper` to add a wrapper RPM step.  Wrapper RPM steps
  need to have a `buildrequires` on the actual Maven build step.
* `packages` - a space delimited list of additional YUM packages to install
  before building
* `maven_options` - command line flags to pass to Maven
* `properties` - "key=value" list of properties to set with `-D`

For Tito, the `.chain` file needs to have a few variables in it that will be
filled in to alleviate the need for setting the git ref by hand.

The variables passed in are

* `mead_scm`: The value of `mead_scm` in `releasers.conf`
* `git_ref`: The git reference Tito is trying to build
* `maven_properties`: The value of any `maven_properties` provided as builder arguments
* `maven_options`: The value of any `maven_args` provided as builder arguments

Here's a short example that will ultimately produce an RPM named "app".

```
[org.example-foobar-parent]
scmurl=${mead_scm}#${git_ref}
maven_options=-N ${maven_options}

[org.example-foobar-common]
scmurl=${mead_scm}?common#${git_ref}
buildrequires=org.example-foobar-parent
packages=gettext

[org.example-app]
scmurl=${mead_scm}?app#${git_ref}
buildrequires=org.example-foobar-common

[app]
type=wrapper
scmurl=${mead_scm}?app#${git_ref}
buildrequires=org.example-app
```

During the release process, Tito will check in a rendered version of your
chain file to dist-git (as well as upload a tarball of the source it is
building to the lookaside cache).  It will then fire off a build.
