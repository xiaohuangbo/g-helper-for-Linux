"""HID report framing between Windows G-Helper and Linux hidraw.

Windows prepends report id 0 even when the descriptor has no report id.
Linux hidraw then returns the payload only, so a battery reply starts at
0x12 0x07 instead of 0x00 0x12 0x07. Callers keep the Windows layout.
"""

from __future__ import annotations


def command_bytes(packet: bytes) -> bytes:
    if len(packet) >= 3 and packet[0] == 0:
        return packet[1:3]
    return packet[:2]


def is_command_response(request: bytes, response: bytes) -> bool:
    want = command_bytes(request)
    if len(want) < 2 or len(response) < 2:
        return False
    if response[:2] == want:
        return True
    return len(response) >= 3 and response[1:3] == want


def to_windows_layout(request: bytes, response: bytes) -> bytes:
    want = command_bytes(request)
    if len(response) >= 2 and response[:2] == want:
        return bytes([0]) + bytes(response)
    return bytes(response)
