"""Exercise the real MAC callback and PHY writer with actual family selection."""
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
kernel = Path(sys.argv[1])
mac = (kernel / 'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
header = (kernel / 'drivers/net/ethernet/airoha/airoha_xpon.h').read_text()
phy = (kernel / 'drivers/phy/airoha/phy-airoha-xpon.c').read_text()

def function(source, signature):
    start = source.index(signature)
    at = source.index('{', start)
    end, depth = at + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

callback = function(mac, 'static void gpon_cb_set_overhead(')
writer = function(phy, 'int airoha_xpon_phy_set_gpon_overhead(')
families = {}
for name in ['en7528', 'en7523', 'en751221']:
    at = mac.index('static const struct airoha_xpon_match_data ' + name + '_xpon_data = {')
    block = mac[at:mac.index('\n};', at)]
    match = re.search(r'\.gpon_guard_bits_override\s*=\s*([A-Z0-9_]+),', block)
    families[name] = match[1] if match else '0'
assert families == {'en7528': 'GPON_PHY_GUARD_BIT_NUM', 'en7523': '0',
                    'en751221': 'GPON_PHY_GUARD_BIT_NUM_EN751221'}

defines = ''
for source, names in [
    (header, ['GPON_PLOu_OVERHEAD', 'GPON_PLOu_GUARD_BIT', 'GPON_PLOu_PRMBL_TYPE1_2',
              'GPON_PLOu_PRMBL_TYPE3', 'GPON_PLOu_DELM_BIT', 'GPON_PRE_ASSIGNED_DLY',
              'PRE_DLY_EN', 'PRE_DLY_MASK', 'GPON_PHY_GUARD_BIT_NUM',
              'GPON_PHY_GUARD_BIT_NUM_EN751221']),
    (phy, ['XPON_GPON_PREAMBLE', 'XPON_GPON_DELIMITER_GUARD',
           'XPON_GPON_PREAMBLE_GUARD_MASK', 'XPON_GPON_PREAMBLE_T1_MASK',
           'XPON_GPON_PREAMBLE_T2_MASK', 'XPON_GPON_PREAMBLE_T3_MASK',
           'XPON_GPON_TX_ENABLE_PATTERN'])]:
    for name in names:
        match = re.search(r'^#define\s+' + name + r'\s+([^\n]+)', source, re.M)
        assert match, name
        defines += '#define ' + name + ' ' + match[1] + '\n'

shim = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <errno.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define BIT(n) (1u << (n))
#define GENMASK(h,l) ((~0u >> (31-(h))) & (~0u << (l)))
#define FIELD_PREP(m,v) (((u32)(v) << __builtin_ctz(m)) & (m))
static void dev_info(void *dev,const char *format,...) {(void)dev;(void)format;}
#define dev_warn(...) do {} while (0)
#define dev_dbg(...) do {} while (0)
struct airoha_xpon_phy { void *dev; };
struct phy { struct airoha_xpon_phy *data; };
struct match { u8 gpon_guard_bits_override; bool gpon_rearm_tx_on_overhead; };
struct xpon_priv { const struct match *match_data; struct phy *phy; void *dev; void *frontend; };
static u32 mac_regs[1024], phy_regs[1024];
static unsigned enables, rearms, adjustments, mac_writes, phy_writes;
static u32 airoha_xpon_phy_read(struct airoha_xpon_phy *p, u32 r) {(void)p; return phy_regs[r/4];}
static void airoha_xpon_phy_write(struct airoha_xpon_phy *p,u32 r,u32 v) {(void)p; phy_writes++;phy_regs[r/4]=v;}
static int airoha_xpon_phy_get_active_gpon(struct phy *p,struct airoha_xpon_phy **out) {*out=p->data;return 0;}
static void gpon_write(struct xpon_priv *p,u32 r,u32 v) {(void)p;mac_writes++;mac_regs[r/4]=v;}
static int airoha_xpon_tx_enable(struct xpon_priv *p,bool on) {(void)p;assert(on);enables++;return 0;}
static int airoha_xpon_tx_rearm(void *dev,void *f) {(void)dev;(void)f;rearms++;return 0;}
static void gpon_adjust_mac_rx_delay(struct xpon_priv *p) {(void)p;adjustments++;}
'''
main = r'''
static void exercise(u8 override, u8 announced,u8 expected,bool rearm) {
 struct match m={override,rearm};struct airoha_xpon_phy frontend={0};
 struct phy phy={&frontend};struct xpon_priv p={&m,&phy,0,0};
 const u8 delim[3]={0xab,0x59,0x83};
 memset(mac_regs,0,sizeof(mac_regs));memset(phy_regs,0xff,sizeof(phy_regs));
 enables=rearms=adjustments=mac_writes=phy_writes=0;
 gpon_cb_set_overhead(&p,announced,0,0,0xaa,delim,true,0x1234);
 assert(mac_regs[GPON_PLOu_GUARD_BIT/4]==expected);
 assert(phy_regs[XPON_GPON_PREAMBLE/4]==(0xaa000000u|expected));
 assert(phy_regs[XPON_GPON_DELIMITER_GUARD/4]==0xaaab5983);
 assert(mac_regs[GPON_PLOu_PRMBL_TYPE1_2/4]==0);
 assert(mac_regs[GPON_PRE_ASSIGNED_DLY/4]==0x80001234);
 assert(mac_writes==3 && phy_writes==2 && adjustments==1);
 assert(enables==(unsigned)rearm && rearms==(unsigned)rearm);
 /* Nonzero T1/T2 confirms the existing field mapping stays intact. */
 gpon_cb_set_overhead(&p,announced,3,5,0x55,delim,false,0);
 assert(phy_regs[XPON_GPON_PREAMBLE/4]==(0x55030500u|expected));
 assert(mac_regs[GPON_PLOu_PRMBL_TYPE1_2/4]==0x00030005);
 assert(mac_regs[GPON_PRE_ASSIGNED_DLY/4]==0);
}
int main(void) {
 exercise(EN7528_GUARD,32,20,true);
 exercise(EN7528_GUARD,0,20,true);
 exercise(EN7528_GUARD,20,20,true);
 exercise(EN7528_GUARD,255,20,true);
 exercise(EN7523_GUARD,32,32,false);
 exercise(EN7523_GUARD,0,20,false);
 exercise(EN751221_GUARD,32,24,true);
 return 0;
}
'''

with tempfile.TemporaryDirectory() as tmp:
    directory = Path(tmp)
    def run(label, cb, phy_writer, selection):
        source = directory / (label + '.c')
        flags = ''.join('#define ' + name.upper() + '_GUARD ' + value + '\n'
                        for name, value in selection.items())
        source.write_text(shim + defines + flags + phy_writer + '\n' + cb + main)
        exe = directory / label
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(source), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)], capture_output=True).returncode

    assert run('actual', callback, writer, families) == 0
    mutations = [
        ('missing-override', callback, writer, dict(families, en7528='0')),
        ('other-board-24', callback, writer, dict(families, en7528='24')),
        ('mac-uses-announced', callback.replace('GPON_PLOu_GUARD_BIT, effective_guard_bits',
                                               'GPON_PLOu_GUARD_BIT, guard_bits'), writer, families),
        ('phy-drops-guard', callback, writer.replace('PREAMBLE_GUARD_MASK, guard_bits',
                                                    'PREAMBLE_GUARD_MASK, guard_bits & 0'), families),
    ]
    for label, cb, pw, selection in mutations:
        assert run(label, cb, pw, selection) != 0, 'Unsafe mutation survived: ' + label
print('Actual MAC/PHY guard propagation, family policies, unchanged overhead fields and four rejected mutations passed')
