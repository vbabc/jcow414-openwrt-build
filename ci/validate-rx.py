"""Validate a passive receive path without normal GPON activation or FE service."""
from pathlib import Path
import sys
s=(Path(sys.argv[1])/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
a=s.index('static int gpon_rx_diagnostic_start(');b=s.index('static ssize_t control_diagnostic_state_show(',a);rx=s[a:b]
assert 'if (!priv->control_diagnostic || !priv->rx_diagnostic)' in rx
assert rx.count('airoha_xpon_phy_tx_inhibited(')==3
assert rx.index('airoha_xpon_phy_tx_inhibited(')<rx.index('gpon_write(')<rx.index('airoha_xpon_reset_mac(')
assert 'MBI_TX_STOP | MPI_TX_STOP);' in rx and 'MPI_TX_STOP_DONE' in rx
assert rx.index('gpon_dev_init(')<rx.index('gpon_rmw(')<rx.index('readl_poll_timeout_atomic(')<rx.rindex('airoha_xpon_phy_tx_inhibited(')<rx.index('WRITE_ONCE(priv->rx_diagnostic_started, true)')
for forbidden in ['gpon_enable(', 'gpon_prepare_hardware(', 'gpon_set_fe_datapath(', 'airoha_xpon_tx_timing_calibrate(', 'ploam_start(', 'mod_delayed_work(', 'phy_power_on(', 'airoha_gpon_omci_start(']:assert forbidden not in rx,forbidden
stop=s[s.index('static void gpon_rx_diagnostic_stop('):a]
assert 'MBI_RX_STOP | MBI_TX_STOP | MPI_RX_STOP | MPI_TX_STOP' in stop
assert 'gpon_write(priv, GPON_INT_ENABLE, 0)' in stop
assert 'stop:\n\tgpon_rx_diagnostic_stop(priv);' in rx
probe=s[s.index('static int airoha_xpon_probe('):s.index('static void airoha_xpon_remove(')]
assert 'if (priv->rx_diagnostic && !priv->control_diagnostic)' in probe
assert probe.index('priv->rx_diagnostic_result = gpon_rx_diagnostic_start(priv)')<probe.rindex('airoha_xpon_phy_tx_inhibited(')
assert 'static DEVICE_ATTR_RO(rx_diagnostic_state)' in s
assert s.count('gpon_rx_diagnostic_stop(priv);')==3
print('Passive RX admission, reset/readback ordering, TX-stop ACK and cleanup verified; activation/FE/IRQs remain blocked')
