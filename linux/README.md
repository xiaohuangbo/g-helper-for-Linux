# G-Helper Linux

华硕笔记本控制工具的 Linux 移植。显示后端 Wayland 优先，GDK_BACKEND 设为 wayland,x11，Wayland 不可用时回退到 X11。主窗口使用 GTK4 / libadwaita，托盘走 org.kde.StatusNotifierItem（KDE Plasma 原生可用；GNOME 需要 AppIndicator 扩展）。

上游 Windows 程序仍在 app/。本目录是独立、可维护的移植，ACPI 设备号与 app/AsusACPI.cs 对齐，鼠标 HID 包与 app/Peripherals/Mouse/AsusMouse.cs 对齐。许可证与上游相同，GPL-3.0-only。

## 运行

```bash
cd linux
python3 bin/ghelper status
python3 bin/ghelper
python3 bin/ghelper --backend x11
python3 bin/ghelper --minimized
```

强制某个后端：

```bash
GHELPER_GDK_BACKEND=wayland python3 bin/ghelper
GHELPER_GDK_BACKEND=x11 python3 bin/ghelper
```

窗口标题栏会显示请求的后端和实际打开的后端（wayland 或 x11）。

托盘右键菜单只有两项：打开主窗口、停止服务并退出。左键单击托盘图标切换窗口显示。

## 架构

| 路径 | 职责 |
| --- | --- |
| ghelper/session.py | 在导入 GTK 之前选择 Wayland/X11 |
| ghelper/hw/ | sysfs、固件属性、风扇曲线、ACPI 设备号 |
| ghelper/helper.py | root 助手，只允许白名单写入和华硕 HID |
| ghelper/peripherals/ | 型号目录 + 共享鼠标协议，新型号加数据即可 |
| ghelper/ui/ | 主窗口页面 |
| ghelper/tray.py | 托盘 |
| ghelper/overlay.py | Wayland layer-shell，缺失时退回置顶窗口 |

新增能力时：

- 新的 ACPI 设备号加到 ghelper/hw/ids.py 的 ACPI_CATALOG，高级页会自动出现。
- 新的 sysfs 节点加到 ghelper/hw/whitelist.py，否则助手会拒绝写入。
- 新外设加到 ghelper/peripherals/catalog.py。

## 功能对照

已实现：

- 性能模式：静音 / 平衡 / 增强，映射到 platform_profile 和 throttle_thermal_policy。机型没有的模式会禁用。
- 自定义模式、插电/电池自动切换、刷新率随电源切换。
- 风扇转速。内核暴露 pwm auto point 时可以写风扇曲线；没有这些节点时只读。
- 充电上限、键盘背光、屏幕亮度。
- 刷新率：KDE kscreen-doctor，其次 wlr-randr / swaymsg。
- 独显模式 Eco / Standard / Ultimate / Optimized：有 dgpu_disable / gpu_mux_mode 时走 sysfs，否则走 ACPI。
- asus-armoury 固件属性动态列出。
- 与 Windows 版相同的 ACPI 标量读写（debugfs dev_id / dsts / devs），需要助手。
- 华硕鼠标 HID：电量、DPI、轮询率、角度捕捉。键盘和耳机按 VID/PID 识别。
- Fn 热键监听（Asus WMI hotkeys）。
- 托盘、主窗口、性能叠加层。
- BIOS 查询（华硕官网 API，只读）和 fwupd 摘要。Linux 固件请用 fwupd，不要运行 Windows 安装包。

和 Windows 版的差异：

- 没有 NvAPI。独显信息走 nvidia-smi，功耗墙走 ACPI / firmware-attributes。
- 没有 PawnIO / Ryzen SMU 驱动。CPU 功耗限制走 ACPI PPT 设备号。
- Anime Matrix / Slash 动画和逐键 Aura 布局没有整页移植。HID 传输层已经接好，后续加协议模块即可。
- 游戏内 DX 叠加层在 Linux 上没有对应接口，改成合成器叠加层，不伪造 FPS。

## 授权

读 sysfs 不需要 root。写性能模式、充电上限、背光和 ACPI 需要助手：

```bash
sudo systemctl enable --now ghelper-helper.service
```

或在窗口里点「授权硬件写入」（pkexec）。安装包会尝试启用 ghelper-helper.service，并安装 udev 规则，让当前会话用户访问华硕 HID 和 Fn 热键。

## 打包

```bash
cd linux
make test
make packages
```

产物在 linux/dist/：

- ghelper_0.292.0-1_all.deb
- ghelper-0.292.0-1.noarch.rpm
- ghelper-0.292.0-1-any.pkg.tar.zst

也可以用发行版工具：

- Debian：python3 packaging/build_all.py 直接生成 deb。
- Fedora：rpmbuild -ba packaging/ghelper.spec（源码目录设为 linux/）。
- Arch：makepkg -p packaging/arch/PKGBUILD，或直接安装上面的 pkg.tar.zst。
- Nix：在 linux/ 执行 nix build。描述在 flake.nix / default.nix。

依赖：Python 3.11+、GTK4、libadwaita、PyGObject、python-dbus、polkit。叠加层可选 gtk4-layer-shell。

## 测试

```bash
make test
python3 bin/ghelper --self-test
python3 tests/gui_smoke.py
```

--self-test 会打开窗口、打印实际显示后端并退出。gui_smoke.py 会构建真实主窗口，等待外设电量轮询，然后检查概览和外设页是否显示电量、锁定状态下 ACPI 按钮是否禁用。

如果在启用了内核 lockdown 的系统上运行，debugfs 会被拒绝，高级 ACPI 页会显示 lockdown 状态并禁用按钮；性能模式、充电上限、背光和风扇仍走 sysfs，不受影响。
