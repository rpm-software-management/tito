%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: tito
Version: 0.4.11
Release: 1%{?dist}
Summary: A tool for managing rpm based git projects

Group: Development/Tools
License: GPLv2
URL: http://rm-rf.ca/tito
Source0: http://rm-rf.ca/files/tito/tito-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch
BuildRequires: python-devel
BuildRequires: python-setuptools
BuildRequires: asciidoc
BuildRequires: libxslt

Requires: python-setuptools
Requires: rpm-build
Requires: rpmlint
Requires: GitPython >= 0.2.0
Requires: fedpkg
Requires: fedora-cert
Requires: fedora-packager
Requires: rpmdevtools
Requires: rpm-python
Requires: yum-utils

%description
Tito is a tool for managing tarballs, rpms, and builds for projects using
git.

%prep
%setup -q -n tito-%{version}


%build
%{__python} setup.py build
# convert manages
a2x -d manpage -f manpage titorc.5.asciidoc
a2x -d manpage -f manpage tito.8.asciidoc
a2x -d manpage -f manpage tito.props.5.asciidoc
a2x -d manpage -f manpage releasers.conf.5.asciidoc

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT
rm -f $RPM_BUILD_ROOT%{python_sitelib}/*egg-info/requires.txt
# manpages
%{__mkdir_p} %{buildroot}%{_mandir}/man5
%{__mkdir_p} %{buildroot}%{_mandir}/man8
%{__gzip} -c titorc.5 > %{buildroot}/%{_mandir}/man5/titorc.5.gz
%{__gzip} -c tito.8 > %{buildroot}/%{_mandir}/man8/tito.8.gz
%{__gzip} -c tito.props.5 > %{buildroot}/%{_mandir}/man5/tito.props.5.gz
%{__gzip} -c releasers.conf.5 > %{buildroot}/%{_mandir}/man5/releasers.conf.5.gz
%{__gzip} -c build.py.props.5 > %{buildroot}/%{_mandir}/man5/build.py.props.5.gz

%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README.mkd AUTHORS COPYING
%doc %{_mandir}/man5/titorc.5.gz
%doc %{_mandir}/man5/tito.props.5.gz
%doc %{_mandir}/man5/releasers.conf.5.gz
%doc %{_mandir}/man5/build.py.props.5.gz
%doc %{_mandir}/man8/tito.8.gz
%{_bindir}/tito
%{_bindir}/tar-fixup-stamp-comment.pl
%{_bindir}/test-setup-specfile.pl
%{_bindir}/generate-patches.pl
%dir %{python_sitelib}/tito
%{python_sitelib}/tito/*
%{python_sitelib}/tito-*.egg-info


%changelog
* Thu Jan 17 2013 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.11-1
- add a --scratch option for KojiReleaser (aronparsons@gmail.com)
- Fix no_build error in KojiReleaser.

* Wed Nov 28 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.10-1
- Add --no-build; this will allow scripted DistGit commits and
  koji/brew chain-builds (admiller@redhat.com)
- Added gembuilder, cleaned up pep8 (admiller@redhat.com)
- Add a Travis configuration (jbowes@repl.ca)
- Update README.mkd (misc@zarb.org)
- fix: RsyncReleaser doesn't handle multiple rsync locations
  (jesusr@redhat.com)
- remove tabs and trailing whitespace. add whitespace between methods
  (jesusr@redhat.com)
- Handle stderr noise getting from remote server (inecas@redhat.com)
- Can now specify a build target for fedora and distgit releasers
  (mstead@redhat.com)

* Tue Sep 04 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.9-1
- Stop passing --installdeps for mock builds. (dgoodwin@redhat.com)
- YumRepoReleaser feature: createrepo command can now be specified from
  releasers.conf with the 'createrepo_command' config option
  (palli@opensource.is)
- Created new releaser called RsyncReleaser. Based heavily on YumRepoReleaser.
  Refactored YumRepoReleaser to inherit most code from RsyncReleaser.
  (palli@opensource.is)
- Optionally print stacktrace whenever error_out is hit (bleanhar@redhat.com)
- encourage users to push only their new tag (jbowes@redhat.com)
- Attempt to copy local Sources during releases. (dgoodwin@redhat.com)

* Mon Apr 02 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.8-1
- Fix MockBuilder for packages that use non-standard builders normally.
  (dgoodwin@redhat.com)
- interpret '0' as False for changelog_with_email setting. (msuchy@redhat.com)

* Thu Mar 15 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.7-1
- Fix issues with DistributionBuilder constructor (dgoodwin@redhat.com)

* Wed Mar 14 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.6-1
- Issue 39: Create /tmp/tito if it doesn't already exist. (dgoodwin@redhat.com)
- Add support for test build releases. (dgoodwin@redhat.com)
- Stop passing all CLI args to builders. (dgoodwin@redhat.com)
- Add mock builder speedup argument. (mstead@redhat.com)
- Add support for no-value args in builder. (mstead@redhat.com)
- Fix rsync options for yum repo releases. (jesusr@redhat.com)
- Add support for customizable changelog formats (jeckersb@redhat.com)

* Tue Jan 24 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.5-1
- Extract bz's and prompt to modify commit message in git releasers.
  (dgoodwin@redhat.com)

* Mon Jan 23 2012 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.4-1
- Issue #35: EDITOR with arguments produces backtrace (jeckersb@redhat.com)
- remove unused fedora_cert reading (jesusr@redhat.com)
- Drop to shell when dist-git merge errors encountered. (dgoodwin@redhat.com)
- Use proper temp dirs for releasing. (dgoodwin@redhat.com)
- Fix git release diff command. (dgoodwin@redhat.com)

* Thu Dec 15 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.3-1
- Escape percent character in changelog. (msuchy@redhat.com)
- Fix distribution builder missing args in constructor.
  (msuchy@redhat.com)
- Add release to usage, alphabetize list. (jesusr@redhat.com)
- PEP8 cleanup. (jesusr@redhat.com)
- No need to maintain timestamps: remove -t and -O from rsync command.
  (jesusr@redhat.com)
- Chdir to yum_temp_dir after creating, avoids rsync's getcwd error
  (jesusr@redhat.com)
- Use -O during rsync commands to fix time setting errors. (dgoodwin@rm-rf.ca)

* Mon Nov 28 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.2-1
- Clean out old versions of RPMs when generating yum repos. (dgoodwin@rm-rf.ca)
- Update manpage to show multiple rsync paths. (dgoodwin@rm-rf.ca)

* Fri Nov 25 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.1-1
- Allow one build to go to multiple yum repo URLs. (dgoodwin@redhat.com)
- Fix --no-cleanup for release module. (dgoodwin@redhat.com)
- Add a BrewDownloadBuilder. (dgoodwin@redhat.com)
- Use proper temp directories to build. (dgoodwin@redhat.com)
- Fix permissions when rsync'ing yum repositories. (dgoodwin@redhat.com)
- Switch to CLI fedpkg command instead of module. (dgoodwin@rm-rf.ca)

* Wed Nov 09 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.4.0-1
- Fix import error with new fedpkg version. (dgoodwin@rm-rf.ca)
- Add a KojiGitReleaser. (dgoodwin@rm-rf.ca)
- Adding --use-version to allow Tito to force a version to use.
  (awood@redhat.com)
- Support SCRATCH=1 env variable for koji releaser. (dgoodwin@rm-rf.ca)
- Support ONLY_TAGS env variable for koji releaser. (dgoodwin@rm-rf.ca)
- List releasers option. (dgoodwin@rm-rf.ca)
- Documentation update. (dgoodwin@rm-rf.ca)
- Allow releaseing to multiple targets at once, and add --all-starting-with.
  (dgoodwin@rm-rf.ca)
- Make auto-install available to all builders. (dgoodwin@rm-rf.ca)
- Allow setting specific builder and passing builder args on CLI. (dgoodwin@rm-
  rf.ca)
- Add new mechanism for passing custom arguments to builders. (dgoodwin@rm-
  rf.ca)
- HACKING tips updated. (dgoodwin@rm-rf.ca)
- Add a rsync username env variable for yum repo releaser. (dgoodwin@rm-rf.ca)
- Restructure release CLI. (dgoodwin@redhat.com)
- Parsing spec files and bumping their versions or releases is now in Python.
  (awood@redhat.com)

* Wed Oct 05 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.3.3-1
- Clarify some initial project layout documentation. (dgoodwin@rm-rf.ca)
- match based on the tag for the package we are building (mmccune@redhat.com)
- Teach tito how to checkout EUS branches (msuchy@redhat.com)
- Remove release parameter from _update_package_metadata() (msuchy@redhat.com)
- Avoid traceback if rpmbuild fails (jumanjiman@gmail.com)
- Make Fedora git builds a little more tolerant if you need to re-run.
  (dgoodwin@redhat.com)
- Fix the binary spew in SOURCES on some weird tags. (dgoodwin@redhat.com)
- Do not print traceback when user lacks write permission (jumanjiman@gmail.com)
- Fix Fedora git releaser to use more reliable commands. (dgoodwin@rm-rf.ca)
- Remove the old tito build --release code. (dgoodwin@rm-rf.ca)
- Allow custom releasers to be loaded and used. (dgoodwin@rm-rf.ca)
- Introduce new CLI module for releases. (dgoodwin@rm-rf.ca)
- Use fedpkg switch branch for git releases. (dgoodwin@rm-rf.ca)
- Do not print traceback when user hit Ctrl+C (msuchy@redhat.com)
- '0' is True, we want it as false (msuchy@redhat.com)

* Tue Apr 26 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.3.2-1
- add debug logging (jesusr@redhat.com)

* Tue Apr 26 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.3.1-1
- flip condition so new files are added and existing files are copied
  (msuchy@redhat.com)
- fix traceback if git_email is not specified (miroslav@suchy.cz)
- Refactor release code out of the builder class. (dgoodwin@rm-rf.ca)
- Configure tito for Fedora git builds. (dgoodwin@rm-rf.ca)
- Complete Fedora git build process. (dgoodwin@rm-rf.ca)
- if remote.origin is not set, assume --offline and print warning, but proceed
  (msuchy@redhat.com)
- Source can be tar.bz2 (msuchy@redhat.com)
- Source can be without number (msuchy@redhat.com)
- add man page for tito.props(5) (msuchy@redhat.com)
- document KOJI_OPTIONS options of titorc (msuchy@redhat.com)
- add option HIDE_EMAIL to .titorc, which will hide your email in first line of
  changelog entry (msuchy@redhat.com)
- pass user_config to tagger class (msuchy@redhat.com)
- issue 18 - do not print TB if user.name, user.email is not set
  (msuchy@redhat.com)
- Upload sources and confirm commit during git release. (dgoodwin@redhat.com)
- First draft of Fedora Git releasing. (dgoodwin@redhat.com)
- Add a --dry-run option for build --release. (dgoodwin@redhat.com)
- Allow user config setting for sub-packages to skip during auto-install.
  (dgoodwin@redhat.com)
- Hookup bugzilla extraction during cvs release. (dgoodwin@redhat.com)
- Plus and dot chars in git email handled correctly now (lzap+git@redhat.com)
- put emails in changelog only if changelog_with_email is set to 1 in
  [globalconfig] section of config (msuchy@redhat.com)
- use _changelog_remove_cherrypick() for rheltagger (msuchy@redhat.com)
- Add code for extracting bugzilla IDs from CVS diff or git log.
  (dgoodwin@redhat.com)
- Prompt user to edit CVS commit messages. (dgoodwin@redhat.com)
- Fix no auto changelog option. (dgoodwin@redhat.com)
- add tagger for Red Hat Enterprise Linux (msuchy@redhat.com)
- Fix test builds in koji. (dgoodwin@rm-rf.ca)
- Documentation update. (dgoodwin@rm-rf.ca)
- Add missing dep on libxslt. (dgoodwin@rm-rf.ca)

* Wed Jan 05 2011 Devan Goodwin <dgoodwin@rm-rf.ca> 0.3.0-1
- implement --only-tags option for builder class (msuchy@redhat.com)
- implement --list-tags option for builder (msuchy@redhat.com)
- add option --scratch to builder class (msuchy@redhat.com)
- do not throw traceback if you hit Ctrl+C during Auto-instaling
  (msuchy@redhat.com)
- allow child taggers to control commit message (msuchy@redhat.com)
- add new tagger: zStreamTagger - bump up release part after dist tag
  (msuchy@redhat.com)
- Better error-reporting when spec file has errors (jumanjiman@gmail.com)
- if we grep rpmbuild output for some string, we have to switch to C locale
  (miroslav@suchy.cz)
- Adding more helpfull error message to show user what is busted
  (mmccune@redhat.com)
- Fix rpm command suggestion for broken specs. (dgoodwin@rm-rf.ca)
- add manpage source: tito(8) (jumanjiman@gmail.com)
- add manpage source: titorc(5) (jumanjiman@gmail.com)
- adding rpm-build as a Requires. Seems pretty critical (mmccune@redhat.com)
- Add missing dep on python-setuptools. (dgoodwin@rm-rf.ca)

* Wed Jun 02 2010 Devan Goodwin <dgoodwin@rm-rf.ca> 0.2.0-1
- Restrict building to a minimum version of tito. (msuchy@redhat.com)
- Added option to pass custom options to rpmbuild. (dgoodwin@rm-rf.ca)
- Add tito-dev script to run directly from source. (dgoodwin@rm-rf.ca)
- Better output after tagging. (dgoodwin@rm-rf.ca)
- Display rpms build on successful completion. (dgoodwin@rm-rf.ca)
- Added tito tag --undo. (dgoodwin@rm-rf.ca)
- Bump versions in setup.py during tagging if possible. (dgoodwin@rm-rf.ca)
- Added lib_dir setting for custom taggers/builders. (dgoodwin@rm-rf.ca)
- Add option to auto-install rpms after build. (dgoodwin@rm-rf.ca)
- Remove check for changelog with today's date. (dgoodwin@rm-rf.ca)
- Allow user to specify an changelog string for new packages.
  (jesusr@redhat.com)
- Use latest commit instead of HEAD for --test. (jesusr@redhat.com)
- Allow tito to understand pkg names with macros. (jesusr@redhat.com)
- Use short sha1 when generating filenames. (jesusr@redhat.com)
- Commit packages dir during tito init. (jesusr@redhat.com)
- More detailed error message if spec has errors. (mmccune@redhat.com)

* Wed Jun 02 2010 Devan Goodwin <dgoodwin@rm-rf.ca>
- Restrict building to a minimal version of tito. (msuchy@redhat.com)
- Added option to pass custom options to rpmbuild. (dgoodwin@rm-rf.ca)
- Add tito-dev script to run directly from source. (dgoodwin@rm-rf.ca)
- Better output after tagging. (dgoodwin@rm-rf.ca)
- Display rpms build on successful completion. (dgoodwin@rm-rf.ca)
- Added tito tag --undo. (dgoodwin@rm-rf.ca)
- Bump versions in setup.py during tagging if possible. (dgoodwin@rm-rf.ca)
- Added lib_dir setting for custom builders/taggers. (dgoodwin@rm-rf.ca)
- Add option to auto-install rpms after build. (dgoodwin@rm-rf.ca)
- Remove check for changelog with today's date. (dgoodwin@rm-rf.ca)
- Allow user to specify an changelog string for new packages.
  (jesusr@redhat.com)
- Use latest commit instead of HEAD for --test. (jesusr@redhat.com)
- Allow tito to understand pkg names with macros. (jesusr@redhat.com)
- Use short sha1 when generating filenames. (jesusr@redhat.com)
- Commit packages dir during tito init. (jesusr@redhat.com)
- More detailed error message if spec is bad. (mmccune@redhat.com)

* Thu Oct 01 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.1.1-2
- Add AUTHORS and COPYING to doc.
- Add BuildRequires on python-setuptools.

* Tue Aug 25 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.1.1-1
- Bumping to 0.1.0 for first release.

* Mon Aug 24 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.0.4-1
- Hack to fix import of tagger/builder on Python 2.4. (dgoodwin@rm-rf.ca)

* Thu Aug 06 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.0.3-1
- Introduce --output option for destination/tmp directory. (dgoodwin@rm-rf.ca)
- Use tito.props for project specific config filename. (dgoodwin@rm-rf.ca)
- Add multi-project repo tagging tests. (dgoodwin@rm-rf.ca)
- Add support for offline (standalone) git repos. (dgoodwin@rm-rf.ca)
- Fix reports for single project git repos. (dgoodwin@rm-rf.ca)
- Add README documentation. (dgoodwin@rm-rf.ca)

* Wed Jul 22 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.0.1-1
- Initial packaging.

