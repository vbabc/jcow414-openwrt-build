# SPDX-License-Identifier: GPL-2.0-only
"""Fetch pinned public inputs and configure an isolated diagnostic build."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('variant', choices=['baseline', 'probe-only'])
args = parser.parse_args()
repository = pathlib.Path(__file__).resolve().parent.parent
build_root = pathlib.Path(os.environ['BUILD_ROOT']).resolve()
source = build_root / 'openwrt'
artifacts = repository / 'artifacts'
artifacts.mkdir(exist_ok=True)
build_root.mkdir(parents=True, exist_ok=True)
assert not source.exists(), 'Refusing to overwrite an existing build tree'


def run(*command, cwd=repository):
    subprocess.run(command, cwd=cwd, check=True)


def checkout(path, url, revision):
    path.mkdir(parents=True)
    run('git', 'init', '-q', str(path))
    run('git', '-C', str(path), 'remote', 'add', 'origin', url)
    run('git', '-C', str(path), 'fetch', '--depth=1', 'origin', revision)
    run('git', '-C', str(path), 'checkout', '--detach', revision)
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == revision


run('gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Itests',
    'tests/test-en7571-calibration-guard.c', '-o', str(build_root / 'guard-test'))
with (artifacts / 'calibration-guard-test.log').open('w') as output:
    subprocess.run([str(build_root / 'guard-test')], stdout=output, check=True)

lock = json.loads((repository / 'source.lock.json').read_text())
checkout(source, lock['repository'], lock['revision'])
feeds = json.loads((repository / 'feeds.lock.json').read_text())
feed_lines = []
for feed in feeds:
    checkout(source / 'feeds' / feed['name'], feed['url'], feed['revision'])
    feed_lines.append(f"src-git {feed['name']} {feed['url']}^{feed['revision']}")
(source / 'feeds.conf').write_text('\n'.join(feed_lines) + '\n')
download_cache = repository / '.cache/downloads'
download_cache.mkdir(parents=True, exist_ok=True)
(source / 'dl').symlink_to(download_cache, target_is_directory=True)
run('./scripts/feeds', 'update', '-i', cwd=source)
run('./scripts/feeds', 'install', '-a', cwd=source)
run('python3', str(repository / 'ci/prepare-board.py'), str(source))
kernel_patches = source / 'target/linux/airoha/patches-6.18'
shutil.copyfile(repository / 'patches/999-jcow414-require-en7571-calibration.patch', kernel_patches / '999-jcow414-require-en7571-calibration.patch')
shutil.copyfile(repository / 'patches/1001-led-netdev-guard-unnamed-hw-device.patch', kernel_patches / '1001-led-netdev-guard-unnamed-hw-device.patch')
if args.variant == 'probe-only':
    shutil.copyfile(repository / 'patches/1000-en7571-diagnostic-only.patch', kernel_patches / '1000-en7571-diagnostic-only.patch')
    patch = repository / 'patches/jcow414-probe-only-board.patch'
    run('git', 'apply', '--check', str(patch), cwd=source)
    run('git', 'apply', str(patch), cwd=source)

if args.variant == 'baseline':
    # Preserve the captured configuration, but distinguish the boot fix from
    # the pon-dev1 image that panicked before device-tree discovery.
    seed = (repository / 'config.lxc.seed').read_text()
    assert 'CONFIG_VERSION_NUMBER="pon-dev1"' in seed
    seed = seed.replace('CONFIG_VERSION_NUMBER="pon-dev1"', 'CONFIG_VERSION_NUMBER="pon-dev2"', 1)
else:
    seed = (repository / 'config.seed').read_text()
    seed += f'CONFIG_VERSION_NUMBER="pon-{args.variant}-2"\n'
seed = '\n'.join(line for line in seed.splitlines() if not line.startswith(('CONFIG_CCACHE', 'CONFIG_DEVEL=')) and line not in ('# CONFIG_CCACHE is not set', '# CONFIG_DEVEL is not set')) + '\n'
# CCACHE has a prompt conditional on DEVEL in the pinned Config-devel.in;
# without DEVEL the user value is hidden and defconfig clears it.
seed += 'CONFIG_DEVEL=y\n'
seed += 'CONFIG_CCACHE=y\n'
seed += f'CONFIG_CCACHE_DIR="{repository / ".cache/ccache"}"\n'
(source / '.config').write_text(seed)
run('make', '-j1', 'defconfig', cwd=source)
config = (source / '.config').read_text()
for selected in ['TARGET_airoha_en7528_DEVICE_jiofiber_jcow414', 'PACKAGE_luci-app-omci', 'PACKAGE_omci-agent']:
    assert f'CONFIG_{selected}=y\n' in config, f'Missing configuration: {selected}'
assert 'CONFIG_DEVEL=y\n' in config and 'CONFIG_CCACHE=y\n' in config
run('git', 'diff', '--check', cwd=source)
with (artifacts / 'config.seed.lock').open('w') as output:
    subprocess.run(['./scripts/diffconfig.sh'], cwd=source, stdout=output, check=True)
with (artifacts / 'source-changes.patch').open('w') as output:
    subprocess.run(['git', 'diff'], cwd=source, stdout=output, check=True)
for name in ['source.lock.json', 'feeds.lock.json']:
    shutil.copyfile(repository / name, artifacts / name)
shutil.copytree(repository / 'patches', artifacts / 'patches', dirs_exist_ok=True)
manifest = {
    'variant': args.variant,
    'source': lock,
    'build_repository_commit': os.environ.get('GITHUB_SHA', 'local-validation'),
    'firmware_seed_sha256': hashlib.sha256(seed.encode()).hexdigest(),
    'optical_mac_phy_enabled': False,
    'hardware_validated': False,
    'raw_appended_dtb_required': True,
    'patches_sha256': {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted((repository / 'patches').glob('*.patch'))
    },
}
(artifacts / 'build-provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Pinned source, paired patches and diagnostic configuration prepared:', args.variant)
