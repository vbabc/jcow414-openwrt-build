"""Exercise the actual passive RX functions with MMIO/PHY fault injection."""
from pathlib import Path
import resource,subprocess,sys,tempfile
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
s=(Path(sys.argv[1])/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
def extract(name):
 a=s.index(name+'(');b=s.index('{',a);end=b+1;level=1
 while level:
  level+=(s[end]=='{')-(s[end]=='}');end+=1
 return s[a:end]
shim='''#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
typedef uint32_t u32;
#define GPON_INT_ENABLE 0x00c
#define GPON_INT_STATUS 0x008
#define GPON_MBI_MPI_STOP 0x160
#define MBI_RX_STOP (1U<<0)
#define MBI_TX_STOP (1U<<8)
#define MPI_RX_STOP (1U<<16)
#define MPI_TX_STOP (1U<<24)
#define MPI_TX_STOP_DONE (1U<<31)
#define WRITE_ONCE(a,b) ((a)=(b))
struct xpon_priv { bool control_diagnostic,rx_diagnostic,rx_diagnostic_started;void *phy;char *gpon_reg; };
static u32 regs[0x200/4];static int writes,checks,fail_at,reset_result,init_result;static bool ack;
static const u32 all=MBI_RX_STOP|MBI_TX_STOP|MPI_RX_STOP|MPI_TX_STOP,tx=MBI_TX_STOP|MPI_TX_STOP;
static void gpon_write(struct xpon_priv*p,u32 reg,u32 value) { (void)p; writes++;if(reg==GPON_INT_ENABLE)assert(value==0);if(reg==GPON_MBI_MPI_STOP)assert((value&tx)==tx);regs[reg/4]=value; }
static void gpon_set_bits(struct xpon_priv*p,u32 r,u32 bits) {gpon_write(p,r,regs[r/4]|bits);}
static void gpon_rmw(struct xpon_priv*p,u32 r,u32 mask,u32 value) {gpon_write(p,r,(regs[r/4]&~mask)|value);}
static int airoha_xpon_phy_tx_inhibited(void*p) {(void)p;checks++;return checks==fail_at?0:1;}
static int airoha_xpon_reset_mac(struct xpon_priv*p) {(void)p;return reset_result;}
static int gpon_dev_init(struct xpon_priv*p) {(void)p;return init_result;}
static void mdelay(int ms) {(void)ms;}
#define readl_poll_timeout_atomic(addr,val,condition,delay,timeout) ({ (void)(addr);(void)(delay);(void)(timeout);val=regs[GPON_MBI_MPI_STOP/4]|(ack?MPI_TX_STOP_DONE:0);(condition)?0:-ETIMEDOUT; })
'''
func='static void\n'+extract('gpon_rx_diagnostic_stop')+'\nstatic int\n'+extract('gpon_rx_diagnostic_start')
test='''
static struct xpon_priv fresh(void) { memset(regs,0,sizeof(regs));writes=checks=fail_at=reset_result=init_result=0;ack=true;return(struct xpon_priv){.control_diagnostic=true,.rx_diagnostic=true,.gpon_reg=(char*)regs}; }
int main(void) {
 struct xpon_priv p=fresh();p.control_diagnostic=false;assert(gpon_rx_diagnostic_start(&p)==-EOPNOTSUPP && writes==0);
 p=fresh();p.rx_diagnostic=false;assert(gpon_rx_diagnostic_start(&p)==-EOPNOTSUPP && writes==0);
 p=fresh();assert(gpon_rx_diagnostic_start(&p)==0 && p.rx_diagnostic_started && checks==3);assert((regs[GPON_MBI_MPI_STOP/4]&all)==tx && regs[GPON_INT_ENABLE/4]==0);
 gpon_rx_diagnostic_stop(&p);assert(!p.rx_diagnostic_started && (regs[GPON_MBI_MPI_STOP/4]&all)==all);
 for(int n=1;n<=3;n++){p=fresh();fail_at=n;assert(gpon_rx_diagnostic_start(&p)==-EIO && !p.rx_diagnostic_started);if(n==1)assert(writes==0);else assert((regs[GPON_MBI_MPI_STOP/4]&all)==all);}
 p=fresh();reset_result=-EBUSY;assert(gpon_rx_diagnostic_start(&p)==-EBUSY && (regs[GPON_MBI_MPI_STOP/4]&all)==all);
 p=fresh();init_result=-EFAULT;assert(gpon_rx_diagnostic_start(&p)==-EFAULT && (regs[GPON_MBI_MPI_STOP/4]&all)==all);
 p=fresh();ack=false;assert(gpon_rx_diagnostic_start(&p)==-ETIMEDOUT && !p.rx_diagnostic_started && (regs[GPON_MBI_MPI_STOP/4]&all)==all);
 return 0;
}
'''
unsafe=func.replace('\t\t MBI_TX_STOP | MPI_TX_STOP);','\t\t 0);',1);assert unsafe!=func
at=func.rindex('if (ret != 1) {');unsafe2=func[:at]+func[at:].replace('if (ret != 1) {','if (false) {',1)
with tempfile.TemporaryDirectory(prefix='jcow414-rx-guard-') as d:
 d=Path(d)
 for name,body,good in [('actual',func,True),('unsafe-tx-release',unsafe,False),('unsafe-final-inhibit',unsafe2,False)]:
  p=d/(name+'.c');exe=d/name;p.write_text(shim+body+test)
  subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
  result=subprocess.run([str(exe)],capture_output=True);assert(result.returncode==0)==good,name
print('Actual passive RX functions passed normal, admission, reset, init, ACK-timeout and inhibit-loss tests; two unsafe mutations rejected')
