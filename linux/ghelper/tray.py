"""StatusNotifierItem tray.

Works on KDE Wayland (org.kde.StatusNotifierWatcher) and on X11 desktops
that export the same watcher. The main window does not depend on the tray.
"""

from __future__ import annotations

import os

from ghelper.i18n import t
from ghelper.logutil import get_logger
from ghelper.paths import share_dir

log = get_logger("ghelper.tray")


class Tray:
    def __init__(self, app):
        self.app = app
        self.item = None
        self.menu = None
        self.bus = None
        self.error = ""

    def start(self) -> bool:
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
        except Exception as exc:
            self.error = str(exc)
            return False
        try:
            DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            self.bus = bus
            name = dbus.service.BusName("org.kde.StatusNotifierItem-%d-1" % os.getpid(), bus)
            self.item = _Item(bus, self)
            self.item.props["IconThemePath"] = str(share_dir() / "icons")
            self.item.props["IconName"] = "ghelper"
            self.menu = _Menu(bus, self)
            watcher = dbus.Interface(
                bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher"),
                "org.kde.StatusNotifierWatcher",
            )
            watcher.RegisterStatusNotifierItem(name.get_name())
            self._name = name
            log.info("tray registered as %s", name.get_name())
            return True
        except Exception as exc:
            self.error = str(exc)
            log.warning("tray unavailable: %s", exc)
            return False

    def stop(self) -> None:
        """Drop the StatusNotifier item so the panel does not keep a dead icon."""
        for obj in (self.item, self.menu):
            if obj is None:
                continue
            try:
                obj.remove_from_connection()
            except Exception:
                pass
        self.item = None
        self.menu = None
        name = getattr(self, "_name", None)
        if name is not None:
            try:
                name.get_bus().release_name(name.get_name())
            except Exception:
                pass
        self._name = None
        self.bus = None

    def set_tooltip(self, text: str) -> None:
        if not self.item:
            return
        import dbus
        empty = dbus.Array([], signature="(iiay)")
        self.item.props["ToolTip"] = dbus.Struct(("ghelper", empty, "G-Helper", text), signature="sa(iiay)ss")
        try:
            self.item.NewToolTip()
        except Exception:
            pass


class _Item:
    """Built lazily so dbus is imported only when the tray starts."""

    def __new__(cls, bus, tray: Tray):
        import dbus
        import dbus.service

        class Item(dbus.service.Object):
            def __init__(self, connection, owner: Tray):
                self.owner = owner
                self.props = {
                    "Category": "ApplicationStatus",
                    "Id": "ghelper",
                    "Title": "G-Helper",
                    "Status": "Active",
                    "IconName": "ghelper",
                    "IconThemePath": "",
                    "Menu": dbus.ObjectPath("/StatusNotifierItem/menu"),
                    "ItemIsMenu": False,
                    "ToolTip": dbus.Struct(("ghelper", dbus.Array([], signature="(iiay)"), "G-Helper", "ASUS"), signature="sa(iiay)ss"),
                }
                dbus.service.Object.__init__(self, connection, "/StatusNotifierItem")

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def Activate(self, x, y):
                self.owner.app.toggle_window()

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def SecondaryActivate(self, x, y):
                self.owner.app.cycle_from_tray()

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
            def ContextMenu(self, x, y):
                return

            @dbus.service.method("org.kde.StatusNotifierItem", in_signature="is", out_signature="")
            def Scroll(self, delta, orientation):
                self.owner.app.adjust_backlight(1 if int(delta) > 0 else -1)

            @dbus.service.signal("org.kde.StatusNotifierItem", signature="")
            def NewToolTip(self):
                return

            @dbus.service.signal("org.kde.StatusNotifierItem", signature="")
            def NewIcon(self):
                return

            @dbus.service.signal("org.kde.StatusNotifierItem", signature="s")
            def NewStatus(self, status):
                return

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ss", out_signature="v")
            def Get(self, interface, prop):
                return self.props[prop]

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="s", out_signature="a{sv}")
            def GetAll(self, interface):
                return self.props

            @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature="ssv", out_signature="")
            def Set(self, interface, prop, value):
                self.props[prop] = value

        return Item(bus, tray)


class _Menu:
    def __new__(cls, bus, tray: Tray):
        import dbus
        import dbus.service

        class Menu(dbus.service.Object):
            def __init__(self, connection, owner: Tray):
                self.owner = owner
                self.revision = 1
                dbus.service.Object.__init__(self, connection, "/StatusNotifierItem/menu")

            def _layout(self):
                children = [
                    (1, {"label": t("打开主窗口", "Open window"), "enabled": True}, []),
                    (2, {"type": "separator"}, []),
                    (90, {"label": t("停止服务并退出", "Stop services and quit")}, []),
                ]

                def pack(item, variant: bool = False):
                    iid, props, kids = item
                    # dbus-python has no Variant class; variant_level wraps a
                    # struct inside av. Without this the layout raises
                    # AttributeError and the panel shows no context menu.
                    return dbus.Struct(
                        (
                            dbus.Int32(iid),
                            dbus.Dictionary(props, signature="sv"),
                            dbus.Array([pack(kid, True) for kid in kids], signature="v"),
                        ),
                        signature="ia{sv}av",
                        variant_level=1 if variant else 0,
                    )

                root_children = dbus.Array([pack(child, True) for child in children], signature="v")
                return dbus.Struct(
                    (dbus.Int32(0), dbus.Dictionary({"children-display": "submenu"}, signature="sv"), root_children),
                    signature="ia{sv}av",
                )

            @dbus.service.method("com.canonical.dbusmenu", in_signature="iias", out_signature="u(ia{sv}av)")
            def GetLayout(self, parent, depth, props):
                return dbus.UInt32(self.revision), self._layout()

            @dbus.service.method("com.canonical.dbusmenu", in_signature="isvu", out_signature="")
            def Event(self, item_id, event, data, timestamp):
                if event != "clicked":
                    return
                app = self.owner.app
                iid = int(item_id)
                if iid == 1:
                    app.toggle_window()
                    return
                if iid == 90:
                    app.stop_services_and_quit()

            @dbus.service.method("com.canonical.dbusmenu", in_signature="i", out_signature="b")
            def AboutToShow(self, item_id):
                return False

            @dbus.service.method("com.canonical.dbusmenu", in_signature="aias", out_signature="a(ia{sv})")
            def GetGroupProperties(self, ids, props):
                return dbus.Array([], signature="(ia{sv})")

        return Menu(bus, tray)
