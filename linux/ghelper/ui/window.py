from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ghelper import __version__
from ghelper.i18n import language, set_language, t
from ghelper.pages import PAGES
from ghelper.peripherals.battery import format_battery
from ghelper.paths import config_dir
from ghelper.priv import spawn_helper
from ghelper.updates import asus_bios, fwupd_summary

def _format_device(device: dict, info: dict | None) -> str:
    return "%s %04X %s  |  %s" % (
        device.get("kind") or "hid",
        int(device.get("pid") or 0),
        device.get("name") or "ASUS",
        format_battery(info),
    )


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, controller):
        super().__init__(application=app, title="G-Helper")
        self.app_ref = app
        self.ctrl = controller
        self.brightness_percent = 40
        self._labels = {}
        self._built = False
        self.set_default_size(1120, 760)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        header = Adw.HeaderBar()
        self.subtitle = Gtk.Label(label="Linux", css_classes=["gh-muted"])
        header.set_title_widget(self._title())
        header.pack_end(self.subtitle)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        sidebar = Gtk.ListBox()
        sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sidebar.add_css_class("navigation-sidebar")
        self._sidebar = sidebar
        self._page_rows = {}
        for page_id, zh, en in PAGES:
            row = Gtk.ListBoxRow()
            row.page_id = page_id
            label = Gtk.Label(label=t(zh, en), xalign=0, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
            row.set_child(label)
            sidebar.append(row)
            self._page_rows[page_id] = row
            self.stack.add_named(self._page(page_id), page_id)
        sidebar.connect("row-selected", self._on_nav)
        sidebar.select_row(sidebar.get_row_at_index(0))

        split = Adw.NavigationSplitView()
        side_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        brand = Gtk.Label(label="G-Helper", margin_top=16, margin_bottom=8, css_classes=["gh-hero"])
        side_box.append(brand)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(sidebar)
        side_box.append(scroll)
        split.set_sidebar(Adw.NavigationPage(child=side_box, title="G-Helper"))
        split.set_content(Adw.NavigationPage(child=self.stack, title="G-Helper"))
        split.set_min_sidebar_width(196)
        split.set_max_sidebar_width(240)
        split.set_show_content(True)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(split)
        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)
        self._built = True
        self.refresh()

    def _title(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Gtk.Label(label="G-Helper", css_classes=["gh-hero"]))
        box.append(Gtk.Label(label=t("华硕笔记本控制 · Linux", "ASUS laptop control for Linux"), css_classes=["gh-muted"]))
        return box

    def toast(self, text: str) -> None:
        if not text:
            return
        self.toasts.add_toast(Adw.Toast(title=text[:180], timeout=4))

    def note_hotkey(self, code: int, name: str) -> None:
        label = self._labels.get("hotkey")
        if label:
            label.set_label("%s (%s)" % (name, code))

    def refresh(self, snap: dict | None = None) -> None:
        if not self._built:
            return
        if snap is None:
            try:
                snap = self.ctrl.snapshot()
            except Exception as exc:
                self.toast(str(exc))
                return
        self._fill(snap)

    def _on_nav(self, box, row):
        if row is None:
            return
        self.stack.set_visible_child_name(row.page_id)

    def switch_page(self, page_id: str) -> bool:
        row = self._page_rows.get(page_id)
        if row is None:
            return False
        self._sidebar.select_row(row)
        self.stack.set_visible_child_name(page_id)
        return True

    def _page(self, page_id: str) -> Gtk.Widget:
        builders = {
            "overview": self._overview,
            "fans": self._fans,
            "gpu": self._gpu,
            "keyboard": self._keyboard,
            "battery": self._battery,
            "display": self._display,
            "peripherals": self._peripherals,
            "hotkeys": self._hotkeys,
            "updates": self._updates,
            "acpi": self._acpi,
            "settings": self._settings,
        }
        body = builders[page_id]()
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(body)
        return scroll

    def _group(self, title: str) -> tuple[Adw.PreferencesGroup, Adw.PreferencesPage]:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=title)
        page.add(group)
        return group, page

    def _overview(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        info = Adw.PreferencesGroup(title=t("本机", "Machine"))
        self._labels["product"] = self._row(info, t("型号", "Model"), "-")
        self._labels["backend"] = self._row(info, t("显示后端", "Display backend"), "-")
        self._labels["helper"] = self._row(info, t("特权助手", "Privileged helper"), "-")
        page.add(info)
        live = Adw.PreferencesGroup(title=t("状态", "Status"))
        self._labels["mode"] = self._row(live, t("性能模式", "Performance"), "-")
        self._labels["temp"] = self._row(live, t("CPU 温度", "CPU temperature"), "-")
        self._labels["fan"] = self._row(live, t("风扇", "Fans"), "-")
        self._labels["battery"] = self._row(live, t("电池", "Battery"), "-")
        self._labels["peri-bat"] = self._row(live, t("外设电量", "Peripheral battery"), "-")
        page.add(live)
        modes = Adw.PreferencesGroup(title=t("性能模式", "Performance modes"))
        box = Gtk.Box(spacing=8, margin_top=6, margin_bottom=6)
        for mode, zh, en in (("silent", "静音", "Silent"), ("balanced", "平衡", "Balanced"), ("turbo", "增强", "Turbo")):
            button = Gtk.Button(label=t(zh, en))
            button.connect("clicked", lambda _b, value=mode: self._apply_mode(value))
            box.append(button)
            self._labels["btn-" + mode] = button
        modes.add(box)
        auth = Gtk.Button(label=t("授权硬件写入", "Authorize hardware writes"))
        auth.connect("clicked", lambda _b: self._authorize())
        modes.add(auth)
        quit_btn = Gtk.Button(label=t("退出并停止全部服务", "Quit and stop all services"))
        quit_btn.connect("clicked", lambda _b: self.app_ref.quit())
        modes.add(quit_btn)
        page.add(modes)
        return page

    def _fans(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("风扇曲线", "Fan curves"))
        self._labels["fan-detail"] = self._row(group, t("检测到的风扇", "Detected fans"), "-")
        self._fan_spins = []
        grid = Gtk.Grid(column_spacing=8, row_spacing=6, margin_top=8)
        grid.attach(Gtk.Label(label=t("温度", "Temp")), 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=t("占空比 %", "Duty %")), 2, 0, 1, 1)
        for index in range(8):
            grid.attach(Gtk.Label(label=str(index + 1)), 0, index + 1, 1, 1)
            temp = Gtk.SpinButton.new_with_range(20, 100, 1)
            duty = Gtk.SpinButton.new_with_range(0, 100, 1)
            temp.set_value(30 + index * 8)
            duty.set_value(index * 12)
            grid.attach(temp, 1, index + 1, 1, 1)
            grid.attach(duty, 2, index + 1, 1, 1)
            self._fan_spins.append((temp, duty))
        group.add(grid)
        self._fan_id = Gtk.Entry(placeholder_text="cpu / gpu / mid")
        self._fan_id.set_text("mid")
        group.add(self._fan_id)
        apply = Gtk.Button(label=t("应用风扇曲线", "Apply fan curve"))
        apply.connect("clicked", lambda _b: self._apply_curve())
        group.add(apply)
        note = Gtk.Label(label=t(
            "曲线写入内核 hwmon 的 pwm auto point。没有这些节点的机型会保持只读，避免误写。",
            "Curves are written to kernel hwmon pwm auto-points. Machines without those nodes stay read-only.",
        ), wrap=True, xalign=0, css_classes=["gh-muted"])
        group.add(note)
        page.add(group)
        limits = Adw.PreferencesGroup(title=t("固件功耗属性", "Firmware power attributes"))
        self._labels["attrs"] = Gtk.Label(label="-", wrap=True, xalign=0)
        limits.add(self._labels["attrs"])
        page.add(limits)
        return page

    def _gpu(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("显卡模式", "GPU mode"))
        self._labels["gpu"] = self._row(group, t("能力", "Capability"), "-")
        box = Gtk.Box(spacing=8)
        for mode, zh, en in (("eco", "集显", "Eco"), ("standard", "标准", "Standard"), ("ultimate", "独显直连", "Ultimate"), ("optimized", "自动优化", "Optimized")):
            button = Gtk.Button(label=t(zh, en))
            button.connect("clicked", lambda _b, value=mode: self._apply_gpu(value))
            box.append(button)
        group.add(box)
        page.add(group)
        return page

    def _keyboard(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("键盘背光", "Keyboard backlight"))
        self._labels["kbd"] = self._row(group, t("当前", "Current"), "-")
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 3, 1)
        scale.set_draw_value(True)
        scale.connect("value-changed", self._kbd_changed)
        self._kbd_scale = scale
        group.add(scale)
        page.add(group)
        aura = Adw.PreferencesGroup(title="Aura")
        aura.add(Gtk.Label(label=t(
            "笔记本 RGB 走 ASUS HID 0x5d。未检测到 Aura 设备时只提供背光亮度，这和原版对 Vivobook / TUF 白光键盘的行为一致。",
            "Laptop RGB uses ASUS HID report 0x5d. Without an Aura device only backlight brightness is offered, matching G-Helper on white-backlight Vivobook and TUF machines.",
        ), wrap=True, xalign=0))
        page.add(aura)
        return page

    def _battery(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("充电上限", "Charge limit"))
        self._labels["charge"] = self._row(group, t("状态", "Status"), "-")
        adj = Gtk.Adjustment(value=80, lower=20, upper=100, step_increment=1, page_increment=5)
        spin = Adw.SpinRow(adjustment=adj, title=t("上限 %", "Limit %"))
        self._charge_spin = spin
        group.add(spin)
        button = Gtk.Button(label=t("应用充电上限", "Apply charge limit"))
        button.connect("clicked", lambda _b: self._apply_charge())
        group.add(button)
        page.add(group)
        auto = Adw.PreferencesGroup(title=t("插电 / 电池自动化", "AC / battery automation"))
        self._auto_switch = Adw.SwitchRow(title=t("自动切换性能模式", "Switch performance mode automatically"))
        self._auto_switch.set_active(bool(self.ctrl.config.data.get("automation", {}).get("enabled", True)))
        self._auto_switch.connect("notify::active", self._auto_toggled)
        auto.add(self._auto_switch)
        page.add(auto)
        return page

    def _display(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("亮度与刷新率", "Brightness and refresh"))
        self._labels["display"] = self._row(group, t("输出", "Outputs"), "-")
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 100, 1)
        scale.set_value(40)
        scale.connect("value-changed", self._brightness_changed)
        self._bright_scale = scale
        group.add(scale)
        self._output_entry = Gtk.Entry(placeholder_text="eDP-1")
        self._mode_entry = Gtk.Entry(placeholder_text="2560x1600@165")
        group.add(self._output_entry)
        group.add(self._mode_entry)
        button = Gtk.Button(label=t("应用刷新率", "Apply refresh rate"))
        button.connect("clicked", lambda _b: self._apply_refresh())
        group.add(button)
        page.add(group)
        return page

    def _peripherals(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("已识别的华硕设备", "Detected ASUS devices"))
        self._labels["peri"] = Gtk.Label(label="-", wrap=True, xalign=0)
        group.add(self._labels["peri"])
        self._peri_level = Gtk.LevelBar()
        self._peri_level.set_min_value(0)
        self._peri_level.set_max_value(100)
        self._peri_level.set_value(0)
        group.add(self._peri_level)
        refresh = Gtk.Button(label=t("刷新外设电量", "Refresh peripheral battery"))
        refresh.connect("clicked", lambda _b: self.ctrl.batteries.refresh_now())
        group.add(refresh)
        self._dpi = Gtk.SpinButton.new_with_range(100, 42000, 50)
        self._dpi.set_value(1600)
        self._pid = Gtk.Entry(placeholder_text="PID hex, e.g. 1a8d")
        group.add(self._pid)
        group.add(self._dpi)
        row = Gtk.Box(spacing=8)
        read = Gtk.Button(label=t("读取电量 / DPI", "Read battery / DPI"))
        read.connect("clicked", lambda _b: self._read_mouse())
        write = Gtk.Button(label=t("设置 DPI", "Set DPI"))
        write.connect("clicked", lambda _b: self._set_dpi())
        row.append(read)
        row.append(write)
        group.add(row)
        self._labels["mouse"] = Gtk.Label(label="", wrap=True, xalign=0)
        group.add(self._labels["mouse"])
        page.add(group)
        return page

    def _hotkeys(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("华硕 Fn 热键", "ASUS Fn hotkeys"))
        self._labels["hotkey"] = self._row(group, t("最近按键", "Last key"), "-")
        self._labels["hotkey-err"] = self._row(group, t("监听", "Listener"), "-")
        group.add(Gtk.Label(label=t(
            "Fn 键来自 Asus WMI hotkeys 输入设备。安装 udev 规则后无需 root。全局快捷键仍由桌面环境负责。",
            "Fn keys come from the Asus WMI hotkeys input device. The udev rule grants access without root. Desktop-global shortcuts stay with the compositor.",
        ), wrap=True, xalign=0, css_classes=["gh-muted"]))
        page.add(group)
        return page

    def _updates(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("BIOS / 固件", "BIOS / firmware"))
        button = Gtk.Button(label=t("检查华硕官网与 fwupd", "Check ASUS and fwupd"))
        button.connect("clicked", lambda _b: self._check_updates())
        group.add(button)
        self._labels["updates"] = Gtk.Label(label=t("尚未检查", "Not checked"), wrap=True, xalign=0)
        group.add(self._labels["updates"])
        page.add(group)
        return page

    def _acpi(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("与 Windows 版相同的 ACPI 设备号", "ACPI device IDs shared with the Windows app"))
        self._labels["lockdown"] = self._row(group, t("内核 lockdown", "Kernel lockdown"), "-")
        self._acpi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._acpi_buttons = []
        group.add(self._acpi_box)
        group.add(Gtk.Label(label=t(
            "读写走 debugfs（asus-nb-wmi dev_id/dsts/devs），需要已授权的助手。错误的值可能让风扇狂转，请只在了解机型时使用。",
            "Reads and writes use debugfs (dev_id/dsts/devs) and need the authorized helper. Wrong values can force fans to full speed.",
        ), wrap=True, xalign=0, css_classes=["gh-muted"]))
        page.add(group)
        return page

    def _settings(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=t("应用", "Application"))
        lang = Adw.ComboRow(title=t("语言", "Language"))
        model = Gtk.StringList.new([t("跟随系统", "System"), "中文", "English"])
        lang.set_model(model)
        current = self.ctrl.config.get("language") or "auto"
        lang.set_selected(0 if current == "auto" else 1 if current == "zh" else 2)
        lang.connect("notify::selected", self._lang_changed)
        group.add(lang)
        mini = Adw.SwitchRow(title=t("启动时只显示托盘", "Start in the tray"))
        mini.set_active(bool(self.ctrl.config.get("start_minimized")))
        mini.connect("notify::active", lambda row, _p: self.ctrl.config.set("start_minimized", row.get_active()))
        group.add(mini)
        auto = Adw.SwitchRow(title=t("登录时启动", "Start at login"))
        auto.set_active(bool(self.ctrl.config.get("autostart")))
        auto.connect("notify::active", self._autostart)
        group.add(auto)
        overlay = Adw.SwitchRow(title=t("性能叠加层", "Metrics overlay"))
        overlay.set_active(bool(self.ctrl.config.data.get("overlay", {}).get("enabled")))
        overlay.connect("notify::active", self._overlay_toggled)
        group.add(overlay)
        group.add(Gtk.Label(label="G-Helper Linux %s  GPL-3.0-only" % __version__, xalign=0))
        page.add(group)
        return page

    def _row(self, group, title: str, value: str) -> Gtk.Label:
        row = Adw.ActionRow(title=title)
        label = Gtk.Label(label=value, css_classes=["gh-muted"])
        row.add_suffix(label)
        group.add(row)
        return label

    def _fill(self, snap: dict) -> None:
        product = snap["product"]
        self._set("product", "%s %s" % (product.get("vendor") or "", product.get("name") or ""))
        info = self.app_ref.launch_info
        self.subtitle.set_label("%s -> %s" % (info.get("requested"), info.get("actual") or self.app_ref.backend))
        self._set("backend", "%s / %s" % (info.get("desktop") or "-", info.get("actual") or self.app_ref.backend))
        helper = snap["helper"]["running"]
        self._set("helper", t("运行中", "running") if helper else t("未运行", "stopped"))
        perf = snap["performance"]
        self._set("mode", "%s / %s" % (perf.get("current") or "-", perf.get("profile") or "-"))
        temp = snap["temps"].get("package_c")
        self._set("temp", "-" if temp is None else "%s C" % temp)
        fans = snap["fans"]
        self._set("fan", ", ".join("%s %srpm" % (fan["label"], fan["rpm"]) for fan in fans) or "-")
        self._set("fan-detail", self._labels["fan"].get_label())
        bat = snap["battery"].get("primary") or {}
        ac = snap["battery"].get("ac_online")
        self._set("battery", "%s%% %s  AC=%s  limit=%s" % (
            bat.get("capacity") if bat.get("capacity") is not None else "-",
            bat.get("status") or "",
            ac,
            bat.get("charge_limit"),
        ))
        self._set("charge", self._labels["battery"].get_label())
        if bat.get("charge_limit") and not getattr(self, "_charge_set", False):
            self._charge_spin.set_value(bat["charge_limit"])
            self._charge_set = True
        kb = snap["keyboard"]["devices"]
        self._set("kbd", "-" if not kb else "%s / %s" % (kb[0]["brightness"], kb[0]["max"]))
        if kb and kb[0]["max"] is not None and self._kbd_scale.get_adjustment().get_upper() != kb[0]["max"]:
            self._kbd_scale.set_range(0, kb[0]["max"])
        bright = snap["display"]["brightness"].get("percent")
        if bright is not None:
            self.brightness_percent = bright
        outputs = snap["display"]["outputs"]
        self._set("display", "; ".join("%s %s" % (item["name"], item.get("current") or "") for item in outputs[:4]) or "-")
        if outputs and not self._output_entry.get_text():
            internal = next((item for item in outputs if "eDP" in item["name"]), outputs[0])
            self._output_entry.set_text(internal["name"])
            if internal.get("current"):
                self._mode_entry.set_text(internal["current"])
        gpu = snap["gpu"]
        self._set("gpu", ", ".join(gpu.get("modes") or []) or t("此机型未暴露独显切换", "no dGPU mux on this machine"))
        attrs = snap["attributes"]
        attrs_text = "\n".join("%s = %s" % (item["name"], item["current"]) for item in attrs) or t("无 armoury 属性", "no armoury attributes")
        if self._labels["attrs"].get_label() != attrs_text:
            self._labels["attrs"].set_label(attrs_text)
        devices = snap["peripherals"]
        batteries = snap.get("peripheral_batteries") or {}
        lines = []
        first_percent = None
        for item in devices:
            info = batteries.get(item["pid"])
            text = _format_device(item, info)
            lines.append(text)
            if first_percent is None and info and info.get("percent") is not None:
                first_percent = int(info["percent"])
        peri_text = "\n".join(lines) or t("未发现华硕 HID", "no ASUS HID device")
        if self._labels["peri"].get_label() != peri_text:
            self._labels["peri"].set_label(peri_text)
        self._set("peri-bat", " / ".join(lines) or "-")
        level = 0 if first_percent is None else first_percent
        if hasattr(self, "_peri_level") and self._peri_level.get_value() != level:
            self._peri_level.set_value(level)
        if devices and not self._pid.get_text():
            self._pid.set_text("%04x" % devices[0]["pid"])
        offered = {item["id"]: item["available"] for item in perf["modes"]}
        for mode, button in (("silent", self._labels.get("btn-silent")), ("balanced", self._labels.get("btn-balanced")), ("turbo", self._labels.get("btn-turbo"))):
            if button:
                button.set_sensitive(bool(offered.get(mode)))
        listener = self.app_ref.hotkeys
        if listener:
            self._set("hotkey-err", listener.last_error or t("监听中", "listening"))
        lockdown = (snap.get("host") or {}).get("lockdown") or "unknown"
        locked = lockdown not in {"none", "unknown"}
        self._set("lockdown", lockdown if locked else t("未启用", "not enabled"))
        for widget in getattr(self, "_acpi_buttons", []):
            widget.set_sensitive(not locked)
        self._fill_acpi(snap)

    def _fill_acpi(self, snap: dict) -> None:
        if getattr(self, "_acpi_filled", False):
            return
        self._acpi_filled = True
        for item in snap["acpi_catalog"]:
            row = Gtk.Box(spacing=6)
            row.append(Gtk.Label(label="%s %s" % (item["group"], item["name"]), xalign=0, hexpand=True))
            spin = Gtk.SpinButton.new_with_range(item["min"], item["max"], 1)
            get_btn = Gtk.Button(label="GET")
            set_btn = Gtk.Button(label="SET")
            device = int(item["id"])
            get_btn.connect("clicked", lambda _b, dev=device, widget=spin: self._acpi_get(dev, widget))
            set_btn.connect("clicked", lambda _b, dev=device, widget=spin: self._acpi_set(dev, widget))
            row.append(spin)
            row.append(get_btn)
            row.append(set_btn)
            self._acpi_buttons.append(spin)
            self._acpi_buttons.append(get_btn)
            self._acpi_buttons.append(set_btn)
            self._acpi_box.append(row)

    def _set(self, key: str, value: str) -> None:
        label = self._labels.get(key)
        if label and label.get_label() != str(value):
            label.set_label(str(value))

    def _apply_mode(self, mode: str) -> None:
        result = self.ctrl.set_mode(mode)
        self.toast(result.message if not result.ok else t("已切换到 ", "switched to ") + mode)
        self.refresh()

    def _apply_gpu(self, mode: str) -> None:
        result = self.ctrl.set_gpu_mode(mode)
        self.toast(result.message or mode)
        self.refresh()

    def _apply_charge(self) -> None:
        result = self.ctrl.set_charge_limit(int(self._charge_spin.get_value()))
        self.toast(result.message or t("充电上限已写入", "charge limit written"))
        self.refresh()

    def _apply_refresh(self) -> None:
        result = self.ctrl.set_refresh(self._output_entry.get_text().strip(), self._mode_entry.get_text().strip())
        self.toast(result.message or "ok")

    def _apply_curve(self) -> None:
        points = [(int(temp.get_value()), int(duty.get_value())) for temp, duty in self._fan_spins]
        result = self.ctrl.apply_fan_curve(self._fan_id.get_text().strip() or "mid", points)
        self.toast(result.message or "ok")

    def _kbd_changed(self, scale) -> None:
        if getattr(self, "_kbd_lock", False):
            return
        self._kbd_lock = True
        result = self.ctrl.set_keyboard_brightness(int(scale.get_value()))
        self._kbd_lock = False
        if not result.ok:
            self.toast(result.message)

    def _brightness_changed(self, scale) -> None:
        self.brightness_percent = int(scale.get_value())
        if getattr(self, "_bright_lock", False):
            return
        result = self.ctrl.set_brightness(self.brightness_percent)
        if not result.ok:
            self.toast(result.message)

    def _authorize(self) -> None:
        def work():
            result = spawn_helper()
            GLib.idle_add(lambda: self.toast(result.message or ("ok" if result.ok else "failed")) or False)
        threading.Thread(target=work, daemon=True).start()

    def _auto_toggled(self, row, _pspec) -> None:
        auto = dict(self.ctrl.config.data.get("automation") or {})
        auto["enabled"] = row.get_active()
        self.ctrl.config.data["automation"] = auto
        self.ctrl.config.save()

    def _lang_changed(self, row, _pspec) -> None:
        selected = row.get_selected()
        lang = "auto" if selected == 0 else "zh" if selected == 1 else "en"
        self.ctrl.config.set("language", lang)
        set_language(lang)
        self.toast(t("语言已保存，重新打开窗口后完整生效", "Language saved. Reopen the window to apply it fully."))

    def _autostart(self, row, _pspec) -> None:
        enabled = row.get_active()
        self.ctrl.config.set("autostart", enabled)
        desktop = Path.home() / ".config" / "autostart" / "org.ghelper.Linux.desktop"
        if enabled:
            desktop.parent.mkdir(parents=True, exist_ok=True)
            desktop.write_text(
                "[Desktop Entry]\nType=Application\nName=G-Helper\nExec=ghelper --minimized\nIcon=ghelper\nX-GNOME-Autostart-enabled=true\n",
                encoding="utf-8",
            )
        elif desktop.exists():
            desktop.unlink()

    def _overlay_toggled(self, row, _pspec) -> None:
        overlay = dict(self.ctrl.config.data.get("overlay") or {})
        overlay["enabled"] = row.get_active()
        self.ctrl.config.data["overlay"] = overlay
        self.ctrl.config.save()
        if self.app_ref.overlay:
            if row.get_active():
                self.app_ref.overlay.present()
            else:
                self.app_ref.overlay.hide()

    def _read_mouse(self) -> None:
        try:
            pid = int(self._pid.get_text().strip(), 16)
        except ValueError:
            self.toast("bad pid")
            return
        mouse = self.ctrl.peripherals.mouse(pid)
        if mouse is None:
            self.toast(t("不是已识别的鼠标", "not a known mouse"))
            return
        battery = mouse.read_battery()
        dpi = mouse.read_dpi()
        polling = mouse.read_polling()
        self._labels["mouse"].set_label("battery=%s dpi=%s polling=%s" % (battery.to_dict(), dpi.to_dict(), polling.to_dict()))

    def _set_dpi(self) -> None:
        try:
            pid = int(self._pid.get_text().strip(), 16)
        except ValueError:
            self.toast("bad pid")
            return
        mouse = self.ctrl.peripherals.mouse(pid)
        if mouse is None:
            return
        result = mouse.set_dpi(int(self._dpi.get_value()))
        self.toast(result.message or "ok")

    def _acpi_get(self, device: int, spin: Gtk.SpinButton) -> None:
        result = self.ctrl.hw.acpi_read(device)
        if result.ok and result.data:
            spin.set_value(int(result.data.get("value") or 0))
            self.toast("0x%X = %s" % (device, result.data.get("value")))
        else:
            self.toast(result.message or "acpi get failed")

    def _acpi_set(self, device: int, spin: Gtk.SpinButton) -> None:
        result = self.ctrl.hw.acpi_write(device, int(spin.get_value()))
        self.toast(result.message or "acpi set")

    def _check_updates(self) -> None:
        def work():
            bios = asus_bios()
            fw = fwupd_summary()
            text = "BIOS: %s\nfwupd: %s" % (bios.message or "ok", "available" if fw.get("available") else "missing")
            if bios.ok:
                text = "BIOS payload received for %s" % (bios.data or {}).get("model")
            GLib.idle_add(lambda: self._labels["updates"].set_label(text[:1200]) or False)
        threading.Thread(target=work, daemon=True).start()
