# SPDX-License-Identifier: GPL-2.0-only
"""Bounded, exact-environment toolchain cache experiment; never caches a kernel."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import time

LIMIT = 2 * 1024**3
SCHEMA = 'jcow414-tools-v2'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def normalized_config(text):
    return '\n'.join(line for line in text.splitlines()
                     if not line.startswith(('CONFIG_VERSION_', '# CONFIG_VERSION_', 'CONFIG_CCACHE_DIR='))) + '\n'


def driver_only_patch(text):
    pairs = re.findall(r'^(?:--- a/(\S+)|\+\+\+ b/(\S+))', text, re.M)
    paths = [a or b for a, b in pairs]
    return bool(paths) and all(path.startswith(('drivers/net/optical/airoha/', 'target/linux/airoha/dts/'))
                               or path in ('drivers/leds/trigger/ledtrig-netdev.c',
                                           'drivers/phy/airoha/phy-airoha-xpon.c',
                                           'include/linux/phy/phy-airoha-xpon.h') for path in paths)


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or len(path.parts) < 2:
        return False
    first, second = path.parts[:2]
    return ((first == 'staging_dir' and (second == 'host' or second.startswith('toolchain-')))
            or (first == 'build_dir' and (second == 'host' or second.startswith('toolchain-'))))


def identity(repository, source):
    special_patches = {p.name: digest(p) for p in sorted((repository / 'patches').glob('*.patch'))
                       if not driver_only_patch(p.read_text())}
    inputs = {
        'schema': SCHEMA, 'source': json.loads((repository / 'source.lock.json').read_text()),
        'feeds': json.loads((repository / 'feeds.lock.json').read_text()),
        'config': normalized_config((source / '.config').read_text()),
        'kernel_template_sha256': digest(source / 'target/linux/airoha/en7528/config-6.18'),
        'image_recipe_sha256': digest(source / 'target/linux/airoha/image/en7528.mk'),
        'non_driver_patch_hashes': special_patches,
        'patch_names': sorted(p.name for p in (repository / 'patches').glob('*.patch')),
        'host': {'machine': platform.machine(), 'image': os.environ.get('ImageOS'),
                 'image_version': os.environ.get('ImageVersion'),
                 'gcc': command('gcc', '--version').splitlines()[0],
                 'gxx': command('g++', '--version').splitlines()[0],
                 'libc': command('getconf', 'GNU_LIBC_VERSION'),
                 'packages': command('dpkg-query', '-W', '-f=${Package}=${Version}\n',
                                     'gcc', 'g++', 'binutils', 'libc6', 'make', 'zlib1g')},
        'absolute_source_path': str(source),
    }
    key = SCHEMA + '-tools-' + hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {'key': key, 'inputs': inputs}


def normalize_source_times(source):
    # OpenWrt find_md5 hashes recipe mtimes. A fresh checkout would otherwise
    # invalidate prepared stamps despite identical pinned recipe contents.
    epoch = int(command('git', 'show', '-s', '--format=%ct', 'HEAD', cwd=source))
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=source).split(b'\0')
    for raw in names:
        if not raw:
            continue
        path = source / os.fsdecode(raw)
        if path.is_file() and not path.is_symlink():
            os.utime(path, (epoch, epoch))
    os.utime(source / '.config', (epoch, epoch))
    for path in (source / 'target/linux/airoha/patches-6.18').glob('*.patch'):
        os.utime(path, (epoch, epoch))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['identity', 'pack', 'unpack'])
    args = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    source = Path(os.environ['BUILD_ROOT']).resolve() / 'openwrt'
    artifacts = repository / 'artifacts'
    cache = repository / '.cache/toolchain-experiment'
    archive = cache / 'tools.tar.zst'
    record = artifacts / 'toolchain-cache-identity.json'
    started = time.monotonic()
    if args.operation == 'identity':
        normalize_source_times(source)
        data = identity(repository, source)
        record.write_text(json.dumps(data, indent=2) + '\n')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('key=' + data['key'] + '\n')
        print('Exact-environment toolchain cache key:', data['key'])
        return
    data = json.loads(record.read_text())
    assert data == identity(repository, source), 'Cache compatibility changed after preparation'
    if args.operation == 'pack':
        cache.mkdir(parents=True, exist_ok=True)
        assert not archive.exists(), 'Refuse to replace an experiment archive'
        roots = [p.relative_to(source).as_posix() for pattern in
                 ('staging_dir/host', 'staging_dir/toolchain-*', 'build_dir/host', 'build_dir/toolchain-*')
                 for p in sorted(source.glob(pattern)) if p.is_dir() and not p.is_symlink()]
        assert any(p.startswith('staging_dir/toolchain-') for p in roots)
        assert all(safe_member(p) for p in roots)
        subprocess.run(['tar', '-I', 'zstd -T2 -3', '-cf', str(archive), '-C', str(source), '--', *roots], check=True)
        assert archive.stat().st_size <= LIMIT, 'Archive exceeds 2 GiB; do not save or run warm pass'
        manifest = dict(data, bytes=archive.stat().st_size, sha256=digest(archive), roots=roots)
        (cache / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    else:
        manifest = json.loads((cache / 'manifest.json').read_text())
        assert manifest['key'] == data['key'] and manifest['inputs'] == data['inputs']
        assert archive.stat().st_size == manifest['bytes'] <= LIMIT
        assert digest(archive) == manifest['sha256'], 'Archive checksum mismatch'
        members = command('tar', '--zstd', '-tf', str(archive)).splitlines()
        assert members and all(safe_member(name) for name in members), 'Unexpected cache member'
        # defconfig may create host prerequisite links, but must not have built
        # a compiler or installed cached host tools before this restore.
        assert not list(source.glob('staging_dir/host/stamp/.tools_compile*'))
        for pattern in ('staging_dir/toolchain-*', 'build_dir/host', 'build_dir/toolchain-*'):
            assert not list(source.glob(pattern)), 'Refuse to overlay an existing toolchain'
        subprocess.run(['tar', '--zstd', '-xf', str(archive), '-C', str(source)], check=True)
        compilers = list(source.glob('staging_dir/toolchain-*/bin/*-openwrt-linux-*-gcc'))
        assert len(compilers) == 1, 'Expected one target compiler'
        subprocess.run([str(compilers[0]), '--version'], check=True)
        assert not list(source.glob('build_dir/target-*')), 'Kernel/target objects must remain fresh'
    result = {'operation': args.operation, 'key': data['key'], 'bytes': archive.stat().st_size,
              'seconds': round(time.monotonic() - started, 3), 'kernel_or_target_objects_cached': False}
    (artifacts / ('toolchain-cache-' + args.operation + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
