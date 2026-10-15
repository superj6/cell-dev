"""Pure field contract for the exact retained V world; no engine imports."""
V_PROTOCOL_SHA256 = 'bc2df79bfd484107ce50027ec6b734c041a00efa982654a64ddc7e065910d99f'
NEUTRAL_VISIBILITY = {'visibility_mode': 0, 'visibility_on': 0.0,
                      'visibility_off': 0.0, 'visibility_low': 1.0}


def check_world(actual, retained):
    """ABI3 fields match V exactly; a current World may append neutral ABI4 fields."""
    if set(retained) & set(NEUTRAL_VISIBILITY):
        raise ValueError('retained V protocol must describe its original ABI3 world')
    expected = dict(retained)
    if set(actual) - set(retained):
        expected.update(NEUTRAL_VISIBILITY)
    if actual != expected:
        raise ValueError('every retained V world field must match exactly')
    if (actual.get('T') != 1024 or actual.get('d0') != 1 or actual.get('d_min') != .5
            or actual.get('v_t') != .3 or actual.get('tau_turn') != 200
            or actual.get('name') != 'catch_speck_l4' or actual.get('R_cap') != 500
            or any(actual.get(k) != 0 for k in ('t0', 't_open', 't_fork', 'flags', 'fork_flags'))):
        raise ValueError('retained world is not the reviewed V fixed-T old-conduction world')
