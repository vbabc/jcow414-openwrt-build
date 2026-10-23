# SPDX-License-Identifier: GPL-2.0-only
"""Collect only generated firmware/metadata, never a host tree or user files."""
import hashlib
import os
import pathlib
import shutil

repository = pathlib.Path(__file__).resolve().parent.parent
target = pathlib.Path(os.environ['BUILD_ROOT']) / 'openwrt/bin/targets/airoha/en7528'
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
