{ lib
, stdenv
, python3
, gtk4
, libadwaita
, gobject-introspection
, wrapGAppsHook4
, polkit
, gdk-pixbuf
, glib
}:
stdenv.mkDerivation {
  pname = "ghelper";
  version = "0.292.0";
  src = ./.;

  nativeBuildInputs = [ wrapGAppsHook4 gobject-introspection ];
  buildInputs = [
    gtk4
    libadwaita
    python3
    python3.pkgs.pygobject3
    python3.pkgs.dbus-python
    polkit
    gdk-pixbuf
    glib
  ];

  dontWrapGApps = true;

  installPhase = ''
    runHook preInstall
    make install DESTDIR=$out PREFIX=
    runHook postInstall
  '';

  preFixup = ''
    wrapGApp $out/bin/ghelper
  '';

  meta = with lib; {
    description = "Wayland-first ASUS laptop control (G-Helper Linux port)";
    homepage = "https://github.com/seerge/g-helper";
    license = licenses.gpl3Only;
    platforms = platforms.linux;
    mainProgram = "ghelper";
  };
}
