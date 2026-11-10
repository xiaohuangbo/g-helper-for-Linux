"""Fan curve helpers.

G-Helper stores 16 bytes: 8 temperatures then 8 duty percentages.
Linux hwmon pwm is 0-255.
"""

from __future__ import annotations

DEFAULT_TEMPS = (30, 40, 50, 60, 70, 80, 90, 100)
DEFAULT_DUTY = (0, 10, 25, 40, 55, 70, 85, 100)


def default_points() -> list[tuple[int, int]]:
    return list(zip(DEFAULT_TEMPS, DEFAULT_DUTY))


def clamp_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cleaned: list[tuple[int, int]] = []
    last_temp = 19
    for temp, duty in list(points)[:8]:
        temp_i = max(20, min(100, int(temp)))
        duty_i = max(0, min(100, int(duty)))
        if temp_i <= last_temp:
            temp_i = min(100, last_temp + 1)
        cleaned.append((temp_i, duty_i))
        last_temp = temp_i
    while len(cleaned) < 8:
        prev_t, prev_d = cleaned[-1] if cleaned else (30, 0)
        cleaned.append((min(100, prev_t + 6), prev_d))
    return cleaned


def pack_curve(points: list[tuple[int, int]]) -> bytes:
    points = clamp_points(points)
    temps = bytes(temp for temp, _duty in points)
    duties = bytes(duty for _temp, duty in points)
    return temps + duties


def unpack_curve(blob: bytes) -> list[tuple[int, int]]:
    if len(blob) < 16:
        return default_points()
    return [(blob[i], blob[i + 8]) for i in range(8)]


def duty_to_pwm(duty: int) -> int:
    return max(0, min(255, round(duty * 255 / 100)))


def pwm_to_duty(pwm: int) -> int:
    return max(0, min(100, round(pwm * 100 / 255)))
