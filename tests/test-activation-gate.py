"""Compile actual activation/PHY gate functions and reject unsafe mutations."""
from pathlib import Path
import resource, subprocess, sys, tempfile
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
k=Path(sys.argv[1])
mac=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
phy=(k/'drivers/phy/airoha/phy-airoha-xpon.c').read_text()
backend=(k/'drivers/net/ethernet/airoha/airoha_gpon_omci.c').read_text()

def function(source,name,kind):
 start=source.index(name+'(');at=source.index('{',start);level=1;end=at+1
 while level:
  level+=(source[end]=='{')-(source[end]=='}');end+=1
 return kind+'\n'+source[start:end]+'\n'

phy_functions=''.join(function(phy,n,t) for n,t in [
 ('airoha_xpon_phy_set_tx_gpio','static void'),
 ('airoha_xpon_phy_set_tx_enable','int'),
 ('airoha_xpon_phy_set_activation_arm','int')])
phy_shim=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define AIROHA_XPON_PHY_SUBMODE_GPON 0
struct mutex { bool held; };
struct airoha_xpon_phy { bool tx_inhibited_diagnostic,manual_activation,activation_armed; int submode; void *tx_disable_gpio; struct mutex tx_gate_lock; };
struct phy { struct airoha_xpon_phy *priv; };
static int level=1,writes;
static void mutex_lock(struct mutex *m) { assert(!m->held);m->held=true; }
static void mutex_unlock(struct mutex *m) { assert(m->held);m->held=false; }
static void *phy_get_drvdata(struct phy *p) { return p->priv; }
static int gpiod_get_value_cansleep(void *g) { (void)g;return level; }
static void gpiod_set_value_cansleep(void *g,int value) { (void)g;level=value;writes++; }
'''
phy_tests=r'''
int main(void) {
 struct airoha_xpon_phy p={.manual_activation=true,.tx_disable_gpio=(void*)1};struct phy f={.priv=&p};
 assert(airoha_xpon_phy_set_tx_enable(&f,true)==-EPERM && writes==0 && level==1);
 airoha_xpon_phy_set_tx_gpio(&p,true);assert(level==1);
 writes=0;assert(airoha_xpon_phy_set_activation_arm(&f,true)==0 && p.activation_armed && writes==0 && level==1);
 assert(airoha_xpon_phy_set_tx_enable(&f,true)==0 && level==0);
 assert(airoha_xpon_phy_set_activation_arm(&f,false)==0 && !p.activation_armed && level==1);
 assert(airoha_xpon_phy_set_tx_enable(&f,true)==-EPERM && level==1);
 level=0;assert(airoha_xpon_phy_set_activation_arm(&f,true)==-EIO && !p.activation_armed);
 level=-EIO;assert(airoha_xpon_phy_set_activation_arm(&f,true)==-EIO && !p.activation_armed);
 level=1;p.submode=1;assert(airoha_xpon_phy_set_activation_arm(&f,true)==-EIO);
 p.submode=0;p.tx_inhibited_diagnostic=true;assert(airoha_xpon_phy_set_activation_arm(&f,true)==-EOPNOTSUPP);
 assert(airoha_xpon_phy_set_tx_enable(&f,true)==-EPERM);
 p.tx_inhibited_diagnostic=false;p.manual_activation=false;
 assert(airoha_xpon_phy_set_activation_arm(&f,true)==-EOPNOTSUPP);
 assert(airoha_xpon_phy_set_tx_enable(&f,true)==0 && level==0);
 assert(airoha_xpon_phy_set_activation_arm(NULL,true)==-EINVAL);
 assert(!p.tx_gate_lock.held);
 return 0;
}
'''
mac_functions=''.join(function(mac,n,t) for n,t in [
 ('airoha_xpon_activation_blocked','static bool'),
 ('airoha_gpon_omci_hw_is_diagnostic','bool'),
 ('airoha_xpon_manual_stop','static int'),
 ('airoha_xpon_activation_expiry','static void'),
 ('airoha_xpon_manual_start','static int'),
 ('activation_store','static ssize_t')])
mac_functions+=function(backend,'airoha_gpon_omci_start_transport','static int')
identity_at=mac.index('\tif (priv->manual_activation && key == OMCI_CONFIG_SERIAL_NUMBER)')
identity_end=mac.index('\tif (airoha_xpon_activation_blocked(priv))',identity_at)
mac_functions+='static void apply_identity(struct xpon_priv *priv, int key, const struct omci_identity *identity)\n{\n'+mac[identity_at:identity_end]+'}\n'

mac_shim=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
#include <sys/types.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define AIROHA_XPON_MODE_GPON 0
#define JCOW414_ACTIVATION_SECONDS 180
#define HZ 100
#define CAP_NET_ADMIN 12
#define OMCI_CONFIG_SERIAL_NUMBER 1
#define OMCI_IDENTITY_F_SERIAL_NUMBER 1
#define OMCI_CONFIG_SOURCE_NETLINK 5
#define OMCI_CONFIG_SOURCE_SYSFS 6
struct omci_identity { int valid,serial_source; };
#define GPON_INT_ENABLE 1
#define GPON_MBI_MPI_STOP 2
#define MBI_RX_STOP 1
#define MBI_TX_STOP 2
#define MPI_RX_STOP 4
#define MPI_TX_STOP 8
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
struct work_struct { int x; };
struct delayed_work { struct work_struct work; };
struct mutex { bool held; };
struct xpon_priv;
struct airoha_gpon_omci { struct xpon_priv *hw_priv; void *gdm_dev; };
struct xpon_priv { bool manual_activation,control_diagnostic,activation_armed,activation_identity_configured,started,mac_enabled,phy_powered; int mode; void *phy,*dev; struct airoha_gpon_omci omci;struct mutex activation_lock; struct delayed_work activation_expiry_work; };
struct device { struct xpon_priv *p; };
struct device_attribute { int x; };
struct omci_device { struct airoha_gpon_omci *p; };
static struct xpon_priv *current_priv;
#define to_delayed_work(x) ((void)(x), &current_priv->activation_expiry_work)
#define container_of(x,type,member) ((void)(x), current_priv)
static int inhibit=1,phy_result,start_result,leases,duration,physical_stops,stops,masks,requests,fe_off,hw_writes,eth_starts,eth_stops,cancels;
static bool permission=true,phy_armed;
static void *system_wq;
static void mutex_lock(struct mutex *m) { assert(!m->held);m->held=true; }
static void mutex_unlock(struct mutex *m) { assert(m->held);m->held=false; }
static int airoha_xpon_phy_set_activation_arm(void *p,bool arm) { (void)p;if(phy_result)return phy_result;phy_armed=arm;if(!arm){physical_stops++;inhibit=1;}return 0; }
static int airoha_xpon_phy_tx_inhibited(void *p) { (void)p;return inhibit; }
static int airoha_gpon_omci_start(struct airoha_gpon_omci *o) { assert(o->hw_priv->activation_armed && phy_armed);if(start_result)return start_result;o->hw_priv->started=true;o->hw_priv->mac_enabled=true;o->hw_priv->phy_powered=true;return 0; }
static void airoha_gpon_omci_stop(struct airoha_gpon_omci *o) { assert(!o->hw_priv->activation_armed && !phy_armed && inhibit==1);stops++;o->hw_priv->started=false; }
static void gpon_disable(struct xpon_priv *p) { assert(!phy_armed);p->mac_enabled=false;p->phy_powered=false; }
static void gpon_write(struct xpon_priv *p,int reg,int value) { (void)p;assert(reg==GPON_INT_ENABLE && value==0);masks++; }
static void gpon_set_bits(struct xpon_priv *p,int reg,int value) { (void)p;assert(reg==GPON_MBI_MPI_STOP && value==15);requests++; }
static int gpon_set_fe_datapath(struct xpon_priv *p,bool on) { (void)p;assert(!on);fe_off++;return 0; }
static int mod_delayed_work(void *q,struct delayed_work *w,int delay) { (void)q;(void)w;leases++;duration=delay;return 0; }
static void cancel_delayed_work_sync(struct delayed_work *w) { (void)w;cancels++; }
static bool capable(int cap) { assert(cap==CAP_NET_ADMIN);return permission; }
static void *dev_get_drvdata(struct device *d) { return d->p; }
static int kstrtobool(const char *s,bool *b) { if(!strcmp(s,"1")){*b=true;return 0;}if(!strcmp(s,"0")){*b=false;return 0;}return -EINVAL; }
static void *omci_device_priv(struct omci_device *o) { return o->p; }
static int airoha_eth_xpon_control_start(void *p) { (void)p;eth_starts++;return 0; }
static void airoha_eth_xpon_control_stop(void *p) { (void)p;eth_stops++; }
static int airoha_gpon_omci_hw_start(void *p) { (void)p;hw_writes++;return start_result; }
'''
mac_tests=r'''
int main(void) {
 struct xpon_priv p={.manual_activation=true};struct device dev={.p=&p};struct device_attribute attr={0};
 p.omci.hw_priv=&p;current_priv=&p;struct omci_device o={.p=&p.omci};
 assert(airoha_xpon_activation_blocked(&p));
 assert(airoha_gpon_omci_start_transport(&o)==-EPERM && !eth_starts && !hw_writes);
 assert(airoha_xpon_manual_start(&p)==-EINVAL && !leases && !phy_armed);
 struct omci_identity id={.valid=1,.serial_source=4};
 apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,&id);assert(!p.activation_identity_configured);
 id.serial_source=1;apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,&id);assert(!p.activation_identity_configured);
 id.serial_source=5;apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,&id);assert(p.activation_identity_configured);
 id.valid=0;apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,&id);assert(!p.activation_identity_configured);
 id.valid=1;id.serial_source=6;apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,&id);assert(p.activation_identity_configured);
 apply_identity(&p,OMCI_CONFIG_SERIAL_NUMBER,NULL);assert(!p.activation_identity_configured);
 p.activation_identity_configured=true;inhibit=0;
 assert(airoha_xpon_manual_start(&p)==-EIO && !phy_armed);
 inhibit=-EIO;assert(airoha_xpon_manual_start(&p)==-EIO && !phy_armed);
 inhibit=1;phy_result=-EIO;assert(airoha_xpon_manual_start(&p)==-EIO && !p.activation_armed);
 phy_result=0;assert(airoha_xpon_manual_start(&p)==0 && p.activation_armed && phy_armed && leases==1 && duration==180*HZ);
 assert(!airoha_xpon_activation_blocked(&p));
 assert(airoha_gpon_omci_start_transport(&o)==0 && eth_starts==1 && hw_writes==1);
 assert(airoha_xpon_manual_start(&p)==-EALREADY && leases==1);
 airoha_xpon_activation_expiry(&p.activation_expiry_work.work);
 assert(!p.activation_armed && !phy_armed && !p.started && !p.mac_enabled && !p.phy_powered && physical_stops==1 && stops==1 && masks==1 && requests==1 && fe_off==1);
 assert(airoha_xpon_activation_blocked(&p));
 start_result=-EIO;assert(airoha_xpon_manual_start(&p)==-EIO && !p.activation_armed && !phy_armed && leases==1 && physical_stops==2);
 permission=false;assert(activation_store(&dev,&attr,"1",1)==-EPERM && !phy_armed);
 permission=true;assert(activation_store(&dev,&attr,"invalid",7)==-EINVAL && !phy_armed);
 start_result=0;assert(activation_store(&dev,&attr,"1",1)==1 && phy_armed);
 assert(activation_store(&dev,&attr,"0",1)==1 && !phy_armed && cancels==1);
 p.control_diagnostic=true;assert(airoha_xpon_manual_start(&p)==-EOPNOTSUPP);
 p.control_diagnostic=false;p.mode=1;assert(airoha_xpon_manual_start(&p)==-EOPNOTSUPP);
 p.mode=0;p.manual_activation=false;assert(airoha_xpon_manual_start(&p)==-EOPNOTSUPP);
 assert(!p.activation_lock.held);
 return 0;
}
'''

cases=[('phy-actual',phy_shim+phy_functions+phy_tests,True),
 ('mac-actual',mac_shim+mac_functions+mac_tests,True)]
for name,old,new in [
 ('phy-bypass-clamp','if (priv->tx_inhibited_diagnostic ||','if (false ||'),
 ('phy-arm-releases','WRITE_ONCE(priv->activation_armed, true);','{ WRITE_ONCE(priv->activation_armed, true); gpiod_set_value_cansleep(priv->tx_disable_gpio, 0); }'),
 ('phy-disarm-no-inhibit','gpiod_set_value_cansleep(priv->tx_disable_gpio, 1);','gpiod_set_value_cansleep(priv->tx_disable_gpio, 0);')]:
 body=phy_functions.replace(old,new,1)
 if name=='phy-bypass-clamp':
  body=body.replace('(priv->manual_activation && !READ_ONCE(priv->activation_armed)))','(false && !READ_ONCE(priv->activation_armed)))',1)
 assert body!=phy_functions;cases.append((name,phy_shim+body+phy_tests,False))
for name,old,new in [
 ('mac-no-identity','if (!READ_ONCE(priv->activation_identity_configured))','if (false)'),
 ('mac-driver-identity','identity->serial_source == OMCI_CONFIG_SOURCE_NETLINK','identity->serial_source == 4'),
 ('mac-no-timer','mod_delayed_work(system_wq, &priv->activation_expiry_work,','mod_delayed_work(system_wq, &priv->activation_expiry_work,'),
 ('mac-no-physical-stop','ret = airoha_xpon_phy_set_activation_arm(priv->phy, false);','ret = 0;'),
 ('mac-bypass-transport','if (airoha_gpon_omci_hw_is_diagnostic(omci->hw_priv))','if (false)')]:
 body=mac_functions.replace(old,new,1)
 if name=='mac-no-timer':body=body.replace('JCOW414_ACTIVATION_SECONDS * HZ','0',1)
 assert body!=mac_functions;cases.append((name,mac_shim+body+mac_tests,False))
with tempfile.TemporaryDirectory(prefix='jcow414-activation-') as d:
 d=Path(d)
 for name,source,expected in cases:
  c=d/(name+'.c');exe=d/name;c.write_text(source)
  subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(c),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe)],capture_output=True)
  assert (result.returncode==0)==expected,(name,result.stderr.decode())
print('Actual PHY/manual lifecycle/transport/store functions pass; eight unsafe mutations rejected')
