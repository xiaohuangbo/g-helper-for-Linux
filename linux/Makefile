PREFIX ?= /usr
DESTDIR ?=
LIBDIR := $(DESTDIR)$(PREFIX)/lib/ghelper
BINDIR := $(DESTDIR)$(PREFIX)/bin
SHARE := $(DESTDIR)$(PREFIX)/share
APPID := org.ghelper.Linux

.PHONY: install uninstall packages test

install:
	install -d "$(LIBDIR)" "$(BINDIR)" "$(SHARE)/ghelper" "$(SHARE)/applications" 		"$(SHARE)/icons/hicolor/scalable/apps" "$(SHARE)/polkit-1/actions" 		"$(DESTDIR)$(PREFIX)/lib/udev/rules.d" 		"$(DESTDIR)$(PREFIX)/lib/systemd/system" 		"$(DESTDIR)$(PREFIX)/lib/systemd/user"
	cp -a ghelper "$(LIBDIR)/"
	python3 -c 'import pathlib,shutil; root=pathlib.Path("$(LIBDIR)"); [shutil.rmtree(p) for p in list(root.rglob("__pycache__"))]; [p.unlink() for p in list(root.rglob("*.pyc"))]'
	install -m 0755 bin/ghelper "$(BINDIR)/ghelper"
	install -m 0755 bin/ghelper-priv "$(BINDIR)/ghelper-priv"
	cp -a share/. "$(SHARE)/ghelper/"
	install -m 0644 share/applications/$(APPID).desktop "$(SHARE)/applications/$(APPID).desktop"
	install -m 0644 share/icons/hicolor/scalable/apps/ghelper.svg "$(SHARE)/icons/hicolor/scalable/apps/ghelper.svg"
	install -m 0644 share/polkit/org.ghelper.linux.policy "$(SHARE)/polkit-1/actions/org.ghelper.linux.policy"
	install -m 0644 share/udev/70-ghelper.rules "$(DESTDIR)$(PREFIX)/lib/udev/rules.d/70-ghelper.rules"
	install -m 0644 share/systemd/ghelper-helper.service "$(DESTDIR)$(PREFIX)/lib/systemd/system/ghelper-helper.service"
	install -m 0644 share/systemd/ghelper.service "$(DESTDIR)$(PREFIX)/lib/systemd/user/ghelper.service"

uninstall:
	rm -rf "$(LIBDIR)" "$(SHARE)/ghelper"
	rm -f "$(BINDIR)/ghelper" "$(BINDIR)/ghelper-priv"
	rm -f "$(SHARE)/applications/$(APPID).desktop"
	rm -f "$(SHARE)/icons/hicolor/scalable/apps/ghelper.svg"
	rm -f "$(SHARE)/polkit-1/actions/org.ghelper.linux.policy"
	rm -f "$(DESTDIR)$(PREFIX)/lib/udev/rules.d/70-ghelper.rules"
	rm -f "$(DESTDIR)$(PREFIX)/lib/systemd/system/ghelper-helper.service"
	rm -f "$(DESTDIR)$(PREFIX)/lib/systemd/user/ghelper.service"

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v

packages:
	python3 packaging/build_all.py
