#!/usr/bin/env python3
"""Build .deb, .rpm and .pkg.tar.zst without distro packaging tools.

Nix is linux/flake.nix. Fedora can also use packaging/ghelper.spec, and Arch
can use packaging/arch/PKGBUILD.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import shutil
import struct
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
VERSION = "0.292.0"
RELEASE = "3"
NAME = "ghelper"
AR_TERM = bytes([96, 10])

POSTINST = """#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
  udevadm trigger --subsystem-match=hidraw --subsystem-match=input || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload || true
  systemctl enable --now ghelper-helper.service || true
fi
"""


def stage() -> Path:
    dest = DIST / "stage"
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(["make", "install", "DESTDIR=" + str(dest), "PREFIX=/usr"], cwd=ROOT, check=True)
    return dest


def iter_files(root: Path) -> list[tuple[str, bytes, int]]:
    found = []
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            mode = 0o100755 if full.stat().st_mode & 0o111 else 0o100644
            found.append((rel, full.read_bytes(), mode))
    return sorted(found)


def tar_gz(members: list[tuple[str, bytes, int]], prefix: str = "./") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        dirs = set()
        for rel, _data, _mode in members:
            parts = Path(rel).parts[:-1]
            acc: list[str] = []
            for part in parts:
                acc.append(part)
                dirs.add("/".join(acc))
        for rel in sorted(dirs):
            info = tarfile.TarInfo(prefix + rel)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = 1760000000
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info)
        for rel, data, mode in members:
            info = tarfile.TarInfo(prefix + rel)
            info.size = len(data)
            info.mode = mode & 0o777
            info.mtime = 1760000000
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=1760000000) as gz:
        gz.write(buf.getvalue())
    return out.getvalue()


def _ar_field(value: bytes, width: int) -> bytes:
    return value.ljust(width, b" ")[:width]


def ar_archive(members: list[tuple[str, bytes]]) -> bytes:
    blob = bytearray(b"!<arch>\n")
    for name, data in members:
        header = b"".join([
            _ar_field(name.encode(), 16),
            _ar_field(b"1760000000", 12),
            _ar_field(b"0", 6),
            _ar_field(b"0", 6),
            _ar_field(b"100644", 8),
            _ar_field(str(len(data)).encode(), 10),
            AR_TERM,
        ])
        if len(header) != 60:
            raise RuntimeError("bad ar header")
        blob += header
        blob += data
        if len(data) % 2:
            blob += b"\n"
    return bytes(blob)


def build_deb(files: list[tuple[str, bytes, int]], dest: Path) -> None:
    control = (
        "Package: ghelper\n"
        "Version: %s-%s\n"
        "Section: utils\n"
        "Priority: optional\n"
        "Architecture: all\n"
        "Maintainer: G-Helper Linux Port <ghelper@localhost>\n"
        "Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, python3-dbus, polkitd | policykit-1\n"
        "Recommends: gtk-layer-shell | libgtk-layer-shell0\n"
        "Homepage: https://github.com/seerge/g-helper\n"
        "Description: Wayland-first ASUS laptop control\n"
        " G-Helper Linux port with a tray, a main window and an X11 fallback.\n"
    ) % (VERSION, RELEASE)
    control = control.encode()
    md5 = "".join("%s  %s\n" % (hashlib.md5(data).hexdigest(), rel) for rel, data, _mode in files).encode()
    control_tar = tar_gz([
        ("control", control, 0o100644),
        ("md5sums", md5, 0o100644),
        ("postinst", POSTINST.encode(), 0o100755),
    ])
    data_tar = tar_gz(files)
    deb = ar_archive([
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", control_tar),
        ("data.tar.gz", data_tar),
    ])
    dest.write_bytes(deb)


def _i16(value: int) -> bytes:
    return struct.pack(">H", value & 0xFFFF)


def _i32(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFFFF)


class _Header:
    def __init__(self) -> None:
        self.entries: list[tuple[int, int, bytes, int]] = []

    def add(self, tag: int, typ: int, data: bytes, count: int) -> None:
        self.entries.append((tag, typ, data, count))

    def string(self, tag: int, value: str) -> None:
        self.add(tag, 6, value.encode() + b"\x00", 1)

    def int32(self, tag: int, value: int) -> None:
        self.add(tag, 4, _i32(value), 1)

    def strings(self, tag: int, values: list[str]) -> None:
        raw = b"".join(item.encode() + b"\x00" for item in values)
        self.add(tag, 8, raw, len(values))

    def binary(self, tag: int, data: bytes) -> None:
        self.add(tag, 7, data, len(data))

    def render(self) -> bytes:
        store = bytearray()
        index = []
        for tag, typ, data, count in sorted(self.entries, key=lambda item: item[0]):
            align = {3: 2, 4: 4, 5: 8}.get(typ, 1)
            pad = (align - (len(store) % align)) % align
            store += b"\x00" * pad
            offset = len(store)
            store += data
            index.append(struct.pack(">iiii", tag, typ, offset, count))
        body = b"\x8e\xad\xe8\x01\x00\x00\x00\x00"
        body += struct.pack(">III", 0, len(index), len(store))
        body += b"".join(index)
        body += bytes(store)
        return body


def cpio_newc(entries: list[tuple[str, bytes, int]]) -> bytes:
    blob = bytearray()
    inode = 1
    dirs: set[str] = set()
    for rel, _data, _mode in entries:
        parent = str(Path(rel).parent)
        while parent not in ("", "."):
            dirs.add(parent)
            parent = str(Path(parent).parent)
    ordered = [(directory, b"", 0o040755) for directory in sorted(dirs)]
    ordered.extend(entries)

    def emit(name: str, data: bytes, mode: int) -> None:
        nonlocal inode
        name_b = name.encode() + b"\x00"
        nlink = 2 if mode & 0o040000 else 1
        fields = [inode, mode, 0, 0, nlink, 1760000000, len(data), 0, 0, 0, 0, len(name_b), 0]
        header = b"070701" + b"".join(b"%08X" % field for field in fields)
        blob.extend(header)
        blob.extend(name_b)
        blob.extend(b"\x00" * ((4 - (len(name_b) % 4)) % 4))
        blob.extend(data)
        blob.extend(b"\x00" * ((4 - (len(data) % 4)) % 4))
        inode += 1

    for name, data, mode in ordered:
        emit(name, data, mode)
    emit("TRAILER!!!", b"", 0)
    return bytes(blob)


def build_rpm(files: list[tuple[str, bytes, int]], dest: Path) -> None:
    cpio = cpio_newc(files)
    payload = gzip.compress(cpio, mtime=1760000000)
    now = int(time.time())
    dirnames: list[str] = []
    dir_index: dict[str, int] = {}
    basenames = []
    indexes = []
    modes = []
    sizes = []
    mtimes = []
    digests = []
    links = []
    users = []
    groups = []
    inodes = []
    langs = []
    for n, (rel, data, mode) in enumerate(files, start=1):
        parent = "/" + str(Path(rel).parent)
        dirname = "/" if parent == "/." else (parent if parent.endswith("/") else parent + "/")
        if dirname not in dir_index:
            dir_index[dirname] = len(dirnames)
            dirnames.append(dirname)
        basenames.append(Path(rel).name)
        indexes.append(dir_index[dirname])
        modes.append(mode)
        sizes.append(len(data))
        mtimes.append(now)
        digests.append(hashlib.md5(data).hexdigest())
        links.append("")
        users.append("root")
        groups.append("root")
        inodes.append(n)
        langs.append("")
    header = _Header()
    header.string(1000, NAME)
    header.string(1001, VERSION)
    header.string(1002, RELEASE)
    header.string(1004, "Wayland-first ASUS laptop control")
    header.string(1005, "G-Helper Linux port. Wayland first, X11 fallback.")
    header.int32(1006, now)
    header.string(1007, "localhost")
    header.int32(1009, sum(sizes))
    header.string(1014, "GPL-3.0-only")
    header.string(1016, "System Environment/Base")
    header.string(1021, "linux")
    header.string(1022, "noarch")
    header.add(1028, 4, b"".join(_i32(size) for size in sizes), len(sizes))
    header.add(1030, 3, b"".join(_i16(mode) for mode in modes), len(modes))
    header.add(1033, 4, b"".join(_i32(0) for _item in files), len(files))
    header.add(1034, 4, b"".join(_i32(stamp) for stamp in mtimes), len(mtimes))
    header.strings(1035, digests)
    header.strings(1036, links)
    header.add(1037, 4, b"".join(_i32(0) for _item in files), len(files))
    header.strings(1039, users)
    header.strings(1040, groups)
    header.string(1044, "%s-%s-%s.src.rpm" % (NAME, VERSION, RELEASE))
    header.string(1064, "4.18.0")
    header.add(1095, 4, b"".join(_i32(0) for _item in files), len(files))
    header.add(1096, 4, b"".join(_i32(n) for n in inodes), len(inodes))
    header.strings(1097, langs)
    header.add(1116, 4, b"".join(_i32(n) for n in indexes), len(indexes))
    header.strings(1117, basenames)
    header.strings(1118, dirnames)
    header.string(1124, "cpio")
    header.string(1125, "gzip")
    header.string(1126, "9")
    header.int32(5011, 1)
    main = header.render()
    sig = _Header()
    sig.int32(1000, len(main) + len(payload))
    sig.binary(1004, hashlib.md5(main + payload).digest())
    sig.int32(1007, len(cpio))
    signature = sig.render()
    signature += b"\x00" * ((8 - (len(signature) % 8)) % 8)
    lead = bytearray(96)
    lead[0:4] = bytes([0xED, 0xAB, 0xEE, 0xDB])
    lead[4] = 3
    struct.pack_into(">h", lead, 6, 0)
    struct.pack_into(">h", lead, 8, 0)
    pkg = ("%s-%s-%s" % (NAME, VERSION, RELEASE)).encode()[:65]
    lead[10:10 + len(pkg)] = pkg
    struct.pack_into(">h", lead, 76, 1)
    struct.pack_into(">h", lead, 78, 5)
    dest.write_bytes(bytes(lead) + signature + main + payload)


def build_arch(files: list[tuple[str, bytes, int]], dest: Path) -> None:
    lines = [
        "pkgname = ghelper",
        "pkgbase = ghelper",
        "pkgver = %s-%s" % (VERSION, RELEASE),
        "pkgdesc = Wayland-first ASUS laptop control (G-Helper Linux port)",
        "url = https://github.com/seerge/g-helper",
        "builddate = %d" % int(time.time()),
        "packager = G-Helper Linux Port",
        "size = %d" % sum(len(data) for _rel, data, _mode in files),
        "arch = any",
        "license = GPL-3.0-only",
        "depend = python",
        "depend = gtk4",
        "depend = libadwaita",
        "depend = python-gobject",
        "depend = python-dbus",
        "depend = polkit",
        "optdepend = gtk4-layer-shell: Wayland metrics overlay",
    ]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        pkginfo = ("\n".join(lines) + "\n").encode()
        info = tarfile.TarInfo(".PKGINFO")
        info.size = len(pkginfo)
        info.mode = 0o644
        info.mtime = 1760000000
        tar.addfile(info, io.BytesIO(pkginfo))
        install = (
            "post_install() {\n"
            "  udevadm control --reload-rules || true\n"
            "  udevadm trigger --subsystem-match=hidraw --subsystem-match=input || true\n"
            "  systemctl daemon-reload || true\n"
            "  systemctl enable --now ghelper-helper.service || true\n"
            "}\n"
            "post_upgrade() { post_install; }\n"
        ).encode()
        hook = tarfile.TarInfo(".INSTALL")
        hook.size = len(install)
        hook.mode = 0o644
        hook.mtime = 1760000000
        tar.addfile(hook, io.BytesIO(install))
        for rel, data, mode in files:
            item = tarfile.TarInfo(rel)
            item.size = len(data)
            item.mode = mode & 0o777
            item.mtime = 1760000000
            item.uid = item.gid = 0
            item.uname = item.gname = "root"
            tar.addfile(item, io.BytesIO(data))
    zstd = shutil.which("zstd")
    if not zstd:
        raise SystemExit("zstd is required to build .pkg.tar.zst")
    proc = subprocess.run([zstd, "-c", "-T1", "-19"], input=buf.getvalue(), capture_output=True, check=True)
    dest.write_bytes(proc.stdout)


def main() -> None:
    DIST.mkdir(exist_ok=True)
    files = iter_files(stage())
    deb = DIST / ("ghelper_%s-%s_all.deb" % (VERSION, RELEASE))
    rpm = DIST / ("ghelper-%s-%s.noarch.rpm" % (VERSION, RELEASE))
    arch = DIST / ("ghelper-%s-%s-any.pkg.tar.zst" % (VERSION, RELEASE))
    build_deb(files, deb)
    build_rpm(files, rpm)
    build_arch(files, arch)
    print(deb)
    print(rpm)
    print(arch)


if __name__ == "__main__":
    main()
