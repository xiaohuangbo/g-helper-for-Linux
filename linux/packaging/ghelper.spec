Name:           ghelper
Version:        0.292.0
Release:        3%{?dist}
Summary:        Wayland-first ASUS laptop control (G-Helper Linux port)
License:        GPL-3.0-only
URL:            https://github.com/seerge/g-helper
BuildArch:      noarch
Requires:       python3 >= 3.11
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       python3-dbus
Requires:       polkit

%description
G-Helper for Linux. Wayland is preferred and X11 is the fallback. Includes a
StatusNotifier tray, a libadwaita main window, an ASUS ACPI/sysfs backend and
packages for the laptop controls shipped by the Windows app.

%install
make -C %{_sourcedir} install DESTDIR=%{buildroot} PREFIX=/usr

%post
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
  udevadm trigger --subsystem-match=hidraw --subsystem-match=input || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || true
  systemctl enable --now ghelper-helper.service || true
fi

%preun
if [ "$1" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now ghelper-helper.service || true
fi

%files
/usr/bin/ghelper
/usr/bin/ghelper-priv
/usr/lib/ghelper
/usr/share/ghelper
/usr/share/applications/org.ghelper.Linux.desktop
/usr/share/icons/hicolor/scalable/apps/ghelper.svg
/usr/share/polkit-1/actions/org.ghelper.linux.policy
/usr/lib/udev/rules.d/70-ghelper.rules
/usr/lib/systemd/system/ghelper-helper.service
/usr/lib/systemd/user/ghelper.service

%changelog
* Mon Nov 09 2026 G-Helper Linux Port <ghelper@localhost> - 0.292.0-1
- Initial Linux port aligned with G-Helper 0.292.
