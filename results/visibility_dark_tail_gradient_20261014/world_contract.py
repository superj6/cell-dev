"""Pure exact-world contract for the approved AD production dark-flash world."""
AD_PROTOCOL_SHA256 = 'ee041636fec03ab3dc8e468b0d3427d75a2ac2736436b4dd954e3ac1c96100fe'
AC_PROTOCOL_SHA256 = '672ac123ca9283cd004e699cb6be1b0ac4203b468f75f03546140560cd58fda2'


def check_world(actual, retained):
    if actual != retained:
        raise ValueError('every retained AD production world field must match exactly')
    expected = {'name': 'catch_speck_flash5_dim25_l4', 'T': 1024, 'd0': 1., 'd_min': .5,
                'v_t': .1, 'tau_turn': 20., 'R_cap': 500., 'visibility_mode': 1,
                'visibility_on': 5., 'visibility_off': 0., 'visibility_low': 0.,
                't0': 0., 't_open': 0., 't_fork': 0., 'flags': 0, 'fork_flags': 0}
    if any(actual.get(k) != v for k, v in expected.items()):
        raise ValueError('retained world is not the reviewed AD fixed-T fully dark flash world')
