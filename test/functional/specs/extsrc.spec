%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           extsrc
Version:        0.0.1
Release:        1%{?dist}
Summary:        tito test package for the external source builder
URL:            https://example.com
Group:          Applications/Internet
License:        GPLv2
Source0:        %{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-root-%(%{__id_u} -n)
BuildArch:      noarch

%description
Nobody cares.

%prep

%build

%install
rm -rf %{buildroot}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root)
#%dir %{python_sitelib}/%{name}
#%{python_sitelib}/%{name}-*.egg-info

%changelog
