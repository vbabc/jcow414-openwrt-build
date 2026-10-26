# SPDX-License-Identifier: GPL-2.0-only
"""Small Linux fixtures: cache admission, complete round trip and fail-closed cases."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('toolchain_cache', REPO / 'ci/toolchain-cache.py')
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class CacheTests(unittest.TestCase):
    def test_only_metadata_is_ignored_by_config_key(self):
        base = 'CONFIG_TARGET_x=y\nCONFIG_VERSION_NUMBER="a"\nCONFIG_CCACHE_DIR="/one"\n'
        self.assertEqual(cache.normalized_config(base), cache.normalized_config(base.replace('"a"', '"b"').replace('/one', '/two')))
        self.assertNotEqual(cache.normalized_config(base), cache.normalized_config(base.replace('TARGET_x', 'TARGET_y')))

    def test_patch_classification_includes_deleted_headers(self):
        self.assertTrue(cache.driver_only_patch('--- a/drivers/net/optical/airoha/en7571_main.c\n+++ b/drivers/net/optical/airoha/en7571_main.c\n'))
        self.assertFalse(cache.driver_only_patch('--- a/include/linux/test.h\n+++ /dev/null\n--- /dev/null\n+++ b/drivers/net/optical/airoha/test.c\n'))

    def test_archive_whitelist(self):
        for name in ('staging_dir/host/bin/tool', 'build_dir/toolchain-mips/gcc/.built'):
            self.assertTrue(cache.safe_member(name))
        for name in ('/etc/passwd', '../tool', 'staging_dir/host/../../etc/test',
                     'build_dir/target-mips/kernel', 'staging_dir/target-mips/lib/test', '.git/config'):
            self.assertFalse(cache.safe_member(name))

    def test_round_trip_and_rejections(self):
        with tempfile.TemporaryDirectory(prefix='jcow414-cache-test-') as directory:
            root = Path(directory)
            repo, source = root / 'repo', root / 'build/openwrt'
            for path in (repo / 'ci', repo / 'artifacts', repo / 'patches', source / 'target/linux/airoha/en7528', source / 'target/linux/airoha/image'):
                path.mkdir(parents=True)
            shutil.copyfile(REPO / 'ci/toolchain-cache.py', repo / 'ci/toolchain-cache.py')
            for name in ('source.lock.json', 'feeds.lock.json'):
                shutil.copyfile(REPO / name, repo / name)
            (source / '.config').write_text('CONFIG_TARGET_test=y\nCONFIG_VERSION_NUMBER="test"\n')
            (source / 'target/linux/airoha/en7528/config-6.18').write_text('CONFIG_TEST=y\n')
            (source / 'target/linux/airoha/image/en7528.mk').write_text('# synthetic fixture\n')
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Cache Test', '-c', 'user.email=cache-test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            env = dict(os.environ, BUILD_ROOT=str(root / 'build'), GITHUB_OUTPUT=str(root / 'output'))

            def run(operation, success=True):
                result = subprocess.run([sys.executable, str(repo / 'ci/toolchain-cache.py'), operation], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result

            run('identity')
            host = source / 'staging_dir/host/bin'
            host.mkdir(parents=True)
            (host / 'tool').write_text('synthetic host tool\n')
            compiler = source / 'staging_dir/toolchain-mips/bin/mipsel-openwrt-linux-musl-gcc'
            compiler.parent.mkdir(parents=True)
            compiler.write_text('#!/bin/sh\necho synthetic-cache-test-compiler\n')
            compiler.chmod(0o755)
            stamp = source / 'build_dir/toolchain-mips/gcc/.built'
            stamp.parent.mkdir(parents=True)
            stamp.write_text('synthetic stamp\n')
            run('pack')
            for relative in ('staging_dir', 'build_dir'):
                shutil.rmtree(source / relative)
            # Fresh defconfig bootstrap is allowed; prior compiled tools are not.
            (source / 'staging_dir/host/bin').mkdir(parents=True)
            run('unpack')
            self.assertEqual(stamp.read_text(), 'synthetic stamp\n')
            self.assertFalse(list(source.glob('build_dir/target-*')))
            run('unpack', success=False)
            for relative in ('staging_dir', 'build_dir'):
                shutil.rmtree(source / relative)
            original = (source / '.config').read_text()
            (source / '.config').write_text(original.replace('TARGET_test', 'TARGET_other'))
            run('unpack', success=False)
            (source / '.config').write_text(original)
            archive = repo / '.cache/toolchain-experiment/tools.tar.zst'
            with archive.open('ab') as output:
                output.write(b'corrupt')
            run('unpack', success=False)


if __name__ == '__main__':
    unittest.main()
