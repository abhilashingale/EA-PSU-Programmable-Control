from ea_psu_control.ps2000b import _percent_to_real, _real_to_percent


def test_real_to_percent_full_scale():
    assert _real_to_percent(nominal=84.0, value=84.0) == 25600


def test_real_to_percent_half_scale():
    assert _real_to_percent(nominal=84.0, value=42.0) == 12800


def test_percent_to_real_round_trip():
    nominal = 84.0
    value = 12.5
    percent = _real_to_percent(nominal, value)
    assert abs(_percent_to_real(nominal, percent) - value) < 0.01
