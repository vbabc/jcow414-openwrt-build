"""Compile the real MAC RX-delay helper and use the actual EN7528 flag."""
from pathlib import Path
import re,resource,subprocess,sys,tempfile
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
k=Path(sys.argv[1]);c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text();h=(k/'drivers/net/ethernet/airoha/airoha_xpon.h').read_text()
at=c.index('static void gpon_adjust_mac_rx_delay(');start=c.index('{',at);end=start+1;depth=1
while depth:depth+=(c[end]=='{')-(c[end]=='}');end+=1
body=c[at:end]
at=c.index('static const struct airoha_xpon_match_data en7528_xpon_data = {');block=c[at:c.index('\n};',at)]
enabled=bool(re.search(r'\.gpon_adjust_rx_delay\s*=\s*true',block))
assert '.gpon_fine_delay = 0x1c' in block and '.gpon_rsp_time_activation = GPON_RSP_TIME_ACT_EN7528' in block
assert 'gpon_guard_bits_override' not in block # Keep guard policy unchanged in this experiment.
names=['GPON_DBG_PROBE_CTRL','GPON_DBG_PROBE_HIGH32','GPON_RSP_TIME','GPON_DBG_DLY']
defines=''
for name in names:
 m=re.search(r'^#define\s+'+name+r'\s+(0x[0-9a-fA-F]+)',h,re.M);assert m,name;defines+=f'#define {name} {m[1]}\n'
shim=r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
typedef uint32_t u32;
#define BIT(n) (1u<<(n))
#define GENMASK(h,l) ((~0u>>(31-(h)))&(~0u<<(l)))
#define FIELD_GET(m,v) (((v)&(m))>>__builtin_ctz(m))
#define FIELD_PREP(m,v) (((u32)(v)<<__builtin_ctz(m))&(m))
#define FIELD_MAX(m) ((m)>>__builtin_ctz(m))
#define DBG_PROBE_RX_DELAY_SEL 0xf
#define DBG_PROBE_RX_DELAY_MASK GENMASK(23,12)
#define DBG_DLY_PHY_RX_DLY_SEL BIT(31)
#define DBG_DLY_FIX_PHY_RX_DLY_MASK GENMASK(27,16)
struct match { bool gpon_adjust_rx_delay; u32 gpon_rsp_time_activation; };
struct xpon_priv { const struct match *match_data; };
static u32 regs[1024],writes,reads;
static u32 gpon_read(struct xpon_priv *p,u32 reg) {(void)p;reads++;return regs[reg/4];}
static void gpon_write(struct xpon_priv *p,u32 reg,u32 v) {(void)p;writes++;regs[reg/4]=v;}
static void gpon_rmw(struct xpon_priv *p,u32 reg,u32 mask,u32 v) {(void)p;writes++;regs[reg/4]=(regs[reg/4]&~mask)|v;}
'''
main=r'''
static void exercise(struct xpon_priv *p,u32 rx,u32 response,u32 expect) {
 const u32 initial=0x10801c55,mask=0x8fff0000;
 regs[GPON_DBG_PROBE_HIGH32/4]=rx<<12;regs[GPON_RSP_TIME/4]=response;
 regs[GPON_DBG_DLY/4]=initial;regs[GPON_DBG_PROBE_CTRL/4]=0;writes=reads=0;
 gpon_adjust_mac_rx_delay(p);
 assert(writes==2 && reads==2 && regs[GPON_DBG_PROBE_CTRL/4]==0xf);
 assert((regs[GPON_DBG_DLY/4]&mask)==(0x80000000u|((expect&0xfff)<<16)));
 assert((regs[GPON_DBG_DLY/4]&~mask)==(initial&~mask));
}
int main(void) {
 struct match disabled={false,0x577},active={EN7528_ADJUST,0x577};
 struct xpon_priv old={&disabled},en7528={&active};
 regs[GPON_DBG_DLY/4]=0x80801c00;writes=reads=0;gpon_adjust_mac_rx_delay(&old);
 assert(!writes && !reads && regs[GPON_DBG_DLY/4]==0x80801c00);
 exercise(&en7528,300,0x577,150);
 exercise(&en7528,301,0x579,158);
 exercise(&en7528,300,0x570,150);
 exercise(&en7528,4095,0x577,2047);
 exercise(&en7528,4095,0x777,(2047+4*0x200)&0xfff);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp)
 def build_run(label,source,flag):
  p=d/(label+'.c');p.write_text(defines+f'#define EN7528_ADJUST {int(flag)}\n'+shim+source+main)
  exe=d/label;subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
  return subprocess.run([str(exe)],capture_output=True).returncode
 assert build_run('actual',body,enabled)==0,'Actual EN7528 RX-delay behavior failed'
 mutations=[('disabled-family-flag',body,False),('missing-halving',body.replace('rx_delay / 2','rx_delay'),True),('missing-response-compensation',body.replace('fixed += 4 * (rsp_time - rsp_base);','fixed += 0;'),True)]
 for name,source,flag in mutations:assert build_run(name,source,flag)!=0,'Unsafe mutation survived: '+name
print('Actual EN7528 admission, measured half-delay, response compensation, mask preservation and three negative mutations passed')
