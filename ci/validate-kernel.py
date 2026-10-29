# SPDX-License-Identifier: GPL-2.0-only
"""Check the applied guard and compile/inspect the actual diagnostic board."""
import os
import pathlib
import subprocess

repository = pathlib.Path(__file__).resolve().parent.parent
source = pathlib.Path(os.environ['BUILD_ROOT']) / 'openwrt'
artifacts = repository / 'artifacts'
kernels = list((source / 'build_dir').glob('target-*/linux-airoha_en7528/linux-6.18.55'))
assert len(kernels) == 1
kernel = kernels[0]

target_config = (source / 'target/linux/airoha/en7528/config-6.18').read_text()
assert 'CONFIG_MIPS_RAW_APPENDED_DTB=y\n' in target_config
assert 'CONFIG_MIPS_ELF_APPENDED_DTB=y\n' not in target_config

led_driver = (kernel / 'drivers/leds/trigger/ledtrig-netdev.c').read_text()
led_activate = led_driver[led_driver.index('static int netdev_trig_activate('):led_driver.index('static void netdev_trig_deactivate(')]
assert 'if (dev && dev_name(dev))' in led_activate, 'Missing protection for unnamed LED hardware-control device'
driver = (kernel / 'drivers/net/optical/airoha/en7571_main.c').read_text()
guard = (repository / 'tests/en7571-calibration-guard.c.inc').read_text().strip()
assert guard in driver, 'Prepared driver does not contain the tested guard body'
probe = driver[driver.index('static int en7571_probe('):driver.index('static void en7571_remove(')]
assert probe.index('en7571_factory_calibration_ready') < probe.index('ret = en7571_init(')
variant = os.environ['VARIANT']
if variant in ('probe-only', 'frontend-diag', 'phy-diag', 'mac-diag', 'rx-diag', 'activation-test', 'ap-ready'):
    assert probe.index('"airoha,diagnostic-only"') < probe.index('ret = en7571_init(')
    assert 'return 0;' in probe[probe.index('"airoha,diagnostic-only"'):probe.index('ret = en7571_init(')]
if variant == 'frontend-diag':
    subprocess.run(['python3', str(repository / 'ci/validate-frontend.py'), str(kernel / 'drivers/net/optical/airoha/en7571_main.c')], check=True)
if variant in ('phy-diag', 'mac-diag', 'rx-diag'):
    subprocess.run(['python3', str(repository / 'ci/validate-phy.py'), str(kernel)], check=True)
    subprocess.run(['python3', str(repository / 'tests/test-phy-inhibit.py'), str(kernel)], check=True)
preprocessed = artifacts / 'diagnostic.preprocessed.dts'
with preprocessed.open('w') as output:
    subprocess.run(['cpp', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                    '-I', str(kernel / 'include'), '-I', str(source / 'target/linux/airoha/dts'),
                    str(source / 'target/linux/airoha/dts/en7528_jiofiber_jcow414.dts')], stdout=output, check=True)
dtb = artifacts / 'diagnostic-review.dtb'
with (artifacts / 'dtb-compile.log').open('w') as errors:
    subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(preprocessed)], stderr=errors, check=True)


def get(node, prop, kind=None):
    command = ['fdtget'] + (['-t', kind] if kind else []) + [str(dtb), node, prop]
    return subprocess.check_output(command, text=True).strip()


assert get('/chosen', 'stdout-path') == '/soc/serial@1fbf0000:115200'
assert get('/soc/serial@1fbf0000', 'clock-frequency', 'u') == '1843200'
for address in ['9', '10', '11', '12']:
    assert get('/soc/switch@1fb58000/mdio/ethernet-phy@' + address, 'status') == 'okay'
assert get('/soc/i2c0@1fbf8000', 'status') == ('disabled' if variant in ('baseline', 'ap-ready') else 'okay')
assert get('/soc/phy@1faf0000', 'status') == ('okay' if variant in ('phy-diag', 'mac-diag', 'rx-diag', 'activation-test') else 'disabled')
for node in ['/soc/xmac@1fb60000', '/soc/ethernet@1fb50000/ethernet@2']:
    assert get(node, 'status') == ('okay' if variant in ('mac-diag', 'rx-diag', 'activation-test') else 'disabled')
assert get('/soc/spi@1fa10000/flash@0/partitions/partition@ddc0000/nvmem-layout/calibration@140477', 'reg', 'x') == '140477 e1'
if variant in ('probe-only', 'frontend-diag', 'phy-diag', 'mac-diag', 'rx-diag', 'activation-test', 'ap-ready'):
    assert get('/soc/i2c0@1fbf8000/lddla@70', 'compatible') == 'airoha,en7571'
    assert get('/soc/i2c0@1fbf8000/lddla@70', 'nvmem-cell-names') == 'calibration'
    node = '/soc/i2c0@1fbf8000/lddla@70'
    if variant == 'probe-only':
        get(node, 'airoha,diagnostic-only')
    elif variant == 'frontend-diag':
        properties = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).splitlines()
        assert 'airoha,diagnostic-only' not in properties
        get(node, 'airoha,frontend-diagnostic')
        cells = get(node, 'tx-disable-gpios', 'u').split()
        assert cells == [get('/soc/system-controller@1fbf0200/pinctrl', 'phandle', 'u'), '16', '0'], cells
    else:
        properties = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).splitlines()
        assert not set(properties) & {'airoha,diagnostic-only', 'airoha,frontend-diagnostic', 'tx-disable-gpios'}
        get(node, 'airoha,manual-activation' if variant in ('activation-test', 'ap-ready') else 'airoha,phy-diagnostic')
        assert get(node, 'phy-names') == 'xpon'
        phy = '/soc/phy@1faf0000'
        assert get(node, 'phys', 'u') == get(phy, 'phandle', 'u')
        get(phy, 'airoha,manual-activation' if variant in ('activation-test', 'ap-ready') else 'airoha,tx-inhibited-diagnostic')
        assert get(phy, 'compatible') == 'airoha,en7528-xpon-phy'
        assert get(phy, 'reg', 'x') == '1faf0000 600'
        assert get(phy, 'tx-disable-gpios', 'u').split() == [get('/soc/system-controller@1fbf0200/pinctrl', 'phandle', 'u'), '16', '0']
print('Applied calibration guard and diagnostic DTB verified:', variant)

if variant in ('mac-diag', 'rx-diag', 'activation-test', 'ap-ready'):
    if variant not in ('activation-test', 'ap-ready'):
        subprocess.run(['python3', str(repository / 'ci/validate-mac.py'), str(kernel)], check=True)
        subprocess.run(['python3', str(repository / 'tests/test-mac-inhibit.py'), str(kernel)], check=True)
    mac = '/soc/xmac@1fb60000'
    get(mac, 'airoha,manual-activation' if variant in ('activation-test', 'ap-ready') else 'airoha,control-diagnostic')
    assert get(mac, 'optical-frontends', 'u') == get(node, 'phandle', 'u')
    assert get(mac, 'optical-frontend-names') == 'pon'
    assert get(node, '#optical-frontend-cells', 'u') == '0'
    assert get(mac, 'reg', 'x') == '1fb60000 10000 1fa2ff24 4'
    assert get(mac, 'ethernet', 'u') == get('/soc/ethernet@1fb50000/ethernet@2', 'phandle', 'u')
    agent = (source / 'package/utils/airoha/omci-agent/files/etc/config/omci').read_text()
    assert "option enabled '0'" in agent and "option dying_gasp '0'" in agent
    assert "option reboot '0'" in agent
    defaults = (source / 'files/etc/uci-defaults/99-jcow414-mac-diagnostic').read_text()
    assert 'delete network.wan' in defaults and "dhcp.lan.ignore='1'" in defaults

if variant == 'rx-diag':
    get('/soc/xmac@1fb60000', 'airoha,rx-diagnostic')
    subprocess.run(['python3', str(repository / 'ci/validate-rx.py'), str(kernel)], check=True)
    subprocess.run(['python3', str(repository / 'tests/test-rx-inhibit.py'), str(kernel)], check=True)

if variant in ('activation-test', 'ap-ready'):
    for node, absent in [('/soc/xmac@1fb60000', ['airoha,control-diagnostic', 'airoha,rx-diagnostic']),
                         ('/soc/phy@1faf0000', ['airoha,tx-inhibited-diagnostic']),
                         ('/soc/i2c0@1fbf8000/lddla@70', ['airoha,phy-diagnostic'])]:
        props = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True).splitlines()
        assert not set(props) & set(absent)
    subprocess.run(['python3', str(repository / 'ci/validate-activation.py'), str(kernel)], check=True)
    subprocess.run(['python3', str(repository / 'tests/test-activation-gate.py'), str(kernel)], check=True)

if variant == 'ap-ready':
    assert get('/soc/i2c0@1fbf8000/lddla@70', 'status') == 'disabled'
    assert not (source / 'files/usr/share/luci/menu.d/jcow414-activation.json').exists()
    defaults = (source / 'files/etc/uci-defaults/99-jcow414-ap-ready').read_text()
    assert "dhcp.lan.ignore='1'" in defaults
    assert '/etc/init.d/dnsmasq disable' in defaults
    assert "trigger='netdev'" in defaults
    print('AP candidate: I2C/frontend/PHY/MAC/GDM2 disabled, no activation UI; DHCP-off defaults verified')
