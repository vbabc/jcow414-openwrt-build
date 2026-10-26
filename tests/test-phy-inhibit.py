# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual applied GPIO functions with simulated pins, then test both modes."""
from pathlib import Path
import subprocess
import sys
import tempfile
import resource

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

source = (Path(sys.argv[1]) / 'drivers/phy/airoha/phy-airoha-xpon.c').read_text()


def extract(name):
    start = source.index(name + '(')
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


shim = '''#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
struct gpio_desc { int value; };
struct airoha_xpon_phy { struct gpio_desc *tx_disable_gpio; bool tx_inhibited_diagnostic; };
struct phy { struct airoha_xpon_phy *data; };
static void gpiod_set_value_cansleep(struct gpio_desc *g, int v) { g->value = v; }
static int gpiod_get_value_cansleep(struct gpio_desc *g) { return g ? g->value : -EINVAL; }
static void *phy_get_drvdata(struct phy *p) { return p->data; }
'''
body = ('static void\n' + extract('airoha_xpon_phy_set_tx_gpio') + '\nint\n' +
        extract('airoha_xpon_phy_set_tx_enable') + '\nint\n' + extract('airoha_xpon_phy_tx_inhibited'))
tests = '''
int main(void) {
    struct gpio_desc pin = { .value = 1 };
    struct airoha_xpon_phy p = { .tx_disable_gpio = &pin };
    struct phy phy = { .data = &p }, empty = { 0 };
    assert(airoha_xpon_phy_set_tx_enable(NULL, true) == -EINVAL);
    assert(airoha_xpon_phy_set_tx_enable(&empty, true) == -ENODEV);
    assert(airoha_xpon_phy_tx_inhibited(NULL) == -EINVAL);
    assert(airoha_xpon_phy_set_tx_enable(&phy, true) == 0 && pin.value == 0);
    assert(airoha_xpon_phy_set_tx_enable(&phy, false) == 0 && pin.value == 1);
    assert(airoha_xpon_phy_tx_inhibited(&phy) == -EOPNOTSUPP);
    p.tx_inhibited_diagnostic = true;
    assert(airoha_xpon_phy_tx_inhibited(&phy) == 1);
    assert(airoha_xpon_phy_set_tx_enable(&phy, true) == -EPERM && pin.value == 1);
    assert(airoha_xpon_phy_set_tx_enable(&phy, false) == 0 && pin.value == 1);
    pin.value = 0;
    assert(airoha_xpon_phy_tx_inhibited(&phy) == 0);
    airoha_xpon_phy_set_tx_gpio(&p, true);
    assert(pin.value == 1);
    airoha_xpon_phy_set_tx_gpio(&p, false);
    assert(pin.value == 1);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='phy-inhibit-test-') as directory:
    work = Path(directory)
    cfile, binary = work / 'test.c', work / 'test'
    cfile.write_text(shim + body + tests)
    subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    for name, old, new in [
        ('central-force-high', 'if (priv->tx_inhibited_diagnostic)\n\t\tenable = false;', ''),
        ('exported-enable-rejection', 'if (priv->tx_inhibited_diagnostic && enable)\n\t\treturn -EPERM;', ''),
    ]:
        assert old in body
        cfile.write_text(shim + body.replace(old, new, 1) + tests)
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(cfile), '-o', str(binary)], check=True)
        failed = subprocess.run([str(binary)], capture_output=True)
        assert failed.returncode != 0, name
print('Actual GPIO functions passed normal/diagnostic/error tests; two unsafe mutations rejected')
