"""Validate applied MAC/OMCI diagnostic admission and blocked activation paths."""
from pathlib import Path
import re,sys
k=Path(sys.argv[1]);c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text();b=(k/'drivers/net/ethernet/airoha/airoha_gpon_omci.c').read_text()
def body(source,name):
 start=source.index(name+'(');at=source.index('{',start);level=1;end=at+1
 while level:
  level+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[at:end]
for name in ['gpon_enable','epon_enable','airoha_gpon_omci_hw_start','gpon_link_start','epon_link_start','airoha_gpon_omci_hw_set_tcont','airoha_gpon_omci_hw_set_gem_port','airoha_gpon_omci_hw_replace_service','airoha_gpon_omci_hw_delete_service']:
 s=body(c,name);assert re.search(r'if \(priv->control_diagnostic\)\s+return -EPERM;',s),name
 first=s.index('if (priv->control_diagnostic)');assert not re.search(r'\w+\s*\(',s[:first]),name
for name in ['airoha_xpon_tx_enable','gpon_set_fe_datapath']:
 s=body(c,name);assert 'if (priv->control_diagnostic && enable)\n\t\treturn -EPERM;' in s
s=body(c,'gpon_hw_send_ploam');assert s.index('if (priv->control_diagnostic)')<s.index('gpon_wait_ploam_tx_space(')
for name,target in [('airoha_gpon_omci_start_transport','airoha_eth_xpon_control_start('),('airoha_gpon_omci_xmit','airoha_eth_xmit_xpon_oam(')]:
 s=body(b,name);assert s.index('airoha_gpon_omci_hw_is_diagnostic(')<s.index('return -EPERM;')<s.index(target)
s=body(c,'airoha_xpon_register_gpon_omci');assert s.index('if (priv->control_diagnostic)')<s.index('return 0;')<s.index('airoha_gpon_omci_start(')
s=body(c,'airoha_gpon_omci_hw_config_changed');assert s.index('if (priv->control_diagnostic)')<s.index('return;')<s.index('mod_delayed_work(')
s=body(c,'airoha_xpon_probe');assert s.index('"airoha,control-diagnostic"')<s.index('data->version != econet_en7528')<s.index('devm_phy_get(')
assert s.index('airoha_xpon_phy_tx_inhibited(')<s.index('of_parse_phandle(')<s.index('airoha_xpon_init_gpon(')
assert s.count('airoha_xpon_phy_tx_inhibited(')==2
assert 'devm_device_add_group(dev, &control_diagnostic_group)' in s
assert 'static DEVICE_ATTR_RO(control_diagnostic_state)' in c
print('MAC/OMCI diagnostic admission, transport/activation/TX/service guards and read-only status verified')
