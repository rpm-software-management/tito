Name:           tito-test-pkg
Version:        0.0.1
Release:        1%{?dist}
Summary:        Tito test package.
URL:            https://example.com
Group:          Applications/Internet
License:        GPLv2
BuildRoot:      %{_tmppath}/%{name}-root-%(%{__id_u} -n)
BuildArch:      noarch

%description
Nobody cares.

%prep
#nothing to do here

%build
#nothing to do here

%install
rm -rf $RPM_BUILD_ROOT

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root)

%changelog
