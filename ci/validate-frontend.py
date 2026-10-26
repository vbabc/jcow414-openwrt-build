# SPDX-License-Identifier: GPL-2.0-only
"""Fail the diagnostic build if the applied TX-inhibit stages regress.

These source gates supplement kernel compilation and offline DTB inspection;
they do not verify physical pin voltage or optical emission.
"""
import pathlib
import sys

driver = pathlib.Path(sys.argv[1]).read_text()
probe = driver[driver.index('static int en7571_probe('):driver.index('static void en7571_remove(')]
stages = [
    'en7571_factory_calibration_ready',
    '"airoha,diagnostic-only"',
    '"airoha,frontend-diagnostic"',
    'devm_gpiod_get(dev, "tx-disable", GPIOD_OUT_HIGH)',
    'if (IS_ERR(tx_disable))',
    'if (gpiod_get_value_cansleep(tx_disable) != 1)',
    'ret = en7571_init(',
    'if (gpiod_get_value_cansleep(tx_disable) != 1)',
    'priv->lddla.ops = &en7571_frontend_diag_ops;',
    'ret = lddla_frontend_register(',
    'EN7571 frontend diagnostic; TX-disable held;',
    'lddla_debugfs_init(',
    'schedule_delayed_work(',
]
position = 0
for stage in stages:
    position = probe.index(stage, position) + len(stage)
before_init = probe[probe.index('"airoha,frontend-diagnostic"'):probe.index('ret = en7571_init(')]
assert before_init.count('return dev_err_probe(') == 2
after_init = probe[probe.index('ret = en7571_init('):probe.index('ret = lddla_frontend_register(')]
assert '"TX-disable GPIO lost after initialization\\n"' in after_init
exit_path = probe[probe.index('EN7571 frontend diagnostic; TX-disable held;'):probe.index('lddla_debugfs_init(')]
assert 'return 0;' in exit_path
ops = driver[driver.index('static const struct airoha_lddla_ops en7571_frontend_diag_ops'):driver.index('static void en7571_set_defaults(')]
for forbidden in ('.bias_refresh', '.tx_power_refresh', '.tx_rearm', '.tx_timing_calibrate', '.diag_show'):
    assert forbidden not in ops, forbidden
for allowed in ('.temp_refresh', '.bosa_temp_refresh', '.vcc_refresh', '.rx_power_refresh'):
    assert allowed in ops, allowed
print('TX-disable admission/readback, telemetry-only ops and early exit verified')
