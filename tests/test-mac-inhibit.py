"""Compile actual transport/TX functions; reject write-before-guard regressions."""
from pathlib import Path
import subprocess,sys,tempfile,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
k=Path(sys.argv[1]);c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text();b=(k/'drivers/net/ethernet/airoha/airoha_gpon_omci.c').read_text()
def extract(source,name):
 start=source.index(name+'(');at=source.index('{',start);level=1;end=at+1
 while level:
  level+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]
shim='''#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stddef.h>
typedef unsigned short u16;
#define dev_err(...) ((void)0)
struct xpon_priv { bool control_diagnostic; void *phy; void *frontend; void *dev; };
struct airoha_gpon_omci { struct xpon_priv *hw_priv; void *gdm_dev; };
struct omci_device { struct airoha_gpon_omci *p; };
struct sk_buff { int dummy; };
static int writes, starts, stops, hw_result;
static void *omci_device_priv(struct omci_device *o) { return o->p; }
static int airoha_eth_xpon_control_start(void *p) { (void)p; writes++; starts++; return 0; }
static void airoha_eth_xpon_control_stop(void *p) { (void)p; writes++; stops++; }
static int airoha_gpon_omci_hw_start(void *p) { (void)p; writes++; return hw_result; }
static int airoha_eth_xmit_xpon_oam(void *p, struct sk_buff *s, int channel,u16 gem) { (void)p;(void)s;(void)channel;(void)gem;writes++;return 0; }
static int airoha_xpon_phy_set_tx_enable(void *p,bool on) { (void)p;(void)on;writes++;return 0; }
static int optical_frontend_tx_enable(void *p,bool on) { (void)p;(void)on;writes++;return -EOPNOTSUPP; }
'''
functions=('bool\n'+extract(c,'airoha_gpon_omci_hw_is_diagnostic')+'\nstatic int\n'+extract(c,'airoha_xpon_tx_enable')+'\nstatic int\n'+extract(b,'airoha_gpon_omci_start_transport')+'\nstatic int\n'+extract(b,'airoha_gpon_omci_xmit'))
tests='''
int main(void) {
 struct xpon_priv p={.control_diagnostic=true,.frontend=(void*)1};
 struct airoha_gpon_omci backend={.hw_priv=&p};struct omci_device o={.p=&backend};struct sk_buff skb={0};
 assert(airoha_gpon_omci_start_transport(&o)==-EPERM && writes==0);
 assert(airoha_gpon_omci_xmit(&o,&skb,0)==-EPERM && writes==0);
 assert(airoha_xpon_tx_enable(&p,true)==-EPERM && writes==0);
 assert(airoha_xpon_tx_enable(&p,false)==0 && writes==2);
 writes=0;p.control_diagnostic=false;
 assert(airoha_gpon_omci_start_transport(&o)==0 && writes==2 && starts==1);
 assert(airoha_gpon_omci_xmit(&o,&skb,0)==0 && writes==3);
 assert(airoha_xpon_tx_enable(&p,true)==0 && writes==5);
 hw_result=-EIO;writes=0;
 assert(airoha_gpon_omci_start_transport(&o)==-EIO && writes==3 && stops==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='jcow414-mac-guard-') as d:
 d=Path(d)
 for name,body,ok in [('actual',functions,True),('unsafe-transport',functions.replace('if (airoha_gpon_omci_hw_is_diagnostic(omci->hw_priv))','if (false)',1),False),('unsafe-transmit',functions.replace('if (priv->control_diagnostic && enable)','if (false)',1),False)]:
  src=d/(name+'.c');exe=d/name;src.write_text(shim+body+tests)
  subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe)],capture_output=True)
  assert (result.returncode==0)==ok,name
print('Actual MAC transport/TX functions block all diagnostic writes; normal/error paths pass; two unsafe mutations rejected')
