"""ACPI device IDs ported from app/AsusACPI.cs.

Linux has no ATKACPI driver. Scalar get/set uses the kernel debugfs
interface (dev_id / dsts / devs) through the privileged helper. Stable
features prefer sysfs and firmware-attributes, and only fall back to these IDs.
"""

from __future__ import annotations

DSTS = 0x53545344
DEVS = 0x53564544

CPU_FAN = 0x00110013
GPU_FAN = 0x00110014
MID_FAN = 0x00110031
PERFORMANCE_MODE = 0x00120075
VIVOBOOK_MODE = 0x00110019
GPU_ECO_ROG = 0x00090020
GPU_ECO_VIVO = 0x00090120
GPU_XG_CONNECTED = 0x00090018
GPU_XG = 0x00090019
GPU_MUX_ROG = 0x00090016
GPU_MUX_VIVO = 0x00090026
BATTERY_LIMIT = 0x00120057
SCREEN_OVERDRIVE = 0x00050019
SCREEN_MINILED1 = 0x0005001E
SCREEN_MINILED2 = 0x0005002E
SCREEN_HDR = 0x00050071
DEVS_CPU_FAN_CURVE = 0x00110024
DEVS_GPU_FAN_CURVE = 0x00110025
DEVS_MID_FAN_CURVE = 0x00110032
FAN_HYSTERESIS = 0x00110034
PPT_APUA0 = 0x001200A0
PPT_EDCA1 = 0x001200A1
PPT_TDCA2 = 0x001200A2
PPT_APUA3 = 0x001200A3
PPT_CPUB0 = 0x001200B0
PPT_CPUB1 = 0x001200B1
PPT_GPUCPU = 0x0012009C
PPT_TEMP = 0x0012009E
PPT_CROSS = 0x0012009F
PPT_GPUC0 = 0x001200C0
PPT_APUC1 = 0x001200C1
PPT_GPUC2 = 0x001200C2
GPU_BASE = 0x00120099
GPU_POWER = 0x00120098
TUF_KB_BRIGHTNESS = 0x00050021
FN_LOCK = 0x00100023
BOOT_SOUND = 0x00130022
CAMERA_SHUTTER = 0x00060078
STATUS_LED = 0x000600C2

PERFORMANCE_BALANCED = 0
PERFORMANCE_TURBO = 1
PERFORMANCE_SILENT = 2
PERFORMANCE_FULLSPEED = 3
PERFORMANCE_MANUAL = 4

ACPI_CATALOG: list[dict] = [
    {"group": "performance", "name": "PerformanceMode", "id": PERFORMANCE_MODE, "kind": "enum",
     "values": {0: "Balanced", 1: "Turbo", 2: "Silent", 3: "Full Speed", 4: "Manual"}, "min": 0, "max": 4},
    {"group": "performance", "name": "VivoBookMode", "id": VIVOBOOK_MODE, "kind": "int", "min": 0, "max": 4},
    {"group": "gpu", "name": "GPUEcoROG", "id": GPU_ECO_ROG, "kind": "enum", "values": {0: "Standard", 1: "Eco"}, "min": 0, "max": 1},
    {"group": "gpu", "name": "GPUEcoVivo", "id": GPU_ECO_VIVO, "kind": "enum", "values": {0: "Standard", 1: "Eco"}, "min": 0, "max": 1},
    {"group": "gpu", "name": "GPUMuxROG", "id": GPU_MUX_ROG, "kind": "enum", "values": {0: "Hybrid", 1: "Ultimate"}, "min": 0, "max": 1},
    {"group": "gpu", "name": "GPUMuxVivo", "id": GPU_MUX_VIVO, "kind": "enum", "values": {0: "Hybrid", 1: "Ultimate"}, "min": 0, "max": 1},
    {"group": "gpu", "name": "XGMobile", "id": GPU_XG, "kind": "int", "min": 0, "max": 1},
    {"group": "gpu", "name": "XGConnected", "id": GPU_XG_CONNECTED, "kind": "int", "min": 0, "max": 1},
    {"group": "power", "name": "SPL_PL1", "id": PPT_APUA3, "kind": "int", "min": 5, "max": 175},
    {"group": "power", "name": "sPPT_PL2", "id": PPT_APUA0, "kind": "int", "min": 5, "max": 175},
    {"group": "power", "name": "fPPT", "id": PPT_APUC1, "kind": "int", "min": 5, "max": 175},
    {"group": "power", "name": "CPU_PPT", "id": PPT_CPUB0, "kind": "int", "min": 5, "max": 175},
    {"group": "power", "name": "SlowPPT", "id": PPT_CPUB1, "kind": "int", "min": 5, "max": 175},
    {"group": "power", "name": "CPUTempLimit", "id": PPT_TEMP, "kind": "int", "min": 75, "max": 105},
    {"group": "power", "name": "GPUDynamicBoost", "id": PPT_GPUC0, "kind": "int", "min": 0, "max": 25},
    {"group": "power", "name": "GPUTempTarget", "id": PPT_GPUC2, "kind": "int", "min": 75, "max": 87},
    {"group": "power", "name": "GPUBaseTGP", "id": GPU_BASE, "kind": "int", "min": 0, "max": 175},
    {"group": "power", "name": "GPUExtraTGP", "id": GPU_POWER, "kind": "int", "min": 0, "max": 75},
    {"group": "power", "name": "CrossLoad", "id": PPT_CROSS, "kind": "int", "min": 0, "max": 125},
    {"group": "power", "name": "GPUtoCPU", "id": PPT_GPUCPU, "kind": "int", "min": 0, "max": 25},
    {"group": "display", "name": "ScreenOverdrive", "id": SCREEN_OVERDRIVE, "kind": "int", "min": 0, "max": 1},
    {"group": "display", "name": "MiniLED1", "id": SCREEN_MINILED1, "kind": "int", "min": 0, "max": 1},
    {"group": "display", "name": "MiniLED2", "id": SCREEN_MINILED2, "kind": "int", "min": 0, "max": 1},
    {"group": "display", "name": "ScreenHDR", "id": SCREEN_HDR, "kind": "int", "min": 0, "max": 1},
    {"group": "keyboard", "name": "FnLock", "id": FN_LOCK, "kind": "int", "min": 0, "max": 1},
    {"group": "keyboard", "name": "TufKbBrightness", "id": TUF_KB_BRIGHTNESS, "kind": "int", "min": 0, "max": 3},
    {"group": "misc", "name": "BatteryLimit", "id": BATTERY_LIMIT, "kind": "int", "min": 40, "max": 100},
    {"group": "misc", "name": "BootSound", "id": BOOT_SOUND, "kind": "int", "min": 0, "max": 1},
    {"group": "misc", "name": "CameraShutter", "id": CAMERA_SHUTTER, "kind": "int", "min": 0, "max": 1},
    {"group": "misc", "name": "StatusLed", "id": STATUS_LED, "kind": "int", "min": 0, "max": 1},
]

FAN_CURVE_IDS = {
    "cpu": DEVS_CPU_FAN_CURVE,
    "gpu": DEVS_GPU_FAN_CURVE,
    "mid": DEVS_MID_FAN_CURVE,
}

ASUS_VID = 0x0B05

AURA_PIDS = {
    0x1A30, 0x1854, 0x1869, 0x1866, 0x19B6, 0x1822, 0x1837, 0x184A, 0x183D,
    0x8502, 0x1807, 0x17E0, 0x1ABE, 0x1B4C, 0x1B6E, 0x1B2C, 0x8854, 0x1CE7,
    0x1CE6, 0x1BF2, 0x1BF3, 0x1CD7, 0x1CD8, 0x4B42, 0x18C6,
}
