%{!?python2_sitelib: %define python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           extsrc
Version:        0.0.1
Release:        1%{?dist}
Summary:        tito test package for the external source builder
URL:            https://example.com
License:        GPLv2
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

%description
Nobody cares.

%prep

%build

%install

%clean

%files
%defattr(-,root,root)

%changelog
