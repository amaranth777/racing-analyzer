"""GT7 Simulator Interface packet decoding.

The wire format follows Nenkai/PDTools (MIT), specifically
PDTools.SimulatorInterface and PDTools.Crypto. The project owns this Python
implementation; no GPL dashboard code is copied.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Final, cast

KEY: Final[bytes] = b"Simulator Interface Packet GT7 ver 0.0"[:32]
TILDE_XOR_KEY: Final[int] = 0x55FABB4F
TILDE_SIZE: Final[int] = 0x158
MAGIC: Final[bytes] = b"0S7G"


class PacketError(ValueError):
    """Raised when a GT7 packet cannot be safely decoded."""


def _rol32(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF


def _salsa20_block(state: list[int]) -> bytes:
    x = state[:]
    for _ in range(10):
        x[4] ^= _rol32((x[0] + x[12]) & 0xFFFFFFFF, 7)
        x[8] ^= _rol32((x[4] + x[0]) & 0xFFFFFFFF, 9)
        x[12] ^= _rol32((x[8] + x[4]) & 0xFFFFFFFF, 13)
        x[0] ^= _rol32((x[12] + x[8]) & 0xFFFFFFFF, 18)
        x[9] ^= _rol32((x[5] + x[1]) & 0xFFFFFFFF, 7)
        x[13] ^= _rol32((x[9] + x[5]) & 0xFFFFFFFF, 9)
        x[1] ^= _rol32((x[13] + x[9]) & 0xFFFFFFFF, 13)
        x[5] ^= _rol32((x[1] + x[13]) & 0xFFFFFFFF, 18)
        x[14] ^= _rol32((x[10] + x[6]) & 0xFFFFFFFF, 7)
        x[2] ^= _rol32((x[14] + x[10]) & 0xFFFFFFFF, 9)
        x[6] ^= _rol32((x[2] + x[14]) & 0xFFFFFFFF, 13)
        x[10] ^= _rol32((x[6] + x[2]) & 0xFFFFFFFF, 18)
        x[3] ^= _rol32((x[15] + x[11]) & 0xFFFFFFFF, 7)
        x[7] ^= _rol32((x[3] + x[15]) & 0xFFFFFFFF, 9)
        x[11] ^= _rol32((x[7] + x[3]) & 0xFFFFFFFF, 13)
        x[15] ^= _rol32((x[11] + x[7]) & 0xFFFFFFFF, 18)
        x[1] ^= _rol32((x[0] + x[3]) & 0xFFFFFFFF, 7)
        x[2] ^= _rol32((x[1] + x[0]) & 0xFFFFFFFF, 9)
        x[3] ^= _rol32((x[2] + x[1]) & 0xFFFFFFFF, 13)
        x[0] ^= _rol32((x[3] + x[2]) & 0xFFFFFFFF, 18)
        x[6] ^= _rol32((x[5] + x[4]) & 0xFFFFFFFF, 7)
        x[7] ^= _rol32((x[6] + x[5]) & 0xFFFFFFFF, 9)
        x[4] ^= _rol32((x[7] + x[6]) & 0xFFFFFFFF, 13)
        x[5] ^= _rol32((x[4] + x[7]) & 0xFFFFFFFF, 18)
        x[11] ^= _rol32((x[10] + x[9]) & 0xFFFFFFFF, 7)
        x[8] ^= _rol32((x[11] + x[10]) & 0xFFFFFFFF, 9)
        x[9] ^= _rol32((x[8] + x[11]) & 0xFFFFFFFF, 13)
        x[10] ^= _rol32((x[9] + x[8]) & 0xFFFFFFFF, 18)
        x[12] ^= _rol32((x[15] + x[14]) & 0xFFFFFFFF, 7)
        x[13] ^= _rol32((x[12] + x[15]) & 0xFFFFFFFF, 9)
        x[14] ^= _rol32((x[13] + x[12]) & 0xFFFFFFFF, 13)
        x[15] ^= _rol32((x[14] + x[13]) & 0xFFFFFFFF, 18)
    return b"".join(struct.pack("<I", (x[i] + state[i]) & 0xFFFFFFFF) for i in range(16))


def _decrypt_tilde(packet: bytes) -> bytes:
    seed = struct.unpack_from("<I", packet, 0x40)[0]
    iv = ((seed ^ TILDE_XOR_KEY) & 0xFFFFFFFF, seed)
    key_words = struct.unpack("<8I", KEY)
    constants = struct.unpack("<4I", b"expand 32-byte k")
    state = [0] * 16
    state[0], state[5], state[10], state[15] = constants
    state[1:5] = key_words[:4]
    state[11:15] = key_words[4:]
    state[6], state[7] = iv
    output = bytearray(packet)
    for offset in range(0, len(output), 64):
        block = _salsa20_block(state)
        for index in range(min(64, len(output) - offset)):
            output[offset + index] ^= block[index]
        state[8] = (state[8] + 1) & 0xFFFFFFFF
        if state[8] == 0:
            state[9] = (state[9] + 1) & 0xFFFFFFFF
    return bytes(output)


def _f(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def _i(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _h(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


@dataclass(frozen=True, slots=True)
class TelemetryPacket:
    magic: str
    packet_type: str
    packet_size: int
    packet_id: int
    lap: int
    best_lap_ms: int
    last_lap_ms: int
    flags: int
    gear: int
    suggested_gear: int
    throttle: float
    brake: float
    speed_mps: float
    speed_kmh: float
    rpm: float
    car_code: int
    wheel_rotation_rad: float
    sway: float
    heave: float
    surge: float
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    wheel_rps: tuple[float, float, float, float]
    tyre_diameter_m: tuple[float, float, float, float]


def decode_packet(packet: bytes) -> TelemetryPacket:
    """Decrypt and decode one GT7 extended (``~``) packet."""
    if len(packet) != TILDE_SIZE:
        raise PacketError(f"expected {TILDE_SIZE} bytes, got {len(packet)}")
    data = _decrypt_tilde(packet)
    if data[:4] != MAGIC:
        raise PacketError(f"invalid magic: {data[:4].hex()}")
    gear_byte = data[0x90]
    return TelemetryPacket(
        magic=data[:4].decode("ascii"), packet_type="tilde", packet_size=len(packet),
        packet_id=_i(data, 0x70), lap=_h(data, 0x74),
        best_lap_ms=_i(data, 0x78), last_lap_ms=_i(data, 0x7C),
        flags=_h(data, 0x8E), gear=gear_byte & 0x0F, suggested_gear=gear_byte >> 4,
        throttle=data[0x91] / 255.0, brake=data[0x92] / 255.0,
        speed_mps=_f(data, 0x4C), speed_kmh=_f(data, 0x4C) * 3.6,
        rpm=_f(data, 0x3C), car_code=_i(data, 0x124),
        wheel_rotation_rad=_f(data, 0x128), sway=_f(data, 0x130),
        heave=_f(data, 0x134), surge=_f(data, 0x138),
        position=(_f(data, 0x04), _f(data, 0x08), _f(data, 0x0C)),
        velocity=(_f(data, 0x10), _f(data, 0x14), _f(data, 0x18)),
        wheel_rps=tuple(_f(data, off) for off in (0xA4, 0xA8, 0xAC, 0xB0)),
        tyre_diameter_m=tuple(_f(data, off) for off in (0xB4, 0xB8, 0xBC, 0xC0)),
    )
