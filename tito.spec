%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: tito
Version: 0.3.3
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

