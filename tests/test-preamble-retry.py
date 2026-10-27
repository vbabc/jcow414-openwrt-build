"""Exercise exact PLOAM handlers, changed MAC callback prefix and PHY code.

The unmodified callback tail (carrier/MIB/timers after the MAC write) is excluded;
static ordering assertions cover its integration into the full callback.
"""
from pathlib import Path
import re,subprocess,sys,tempfile,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
k=Path(sys.argv[1]);c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text();p=(k/'drivers/phy/airoha/phy-airoha-xpon.c').read_text();fsm=(k/'drivers/net/ethernet/airoha/airoha_ploam.c').read_text()
def fn(s,name):
 m=re.search(r'^(?:static )?(?:int|void)\s+'+name+r'\(',s,re.M);assert m,name
 at=s.index('{',m.start());end=at+1;depth=1
 while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[m.start():end]
full=fn(c,'gpon_cb_state_changed');prefix=full[:full.index('\tgpon_bip_set_active(')]+'}\n'
assert full.index('gpon_restore_t3_preamble(priv)')<full.index('gpon_write(priv, GPON_ACTIVATION_ST')
assert 'gpon_invalidate_t3_cache(priv)' in fn(c,'gpon_reset_activation_context')
assert 'set_t3_preamble' not in fn(fsm,'handle_upstream_overhead')
assert 'GPON_O3_SERIAL_NUMBER' in fn(fsm,'handle_extended_burst_length')
assert 'state_changed' not in fn(fsm,'ploam_reset') # TO1 reset must retain cache through silent O1.
sh=r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
typedef uint32_t u32;typedef uint16_t u16;typedef uint8_t u8;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define BIT(n) (1u<<(n))
#define GENMASK(h,l) ((~0u>>(31-(h)))&(~0u<<(l)))
#define FIELD_PREP(m,v) (((u32)(v)<<__builtin_ctz(m))&(m))
#define dev_dbg(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_warn(...) ((void)0)
#define XPON_GPON_EXT_PREAMBLE 0x408
#define XPON_GPON_EXT_O3_O4_MASK GENMASK(7,0)
#define XPON_GPON_EXT_O5_MASK GENMASK(15,8)
#define XPON_GPON_EXT_MODE BIT(16)
#define XPON_GPON_EXT_OPER_MASK GENMASK(18,17)
#define GPON_PLOu_PRMBL_TYPE3 0x9c
#define GPON_ACTIVATION_ST 0xbc
#define PLOAM_ONU_BCAST 255
#define PLOAM_ONU_UNASSIGNED 255
#define PLOAM_CONTENT_LEN 10
enum airoha_xpon_phy_gpon_oper_state { AIROHA_XPON_PHY_GPON_OPER_DISABLED=0,AIROHA_XPON_PHY_GPON_OPER_RANGING=2,AIROHA_XPON_PHY_GPON_OPER_OPERATION=3 };
enum gpon_state { GPON_O1_INITIAL=1,GPON_O2_STANDBY,GPON_O3_SERIAL_NUMBER,GPON_O4_RANGING,GPON_O5_OPERATION,GPON_O6_POPUP,GPON_O7_EMERGENCY_STOP };
struct phy { int unused; };struct airoha_xpon_phy { int unused; };
struct xpon_priv { struct phy *phy; bool gpon_t3_valid; u8 gpon_t3_o3,gpon_t3_o5; u32 gpon_t3_restores; };
static struct airoha_xpon_phy hw;static u32 phyreg,macreg,act;static bool blocked,phy_fail,tx_disabled;
static int airoha_xpon_phy_get_active_gpon(struct phy *phy,struct airoha_xpon_phy **out) { (void)phy;*out=&hw;return phy_fail?-EIO:0; }
static void airoha_xpon_phy_rmw(struct airoha_xpon_phy *p,u32 a,u32 mask,u32 v) { (void)p;assert(a==0x408);phyreg=(phyreg&~mask)|v; }
static bool airoha_xpon_activation_blocked(struct xpon_priv *p) { (void)p;return blocked; }
static int airoha_xpon_tx_enable(struct xpon_priv *p,bool enable) { (void)p;assert(!enable);tx_disabled=true;return 0; }
static void gpon_write(struct xpon_priv *p,u32 a,u32 v) {
 if(a==GPON_PLOu_PRMBL_TYPE3) { macreg=v;return; }
 assert(a==GPON_ACTIVATION_ST);
 if(v==GPON_O3_SERIAL_NUMBER && p->gpon_t3_valid) {
  assert((phyreg&0x1ffff)==(0x10000u|((u32)p->gpon_t3_o5<<8)|p->gpon_t3_o3));
  assert(macreg==(0x1000000u|((u32)p->gpon_t3_o5<<8)|p->gpon_t3_o3));
 }
 act=v;
}
struct ploam_ops {
 void (*state_changed)(void*,enum gpon_state);
 void (*set_overhead)(void*,u8,u8,u8,u8,const u8*,bool,u16);
 void (*set_t3_preamble)(void*,u8,u8);
};
struct ploam_priv { const struct ploam_ops *ops;void *hw_priv;enum gpon_state state;u8 onu_id;bool emergency_state,key_exchange_pending,dedup_prev_valid;u8 rei_seq,dedup_same_cnt;u32 eqd; };
static void overhead(void *p,u8 a,u8 b,u8 c,u8 d,const u8 *e,bool f,u16 g) { (void)p;(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g; }
'''
parts=[fn(p,'airoha_xpon_phy_set_gpon_extended_preamble'),fn(p,'airoha_xpon_phy_set_gpon_oper_state'),fn(c,'gpon_invalidate_t3_cache'),fn(c,'gpon_restore_t3_preamble'),fn(c,'gpon_cb_set_t3_preamble'),prefix]+[fn(fsm,n) for n in ['ploam_set_state','handle_upstream_overhead','handle_extended_burst_length','ploam_reset','ploam_start']]
main=r'''
int main(void) {
 struct phy phy={0};struct xpon_priv x={.phy=&phy};
 struct ploam_ops ops={.state_changed=gpon_cb_state_changed,.set_overhead=overhead,.set_t3_preamble=gpon_cb_set_t3_preamble};
 struct ploam_priv pp={.ops=&ops,.hw_priv=&x,.state=GPON_O1_INITIAL};u8 msg[10]={0};
 ploam_start(&pp);assert(act==2 && !x.gpon_t3_valid && phyreg==0);
 handle_upstream_overhead(&pp,255,msg);assert(act==3 && !x.gpon_t3_valid);assert(phyreg==0x40000);
 msg[0]=121;msg[1]=55;handle_extended_burst_length(&pp,254,msg);assert(!x.gpon_t3_valid);
 handle_extended_burst_length(&pp,255,msg);assert(x.gpon_t3_valid && phyreg==0x53779);
 for(int i=0;i<3;i++) {
  ploam_reset(&pp);ploam_start(&pp);assert(x.gpon_t3_valid && phyreg==0 && act==2);
  handle_upstream_overhead(&pp,255,msg);assert(act==3 && phyreg==0x53779);
 }
 assert(x.gpon_t3_restores==3);
 msg[0]=104;msg[1]=12;handle_extended_burst_length(&pp,255,msg);
 ploam_reset(&pp);ploam_start(&pp);handle_upstream_overhead(&pp,255,msg);assert(phyreg==0x50c68 && act==3);
 ploam_set_state(&pp,GPON_O1_INITIAL);assert(!x.gpon_t3_valid);ploam_start(&pp);handle_upstream_overhead(&pp,255,msg);assert(phyreg==0x40000 && !x.gpon_t3_valid);
 handle_extended_burst_length(&pp,255,msg);ploam_set_state(&pp,GPON_O7_EMERGENCY_STOP);assert(!x.gpon_t3_valid);
 ploam_set_state(&pp,GPON_O3_SERIAL_NUMBER);handle_extended_burst_length(&pp,255,msg);
 ploam_reset(&pp);ploam_start(&pp);phy_fail=true;tx_disabled=false;
 handle_upstream_overhead(&pp,255,msg);assert(act==2 && tx_disabled);phy_fail=false;
 ploam_reset(&pp);ploam_start(&pp);blocked=true;tx_disabled=false;
 handle_upstream_overhead(&pp,255,msg);assert(act==2 && tx_disabled);blocked=false;
 phy_fail=true;handle_extended_burst_length(&pp,255,msg);assert(!x.gpon_t3_valid && tx_disabled);phy_fail=false;
 gpon_invalidate_t3_cache(&x);assert(!x.gpon_t3_valid && !x.gpon_t3_o3 && !x.gpon_t3_o5);
 return 0;
}
'''
source=sh+'\n'.join(parts)+main
with tempfile.TemporaryDirectory() as tmp:
 t=Path(tmp)
 def run(text,name):
  path=t/(name+'.c');exe=t/name;path.write_text(text)
  subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter',str(path),'-o',str(exe)],check=True)
  return subprocess.run([str(exe)],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
 assert run(source,'real')==0
 mutations={
 'omit_restore':source.replace('ret = gpon_restore_t3_preamble(priv);','ret = 0;'),
 'reuse_cache_after_o1':source.replace('if (state == GPON_O1_INITIAL || state == GPON_O7_EMERGENCY_STOP)','if (false)'),
 'ignore_restore_failure':source.replace('ret = gpon_restore_t3_preamble(priv);','ret = gpon_restore_t3_preamble(priv); ret = 0;')}
 for name,text in mutations.items():assert text!=source and run(text,name)!=0,name
print('Actual PLOAM/PHY + changed MAC prefix pass: retry ordering, negotiated updates, O1/O7 invalidation, error/admission shutdown; three unsafe mutations rejected')
