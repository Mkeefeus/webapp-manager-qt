Name:           webapp-manager-qt
Version:        0.1.2
Release:        1%{?dist}
Summary:        Run websites as if they were apps

License:        GPL-3.0-or-later
URL:            https://github.com/mkeefeus/webapp-manager-qt
Source0:        https://github.com/mkeefeus/%{name}/releases/download/%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  gettext
BuildRequires:  desktop-file-utils
BuildRequires:  make

Requires:       python3
Requires:       python3-pyside6
Requires:       python3-requests
Requires:       python3-pillow
Requires:       python3-beautifulsoup4
Requires:       python3-setproctitle
Requires:       python3-tldextract

%description
Run websites as if they were apps. This is a Qt version of the Linux Mint webapp-manager
that allows you to create desktop entries for web applications that run in
isolated browser profiles.

%prep
%autosetup

# Replace version placeholder
sed -i 's/@VERSION@/%{version}/g' usr/lib/webapp-manager/webapp-manager.py

%build
# Build translation files
make buildmo

%install
# Create directory structure
install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_datadir}/applications
install -d %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
install -d %{buildroot}%{_datadir}/icons/hicolor/scalable/categories
install -d %{buildroot}%{_datadir}/%{name}
install -d %{buildroot}%{_datadir}/%{name}/firefox/profile/chrome
install -d %{buildroot}%{_prefix}/lib/%{name}

# Install executable
install -m 755 usr/bin/webapp-manager %{buildroot}%{_bindir}/

# Install Python modules
install -m 644 usr/lib/webapp-manager/common.py %{buildroot}%{_prefix}/lib/%{name}/
install -m 755 usr/lib/webapp-manager/webapp-manager.py %{buildroot}%{_prefix}/lib/%{name}/

# Install desktop file
desktop-file-install --dir=%{buildroot}%{_datadir}/applications \
    usr/share/applications/webapp-manager.desktop

# Install Firefox profile files
install -m 644 usr/share/webapp-manager/firefox/userChrome-with-navbar.css \
    %{buildroot}%{_datadir}/%{name}/firefox/
install -m 644 usr/share/webapp-manager/firefox/profile/search.json.mozlz4 \
    %{buildroot}%{_datadir}/%{name}/firefox/profile/
install -m 644 usr/share/webapp-manager/firefox/profile/user.js \
    %{buildroot}%{_datadir}/%{name}/firefox/profile/
install -m 644 usr/share/webapp-manager/firefox/profile/chrome/userChrome.css \
    %{buildroot}%{_datadir}/%{name}/firefox/profile/chrome/

# Install icons
for size in scalable; do
    if [ -d usr/share/icons/hicolor/$size/apps ]; then
        cp -r usr/share/icons/hicolor/$size/apps/* \
            %{buildroot}%{_datadir}/icons/hicolor/$size/apps/ || true
    fi
    if [ -d usr/share/icons/hicolor/$size/categories ]; then
        cp -r usr/share/icons/hicolor/$size/categories/* \
            %{buildroot}%{_datadir}/icons/hicolor/$size/categories/ || true
    fi
done

# Install translations
cp -r usr/share/locale %{buildroot}%{_datadir}/

%files
%license LICENSE
%doc README.md
%{_bindir}/webapp-manager
%{_prefix}/lib/%{name}/
%{_datadir}/applications/webapp-manager.desktop
%{_datadir}/%{name}/
%{_datadir}/icons/hicolor/scalable/apps/*
%{_datadir}/icons/hicolor/scalable/categories/*
%{_datadir}/locale/*/LC_MESSAGES/webapp-manager.mo

%changelog
* Fri Nov 29 2024 Your Name <your.email@example.com> - 1.0.0-1
- Initial release
