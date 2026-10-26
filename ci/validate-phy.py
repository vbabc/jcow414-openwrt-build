# SPDX-License-Identifier: GPL-2.0-only
"""Inspect applied diagnostic source; supplements behavioral and kernel builds."""
from pathlib import Path
import sys

kernel = Path(sys.argv[1])
client = (kernel / 'drivers/net/optical/airoha/en7571_main.c').read_text()
phy = (kernel / 'drivers/phy/airoha/phy-airoha-xpon.c').read_text()
api = (kernel / 'include/linux/phy/phy-airoha-xpon.h').read_text()
probe = client[client.index('static int en7571_probe('):client.index('static void en7571_remove(')]
assert probe.index('en7571_factory_calibration_ready') < probe.index('"airoha,phy-diagnostic"')
branch = probe[probe.index('if (phy_diag) {'):probe.index('ret = en7571_init(')]
assert branch.index('devm_phy_get(dev, "xpon")') < branch.index('airoha_xpon_phy_tx_inhibited(')
assert 'ret < 0 ? ret : -EIO' in branch
assert '} else if (frontend_diag) {' in branch
assert branch.index('} else if (frontend_diag) {') < branch.index('devm_gpiod_get(')
stages = ['ret = en7571_init(', 'ret = phy_diag ? airoha_xpon_phy_tx_inhibited(',
          'ret = phy_init(', 'priv->diag_phy_initialized = true;',
          'devm_add_action_or_reset(', 'phy_set_mode_ext(', 'phy_power_on(',
          'priv->diag_phy_powered = true;', 'ret = airoha_xpon_phy_tx_inhibited(',
          'ret = lddla_frontend_register(']
pos = 0
for stage in stages:
    pos = probe.index(stage, pos) + len(stage)
assert 'return 0;' in probe[probe.index('EN7571 frontend diagnostic; TX-disable held;'):probe.index('lddla_debugfs_init(')]
ops = client[client.index('static const struct airoha_lddla_ops en7571_frontend_diag_ops'):client.index('static void en7571_set_defaults(')]
for forbidden in ('.bias_refresh', '.tx_power_refresh', '.tx_rearm', '.tx_timing_calibrate', '.diag_show'):
    assert forbidden not in ops
assert '.name = "en7571_frontend_diag"' in ops
setter = phy[phy.index('airoha_xpon_phy_set_tx_gpio('):phy.index('int airoha_xpon_phy_set_tx_enable(')]
assert setter.index('if (priv->tx_inhibited_diagnostic)') < setter.index('enable = false;') < setter.index('gpiod_set_value_cansleep(')
assert phy.count('gpiod_set_value_cansleep(priv->tx_disable_gpio, !enable)') == 1
exported = phy[phy.index('int airoha_xpon_phy_set_tx_enable('):phy.index('EXPORT_SYMBOL_GPL(airoha_xpon_phy_set_tx_enable)')]
assert exported.index('if (priv->tx_inhibited_diagnostic && enable)') < exported.index('return -EPERM;') < exported.index('airoha_xpon_phy_set_tx_gpio(')
power = phy[phy.index('static int airoha_xpon_phy_power_on('):phy.index('static int airoha_xpon_phy_power_off(')]
assert power.count('gpiod_get_value_cansleep(priv->tx_disable_gpio) != 1') == 2
assert power.index('airoha_xpon_phy_set_tx_gpio(priv, false)') < power.index('airoha_xpon_phy_configure(priv)')
assert 'if (priv->tx_inhibited_diagnostic)\n\t\tdev_info' in power
assert 'else\n\t\tmod_delayed_work' in power
assert 'static DEVICE_ATTR_RO(diagnostic_state)' in phy
assert 'int airoha_xpon_phy_tx_inhibited(struct phy *phy);' in api
print('Single GPIO owner, client admission/cleanup, TX guards and read-only PHY status verified')
