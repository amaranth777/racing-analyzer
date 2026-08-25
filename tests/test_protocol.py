from pathlib import Path

import pytest

from gt7coach.protocol import PacketError, decode_packet

FIXTURE = Path(__file__).parent / "fixtures" / "first_packet.bin"


def test_decode_real_gt7_extended_packet():
    packet = decode_packet(FIXTURE.read_bytes())

    assert packet.magic == "0S7G"
    assert packet.packet_type == "tilde"
    assert packet.packet_size == 344
    assert packet.car_code == 1365
    assert packet.lap == 3
    assert packet.packet_id == 1238170
    assert packet.speed_kmh == pytest.approx(197.0, abs=0.2)
    assert packet.rpm == pytest.approx(7795.0)
    assert packet.throttle == 1.0
    assert packet.brake == 0.0
    assert packet.wheel_rotation_rad == pytest.approx(0.3239406, abs=1e-5)


def test_decode_rejects_wrong_packet_size():
    with pytest.raises(PacketError, match="344"):
        decode_packet(FIXTURE.read_bytes()[:-1])


def test_decode_rejects_corrupted_packet():
    corrupted = bytearray(FIXTURE.read_bytes())
    corrupted[0] ^= 0xFF
    with pytest.raises(PacketError, match="magic"):
        decode_packet(bytes(corrupted))
