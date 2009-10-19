%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: tito
Version: 0.1.1
Release:        2%{?dist}
Summary: A tool for managing rpm based git projects

Group: Development/Tools
License: GPLv2
URL: http://rm-rf.ca/tito
Source0: http://rm-rf.ca/files/tito/tito-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch
BuildRequires: python-devel
BuildRequires: python-setuptools

%description
Tito is a tool for managing tarballs, rpms, and builds for projects using
git.

%prep
%setup -q -n tito-%{version}


%build
%{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT
rm -f $RPM_BUILD_ROOT%{python_sitelib}/*egg-info/requires.txt


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README.mkd AUTHORS COPYING
%{_bindir}/tito
%{_bindir}/bump-version.pl
%{_bindir}/tar-fixup-stamp-comment.pl
%{_bindir}/test-setup-specfile.pl
%dir %{python_sitelib}/tito
%{python_sitelib}/tito/*
%{python_sitelib}/tito-*.egg-info


%changelog
* Mon Oct 19 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.1.1-2
- Fix spec file issues for Fedora inclusion.

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

