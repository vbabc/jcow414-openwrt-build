"""Validate complete applied activation source, not an untested source fragment."""
from pathlib import Path
import sys
k=Path(sys.argv[1])
c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
p=(k/'drivers/phy/airoha/phy-airoha-xpon.c').read_text()
f=(k/'drivers/net/optical/airoha/en7571_main.c').read_text()
b=(k/'drivers/net/ethernet/airoha/airoha_gpon_omci.c').read_text()

def body(source,name):
 start=source.index(name+'(');at=source.index('{',start);end=at+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[at:end]

for name in ['gpon_enable','airoha_gpon_omci_hw_start','gpon_link_start','airoha_gpon_omci_hw_set_tcont','airoha_gpon_omci_hw_set_gem_port','airoha_gpon_omci_hw_replace_service','airoha_gpon_omci_hw_delete_service']:
 s=body(c,name);assert s.index('airoha_xpon_activation_blocked(priv)')<s.index('return -EPERM;'),name
for name in ['airoha_xpon_tx_enable','gpon_set_fe_datapath']:
 assert 'airoha_xpon_activation_blocked(priv) && enable' in body(c,name)
for name in ['epon_enable','epon_link_start']:assert 'if (priv->manual_activation)' in body(c,name)
assert 'airoha_xpon_activation_blocked(priv)' in body(c,'gpon_hw_send_ploam')
assert 'airoha_xpon_activation_blocked(priv)' in body(c,'airoha_gpon_omci_hw_is_diagnostic')
for name in ['airoha_gpon_omci_start_transport','airoha_gpon_omci_xmit']:assert 'airoha_gpon_omci_hw_is_diagnostic' in body(b,name)
s=body(c,'airoha_xpon_register_gpon_omci');assert s.index('priv->manual_activation')<s.index('return 0;')<s.index('airoha_gpon_omci_start(')
s=body(c,'airoha_gpon_omci_hw_config_changed')
assert 'key == OMCI_CONFIG_SERIAL_NUMBER' in s and 'OMCI_CONFIG_SOURCE_NETLINK' in s and 'OMCI_CONFIG_SOURCE_SYSFS' in s
assert 'OMCI_CONFIG_SOURCE_DRIVER' not in s and 'OMCI_IDENTITY_F_SERIAL_NUMBER' in s
s=body(c,'airoha_xpon_manual_start')
order=['activation_identity_configured','airoha_xpon_phy_tx_inhibited(','airoha_xpon_phy_set_activation_arm(priv->phy, true)','WRITE_ONCE(priv->activation_armed, true)','airoha_gpon_omci_start(','mod_delayed_work(']
assert [s.index(v) for v in order]==sorted(s.index(v) for v in order)
assert 'if (ret) {\n\t\tairoha_xpon_manual_stop(priv);' in s
s=body(c,'airoha_xpon_manual_stop');assert s.index('WRITE_ONCE(priv->activation_armed, false)')<s.index('airoha_xpon_phy_set_activation_arm(priv->phy, false)')<s.index('airoha_gpon_omci_stop(')
assert 'MBI_RX_STOP | MBI_TX_STOP | MPI_RX_STOP | MPI_TX_STOP' in s and 'GPON_INT_ENABLE, 0' in s
for name in ['airoha_xpon_activation_expiry','airoha_xpon_shutdown','airoha_xpon_remove']:assert 'airoha_xpon_manual_stop(priv)' in body(c,name)
s=body(c,'activation_store');assert s.index('capable(CAP_NET_ADMIN)')<s.index('kstrtobool(')<s.index('mutex_lock(')
assert s.index('cancel_delayed_work_sync(')<s.index('mutex_lock(')
assert 'static DEVICE_ATTR(activation, 0600' in c and '#define JCOW414_ACTIVATION_SECONDS 180' in c
s=body(p,'airoha_xpon_phy_set_tx_gpio');assert s.index('mutex_lock(')<s.index('priv->manual_activation')<s.index('gpiod_set_value_cansleep(')<s.index('mutex_unlock(')
s=body(p,'airoha_xpon_phy_set_activation_arm');assert 'gpiod_set_value_cansleep(priv->tx_disable_gpio, 0)' not in s and 'gpiod_set_value_cansleep(priv->tx_disable_gpio, 1)' in s
s=body(p,'airoha_xpon_phy_power_on');assert 'if (!priv->manual_activation)\n\t\tairoha_xpon_phy_set_tx_gpio(priv, true)' in s
assert 'priv->manual_activation && submode != AIROHA_XPON_PHY_SUBMODE_GPON' in body(p,'airoha_xpon_phy_set_mode')
s=body(f,'en7571_probe');assert s.index('en7571_factory_calibration_ready')<s.index('"airoha,manual-activation"')<s.index('en7571_init(')
assert 'if (frontend_diag)\n\t\t\tpriv->lddla.ops = &en7571_frontend_diag_ops' in s
assert 'schedule_delayed_work(&priv->tick_work, HZ)' in s
assert 'reg = <0x140477' not in c+p+f
print('Default-off manual identity/transport/TX gate, expiry/removal/shutdown and calibrated frontend ordering verified')

assert '(!priv->tx_inhibited_diagnostic && !priv->manual_activation)' in body(p,'diagnostic_state_show')
assert 'ret = airoha_xpon_manual_stop(priv);' in body(c,'activation_store')
assert body(p,'airoha_xpon_phy_power_on').count('(priv->tx_inhibited_diagnostic || priv->manual_activation)')==2

# Validate the actual diagnostic reader without a hardware control/write API.
import subprocess
subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "tests/test-registration-state.py"), str(k)], check=True)

subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "tests/test-preamble-retry.py"), str(k)], check=True)

subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "tests/test-rx-delay-activation.py"), str(k)], check=True)

subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "tests/test-gpon-guard-default.py"), str(k)], check=True)
