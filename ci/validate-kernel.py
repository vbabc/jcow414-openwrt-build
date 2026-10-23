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
driver = (kernel / 'drivers/net/optical/airoha/en7571_main.c').read_text()
guard = (repository / 'tests/en7571-calibration-guard.c.inc').read_text().strip()
assert guard in driver, 'Prepared driver does not contain the tested guard body'
probe = driver[driver.index('static int en7571_probe('):driver.index('static void en7571_remove(')]
assert probe.index('en7571_factory_calibration_ready') < probe.index('ret = en7571_init(')
variant = os.environ['VARIANT']
if variant == 'probe-only':
    assert probe.index('"airoha,diagnostic-only"') < probe.index('ret = en7571_init(')
    assert 'return 0;' in probe[probe.index('"airoha,diagnostic-only"'):probe.index('ret = en7571_init(')]
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


assert get('/soc/i2c0@1fbf8000', 'status') == ('okay' if variant == 'probe-only' else 'disabled')
for node in ['/soc/phy@1faf0000', '/soc/xmac@1fb60000', '/soc/ethernet@1fb50000/ethernet@2']:
    assert get(node, 'status') == 'disabled'
assert get('/soc/spi@1fa10000/flash@0/partitions/partition@ddc0000/nvmem-layout/calibration@140477', 'reg', 'x') == '140477 e1'
if variant == 'probe-only':
    assert get('/soc/i2c0@1fbf8000/lddla@70', 'compatible') == 'airoha,en7571'
    assert get('/soc/i2c0@1fbf8000/lddla@70', 'nvmem-cell-names') == 'calibration'
    get('/soc/i2c0@1fbf8000/lddla@70', 'airoha,diagnostic-only')
print('Applied calibration guard and diagnostic DTB verified:', variant)
