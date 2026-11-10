"""VID/PID catalog ported from app/Peripherals.

kind: mouse, keyboard, headset, other.
iface: preferred hidraw input index (mi_00 -> 0).
"""

from __future__ import annotations

ASUS = 0x0B05

# pid -> metadata. Wireless flag and DPI limits follow the C# model classes.
MICE: dict[int, dict] = {
    0x1845: {"name": "ROG Gladius II", "max_dpi": 12000, "step": 100, "iface": 2},
    0x1846: {"name": "ROG Pugio", "max_dpi": 7200, "step": 100, "iface": 2},
    0x1847: {"name": "ROG Strix Impact", "max_dpi": 5000, "step": 100, "iface": 2},
    0x185B: {"name": "ROG Strix Evolve", "max_dpi": 7200, "step": 100, "iface": 0},
    0x1877: {"name": "ROG Gladius II Origin", "max_dpi": 12000, "step": 100, "iface": 2},
    0x1898: {"name": "TUF Gaming M5", "max_dpi": 6200, "step": 100, "iface": 2},
    0x18A0: {"name": "ROG Gladius II Wireless", "max_dpi": 16000, "step": 100, "iface": 2, "wireless": True},
    0x18B1: {"name": "ROG Gladius II Origin COD", "max_dpi": 12000, "step": 100, "iface": 2},
    0x18B4: {"name": "ROG Strix Carry", "max_dpi": 7200, "step": 100, "iface": 1, "wireless": True},
    0x18CD: {"name": "ROG Gladius II Origin PNK", "max_dpi": 12000, "step": 100, "iface": 2},
    0x18DD: {"name": "ROG Gladius II Core", "max_dpi": 6200, "step": 100, "iface": 2},
    0x18E1: {"name": "ROG Strix Impact II", "max_dpi": 6200, "step": 100, "iface": 0},
    0x18E3: {"name": "ROG Chakram Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x18E5: {"name": "ROG Chakram", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x1906: {"name": "ROG Pugio II Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1908: {"name": "ROG Pugio II", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x1910: {"name": "TUF Gaming M3", "max_dpi": 7000, "step": 100, "iface": 1},
    0x1947: {"name": "ROG Strix Impact II Wireless Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1949: {"name": "ROG Strix Impact II Wireless", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x1956: {"name": "ROG Strix Impact II Electro Punk", "max_dpi": 6200, "step": 100, "iface": 0},
    0x1958: {"name": "ROG Chakram Core", "max_dpi": 16000, "step": 100, "iface": 0},
    0x195C: {"name": "ROG Keris", "max_dpi": 16000, "step": 100, "iface": 0},
    0x195E: {"name": "ROG Keris Wireless Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1960: {"name": "ROG Keris Wireless", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x1977: {"name": "ROG Spatha X Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1979: {"name": "ROG Spatha X", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x197B: {"name": "ROG Gladius III", "max_dpi": 26000, "step": 100, "iface": 0},
    0x197D: {"name": "ROG Gladius III Wired", "max_dpi": 26000, "step": 100, "iface": 0},
    0x197F: {"name": "ROG Gladius III Wireless", "max_dpi": 26000, "step": 100, "iface": 0, "wireless": True},
    0x19D2: {"name": "ROG Strix Impact II Moonlight", "max_dpi": 6200, "step": 100, "iface": 0},
    0x19F4: {"name": "TUF Gaming M4 Wireless", "max_dpi": 12000, "step": 100, "iface": 0, "wireless": True},
    0x1A03: {"name": "TUF Gaming M4 Air", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1A18: {"name": "ROG Chakram X Wired", "max_dpi": 36000, "step": 100, "iface": 0},
    0x1A1A: {"name": "ROG Chakram X", "max_dpi": 36000, "step": 100, "iface": 0, "wireless": True},
    0x1A57: {"name": "ROG Keris Wireless EVA Wired", "max_dpi": 16000, "step": 100, "iface": 0},
    0x1A59: {"name": "ROG Keris Wireless EVA", "max_dpi": 16000, "step": 100, "iface": 0, "wireless": True},
    0x1A66: {"name": "ROG Keris Wireless Aimpoint Wired", "max_dpi": 36000, "step": 100, "iface": 0},
    0x1A68: {"name": "ROG Keris Wireless Aimpoint", "max_dpi": 36000, "step": 100, "iface": 0, "wireless": True},
    0x1A70: {"name": "ROG Gladius III Aimpoint Wired", "max_dpi": 36000, "step": 100, "iface": 0},
    0x1A72: {"name": "ROG Gladius III Aimpoint", "max_dpi": 36000, "step": 100, "iface": 0, "wireless": True},
    0x1A88: {"name": "ROG Strix Impact III", "max_dpi": 12000, "step": 100, "iface": 0},
    0x1A8D: {"name": "TX Gaming Mouse", "max_dpi": 12000, "step": 100, "iface": 0, "wireless": True},
    0x1A92: {"name": "ROG Harpe Ace Aim Lab Wired", "max_dpi": 36000, "step": 50, "iface": 0},
    0x1A94: {"name": "ROG Harpe Ace Aim Lab", "max_dpi": 36000, "step": 50, "iface": 0, "wireless": True},
    0x1A9B: {"name": "TUF Gaming M3 Gen II", "max_dpi": 8000, "step": 100, "iface": 2},
    0x1ACE: {"name": "ROG Omni Receiver", "max_dpi": 36000, "step": 50, "iface": 2, "wireless": True, "rgb": True},
    0x1AD0: {"name": "ROG Harpe II Ace Wireless", "max_dpi": 42000, "step": 50, "iface": 2, "wireless": True},
    0x1AF3: {"name": "TX Gaming Mouse Mini Wired", "max_dpi": 12000, "step": 50, "iface": 0, "xy": True},
    0x1AF5: {"name": "TX Gaming Mouse Mini", "max_dpi": 12000, "step": 50, "iface": 0, "wireless": True, "xy": True},
    0x1B0A: {"name": "ROG Gladius III Aimpoint EVA-02 Wired", "max_dpi": 36000, "step": 100, "iface": 0},
    0x1B0C: {"name": "ROG Gladius III Aimpoint EVA-02", "max_dpi": 36000, "step": 100, "iface": 0, "wireless": True},
    0x1B16: {"name": "ROG Keris II Ace Wired", "max_dpi": 42000, "step": 50, "iface": 0, "wireless": True},
    0x1B63: {"name": "ROG Harpe Ace Mini Wired", "max_dpi": 36000, "step": 50, "iface": 0},
    0x1B67: {"name": "ROG Harpe Ace Extreme", "max_dpi": 42000, "step": 50, "iface": 0},
    0x1C0C: {"name": "ROG Keris II Origin Wired", "max_dpi": 26000, "step": 100, "iface": 0, "wireless": True},
    0x1C56: {"name": "TUF Gaming Mini Miku Wired", "max_dpi": 12000, "step": 50, "iface": 0, "rgb": True, "xy": True},
    0x1C57: {"name": "TUF Gaming Mini Miku", "max_dpi": 12000, "step": 50, "iface": 0, "wireless": True, "rgb": True, "xy": True},
    0x1C69: {"name": "ROG Harpe II Ace Wired", "max_dpi": 42000, "step": 50, "iface": 0},
    0x1C8F: {"name": "ROG Harpe Mini Core", "max_dpi": 8000, "step": 50, "iface": 0},
    0x1CD3: {"name": "ASUS MD301", "max_dpi": 4200, "step": 100, "iface": 3, "wireless": True},
    0x1CD5: {"name": "ASUS MD301 Wired", "max_dpi": 4200, "step": 100, "iface": 3},
    0x1D4C: {"name": "ROG Keris II Origin KJP", "max_dpi": 26000, "step": 100, "iface": 0, "wireless": True},
}

KEYBOARDS: dict[int, dict] = {
    0x1875: {"name": "ROG Strix Flare", "iface": 1},
    0x18AF: {"name": "ROG Strix Flare COD", "iface": 1},
    0x18CF: {"name": "ROG Strix Flare PNK", "iface": 1},
    0x193C: {"name": "ROG Falchion", "iface": 1},
    0x193E: {"name": "ROG Falchion Wireless", "iface": 1, "wireless": True},
    0x1945: {"name": "TUF Gaming K1", "iface": 2},
    0x194B: {"name": "TUF Gaming K3", "iface": 1},
    0x1951: {"name": "ROG Strix Scope RX", "iface": 1},
    0x196B: {"name": "ROG Claymore II", "iface": 1},
    0x19FC: {"name": "ROG Strix Flare II Animate", "iface": 1},
    0x19FE: {"name": "ROG Strix Flare II", "iface": 1},
    0x1A05: {"name": "ROG Strix Scope RX TKL Wired", "iface": 1},
    0x1A07: {"name": "ROG Strix Scope RX TKL", "iface": 1, "wireless": True},
    0x1A55: {"name": "ROG Strix Scope RX EVA", "iface": 1},
    0x1A64: {"name": "ROG Falchion Ace", "iface": 1},
    0x1A83: {"name": "ROG Azoth", "iface": 1},
    0x1A85: {"name": "ROG Azoth Wireless", "iface": 1, "wireless": True},
    0x1AAE: {"name": "ROG Strix Scope II 96", "iface": 1, "wireless": True},
    0x1AB3: {"name": "ROG Strix Scope II", "iface": 1},
    0x1AB5: {"name": "ROG Strix Scope II RX", "iface": 1},
    0x1B04: {"name": "ROG Falchion RX", "iface": 1},
    0x1B12: {"name": "ROG Strix Scope RX EVA-02", "iface": 1},
    0x1B30: {"name": "TUF Gaming K3 Gen II", "iface": 1},
    0x1B3A: {"name": "ASUS TX 98", "iface": 1},
    0x1B3F: {"name": "ROG Azoth Extreme", "iface": 1},
    0x1B78: {"name": "ROG Strix Scope II 96 RX", "iface": 1, "wireless": True},
    0x1B7E: {"name": "ROG Falchion Ace HFX", "iface": 1},
    0x1C24: {"name": "ROG Azoth X", "iface": 1},
    0x1C25: {"name": "ROG Azoth X Wireless", "iface": 1, "wireless": True},
    0x1C60: {"name": "TUF Gaming K3 Gen II Miku", "iface": 1},
    0x1CEF: {"name": "ROG Azoth Extreme SE", "iface": 1},
}

HEADSETS: dict[int, dict] = {
    0x18D6: {"name": "ROG Strix Go 2.4", "iface": 0},
    0x1943: {"name": "ROG Delta S", "iface": 0},
    0x195B: {"name": "ROG Clavis", "iface": 0},
    0x1965: {"name": "ROG Cetra RGB", "iface": 0},
    0x1AD3: {"name": "ROG Cetra True Wireless SpeedNova", "iface": 0, "wireless": True},
    0x1AFA: {"name": "ROG Delta II", "iface": 0},
    0x1B84: {"name": "ROG Pelta", "iface": 0},
    0x1D41: {"name": "ROG Delta II KJP", "iface": 0},
}

POLLING = (125, 250, 500, 1000, 2000, 4000, 8000, 16000)


def identify(pid: int) -> dict:
    if pid in MICE:
        return {"kind": "mouse", "pid": pid, **MICE[pid]}
    if pid in KEYBOARDS:
        return {"kind": "keyboard", "pid": pid, **KEYBOARDS[pid]}
    if pid in HEADSETS:
        return {"kind": "headset", "pid": pid, **HEADSETS[pid]}
    return {"kind": "unknown", "pid": pid, "name": "ASUS device %04X" % pid, "iface": 0}
