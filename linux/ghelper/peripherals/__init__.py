"""ASUS HID peripherals.

Model identity is data (catalog.py). The shared mouse packet family from
app/Peripherals/Mouse/AsusMouse.cs lives in mouse.py. New devices are added
by extending the catalog, not by forking the UI.
"""

from ghelper.peripherals.manager import PeripheralManager

__all__ = ["PeripheralManager"]
