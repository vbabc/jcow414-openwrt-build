"""Compile actual frontend rearm and byte RMW; inject bus failures and mutations."""
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
kernel = Path(sys.argv[1]) / 'drivers/net/optical/airoha'

def function(source, signature):
    start = source.index(signature)
    at = source.index('{', start)
    end, depth = at + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

rearm = function((kernel / 'en7571_main.c').read_text(), 'static int en7571_op_tx_rearm(')
update = function((kernel / 'airoha_lddla_core.c').read_text(), 'int lddla_update8(')
header = (kernel / 'en7571_regs.h').read_text()
defines = ''
for name in ['EN7571_T1DELAY', 'EN7571_T1_DELAY_MASK', 'EN7571_T1_DELAY_NORMAL',
             'EN7571_DUMMY', 'EN7571_BURST_CTRL_MASK', 'EN7571_BURST_CTRL_OFF',
             'EN7571_PWR_CTRL_0', 'EN7571_DCL_RST_B_MASK', 'EN7571_DCL_RST_B',
             'EN7571_SAFE_PROTECT', 'EN7571_SAFE_CIRCUIT_MASK', 'EN7571_SAFE_CIRCUIT_RESET']:
    match = re.search(r'^#define\s+' + name + r'\s+([^\n]+)', header, re.M)
    assert match, name
    defines += '#define ' + name + ' ' + match[1] + '\n'

shim = r'''
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16;
struct airoha_lddla { void *dev; };
struct en7571_priv { struct airoha_lddla lddla; int ver; };
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define dev_warn(...) do {} while (0)
static u8 regs[1024], expected[1024];
static unsigned io, fail_at, rogue, writes, addr_log[8];
static int lddla_rd8(struct airoha_lddla *l,u16 a,u8 *v) {
 (void)l;assert(a<sizeof(regs));io++;if(io==fail_at)return -EIO;*v=regs[a];return 0;
}
static int lddla_wr8(struct airoha_lddla *l,u16 a,u8 v) {
 (void)l;assert(a<sizeof(regs));io++;if(io==fail_at)return -EIO;
 assert(writes<8);addr_log[writes++]=a;regs[a]=v;return 0;
}
static void en7571_rogue_clear(struct en7571_priv *p) {
 (void)p;assert(regs[EN7571_PWR_CTRL_0+1]&EN7571_DCL_RST_B);rogue++;
}
'''
main = r'''
static void reset(u8 delay,u8 dummy) {
 memset(regs,0x52,sizeof(regs));regs[EN7571_T1DELAY]=delay;
 regs[EN7571_T1DELAY+1]=0x4a;regs[EN7571_T1DELAY+2]=0x4b;
 regs[EN7571_T1DELAY+3]=0xb6;
 regs[EN7571_DUMMY]=3;regs[EN7571_DUMMY+1]=dummy;
 memcpy(expected,regs,sizeof(regs));io=fail_at=rogue=writes=0;
}
static void exercise(int rev,u8 delay,u8 dummy) {
 struct en7571_priv p={.ver=rev};reset(delay,dummy);
 if(rev==2) {
  expected[EN7571_T1DELAY]=delay&0xf0;
  expected[EN7571_DUMMY+1]=dummy|4;
 }
 expected[EN7571_PWR_CTRL_0+1]|=1;
 expected[EN7571_SAFE_PROTECT+1]|=0x40;
 assert(en7571_op_tx_rearm(&p.lddla)==0);
 assert(memcmp(expected,regs,sizeof(regs))==0 && rogue==1);
 assert(io==(rev==2?8u:4u) && writes==(rev==2?4u:2u));
 if(rev==2)assert(addr_log[0]==EN7571_T1DELAY && addr_log[1]==EN7571_DUMMY+1);
 assert(addr_log[writes-2]==EN7571_PWR_CTRL_0+1);
 assert(addr_log[writes-1]==EN7571_SAFE_PROTECT+1);
 /* Repeating rearm must not change any further register bit. */
 io=rogue=writes=0;
 assert(en7571_op_tx_rearm(&p.lddla)==0);
 assert(memcmp(expected,regs,sizeof(regs))==0 && rogue==1);
}
int main(void) {
 for(unsigned i=0;i<256;i++)for(unsigned j=0;j<256;j++)exercise(2,(u8)i,(u8)j);
 exercise(1,0xaa,0x51);exercise(0,0x77,0xb1);exercise(3,0xfe,0xff);
 for(unsigned n=1;n<=8;n++) {
  struct en7571_priv p={.ver=2};reset(0xaa,0xb1);fail_at=n;
  assert(en7571_op_tx_rearm(&p.lddla)==-EIO && io==n);
  assert(rogue==(n>=7?1u:0u));
  if(n<=2)assert(memcmp(expected,regs,sizeof(regs))==0 && writes==0);
  assert(regs[EN7571_T1DELAY+1]==0x4a && regs[EN7571_T1DELAY+2]==0x4b);
  assert(regs[EN7571_T1DELAY+3]==0xb6);
  if(n<=4)assert(regs[EN7571_PWR_CTRL_0+1]==expected[EN7571_PWR_CTRL_0+1]);
  assert(regs[EN7571_DUMMY]==3 && regs[EN7571_DUMMY+2]==0x52 && regs[EN7571_DUMMY+3]==0x52);
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    directory = Path(tmp)
    def run(label, body):
        source = directory / (label + '.c')
        source.write_text(defines + shim + update + '\n' + body + main)
        exe = directory / label
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(source), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)], capture_output=True).returncode

    assert run('actual', rearm) == 0
    mutations = [
        ('wrong-revision', rearm.replace('priv->ver == 2', 'priv->ver == 1')),
        ('wrong-byte', rearm.replace('lddla, EN7571_T1DELAY,', 'lddla, EN7571_T1DELAY + 1,')),
        ('clobber-high-nibble', rearm.replace('EN7571_T1_DELAY_MASK,', '0x0f,')),
        ('missing-clear', rearm.replace('EN7571_T1_DELAY_MASK,', '0xff,')),
        ('ignore-error', rearm.replace('"EN7571 TX rearm delay failed: %d\\n", ret);\n\t\t\treturn ret;',
                                      '"EN7571 TX rearm delay failed: %d\\n", ret);\n\t\t\tret = 0;')),
        ('wrong-burst-byte', rearm.replace('lddla, EN7571_DUMMY + 1,','lddla, EN7571_DUMMY,')),
        ('burst-clobbers-reset', rearm.replace('EN7571_BURST_CTRL_MASK,','0,')),
        ('burst-missing-bit', rearm.replace('EN7571_BURST_CTRL_OFF);','0);')),
        ('burst-ignore-error', rearm.replace('"EN7571 TX rearm burst failed: %d\\n", ret);\n\t\t\treturn ret;',
                                             '"EN7571 TX rearm burst failed: %d\\n", ret);\n\t\t\tret = 0;')),
    ]
    for label, body in mutations:
        assert body != rearm, label
        assert run(label, body) != 0, 'Unsafe mutation survived: ' + label
print('Actual rev2 rearm/RMW: 65536 delay/DUMMY pairs, idempotence, other revisions, eight I/O failures and nine rejected mutations passed')
