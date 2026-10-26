# SPDX-License-Identifier: GPL-2.0-only
"""Collect only generated firmware/metadata, never a host tree or user files."""
import hashlib
import os
import pathlib
import shutil
import subprocess

repository = pathlib.Path(__file__).resolve().parent.parent
source = pathlib.Path(os.environ['BUILD_ROOT']) / 'openwrt'
target = source / 'bin/targets/airoha/en7528'
kernels = list((source / 'build_dir').glob('target-*/linux-airoha_en7528/linux-6.18.55'))
assert len(kernels) == 1, 'Cannot identify the built kernel'
kernel = kernels[0]
resolved_config = (kernel / '.config').read_text()
assert 'CONFIG_MIPS_RAW_APPENDED_DTB=y\n' in resolved_config, 'Built kernel cannot carry the raw-appended DTB'
assert 'CONFIG_MIPS_ELF_APPENDED_DTB=y\n' not in resolved_config, 'Built kernel still uses the incompatible DTB mode'
shutil.copyfile(kernel / '.config', repository / 'artifacts/kernel.config')
shutil.copyfile(kernel / 'System.map', repository / 'artifacts/kernel.System.map')
with (repository / 'artifacts/kernel-elf-header.txt').open('w') as output:
    subprocess.run(['readelf', '-h', str(kernel / 'vmlinux')], stdout=output, check=True)
output = repository / 'artifacts/firmware'
output.mkdir(parents=True, exist_ok=True)
assert target.is_dir(), 'No target output directory'
images = []
for item in sorted(target.iterdir()):
    if not item.is_file():
        continue
    if item.suffix in ['.bin', '.trx', '.json', '.manifest', '.buildinfo'] or 'sysupgrade' in item.name or item.name == 'sha256sums':
        shutil.copyfile(item, output / item.name)
        if item.suffix in ['.bin', '.trx'] or 'sysupgrade' in item.name:
            images.append(item.name)
assert images, 'Build completed without a firmware image'
hashes = []
for item in sorted(output.iterdir()):
    hashes.append(f'{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}')
(repository / 'artifacts/artifacts.sha256').write_text('\n'.join(hashes) + '\n')
print('Collected', len(images), 'firmware files; image review and hardware tests remain required')
