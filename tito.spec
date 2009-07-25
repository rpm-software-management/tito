%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name: tito
Version: 0.0.1
Release:        1%{?dist}
Summary: A tool for managing rpm based git projects

Group: Development/Tools
License: GPLv2
URL: http://rm-rf.ca/tito
Source0: http://rm-rf.ca/files/tito/tito-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch: noarch
BuildRequires: python-devel

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
#%doc AUTHORS
#%doc LICENSE
#%doc README
%{_bindir}/tito
%{_bindir}/bump-version.pl
%{_bindir}/tar-fixup-stamp-comment.pl
%{_bindir}/test-setup-specfile.pl
%dir %{python_sitelib}/spacewalk
%{python_sitelib}/spacewalk/*
%{python_sitelib}/tito-*.egg-info


%changelog
* Wed Jul 22 2009 Devan Goodwin <dgoodwin@rm-rf.ca> 0.0.1-1
- Initial packaging.

