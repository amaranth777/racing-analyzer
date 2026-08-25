from gt7coach.diagnostics import wheel_speeds_kmh


def test_wheel_speed_conversion_has_no_extra_pi():
    result = wheel_speeds_kmh((100.0, 100.0, 100.0, 100.0), (0.33, 0.33, 0.33, 0.33))
    assert result == (118.8, 118.8, 118.8, 118.8)
