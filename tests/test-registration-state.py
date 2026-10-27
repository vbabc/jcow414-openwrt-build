"""Compile the real root-only diagnostic reader against a write-free mock MMIO API."""
from pathlib import Path
import re,subprocess,sys,tempfile
k=Path(sys.argv[1]);repo=Path(__file__).resolve().parents[1]
c=(k/'drivers/net/ethernet/airoha/airoha_xpon.c').read_text()
h=(k/'drivers/net/ethernet/airoha/airoha_xpon.h').read_text()
start=c.index('static ssize_t registration_state_show(');at=c.index('{',start);end=at+1;depth=1
while depth:
 depth+=(c[end]=='{')-(c[end]=='}');end+=1
reader=c[start:end]
assert 'static DEVICE_ATTR(registration_state, 0400, registration_state_show, NULL);' in c
assert '&dev_attr_registration_state.attr,' in c
assert not re.search(r'gpon_write|gpon_rmw|set_bits|clear_bits|set_tx|set_activation|FIFO.*RDATA|phy_get|WRITE_ONCE',reader)
assert not re.search(r'%[0-9.*# +\-]*p|%s',reader)
registers=re.findall(r'^#define (GPON_\w+)\s+(0x[0-9A-Fa-f]+)\b',h,re.M)
shim=r'''
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <errno.h>
typedef uint32_t u32;
#define READ_ONCE(x) (x)
struct device { int unused; };
struct device_attribute { int unused; };
struct xpon_priv {
 bool manual_activation; unsigned char hw_sn[8];
 u32 diag_sn_requests,diag_sn_sent,diag_ranging,diag_ploam;
 u32 diag_phy_frames,diag_phy_bursts,diag_phy_samples,ploam_rx_messages,ploam_rx_drops,assign_onu_fastpath;
 int diag_phy_ret; bool gpon_t3_valid; unsigned char gpon_t3_o3,gpon_t3_o5; u32 gpon_t3_restores;
};
static struct xpon_priv *instance;
static u32 regs[0x400/4];
static unsigned int reads;
static void *dev_get_drvdata(struct device *d) { (void)d;return instance; }
static u32 get_unaligned_be32(const void *p) {
 const unsigned char *v=p;
 return ((u32)v[0]<<24)|((u32)v[1]<<16)|((u32)v[2]<<8)|v[3];
}
static u32 gpon_read(struct xpon_priv *p,unsigned int offset) {
 (void)p;assert(offset<sizeof(regs) && offset%4==0);reads++;return regs[offset/4];
}
static int sysfs_emit(char *buf,const char *fmt,...) {
 va_list ap;va_start(ap,fmt);int n=vsnprintf(buf,4096,fmt,ap);va_end(ap);return n;
}
'''
main=r'''
int main(void) {
 struct device d={0};struct device_attribute a={0};char output[4096];
 assert(registration_state_show(&d,&a,output)==-EOPNOTSUPP && reads==0);
 struct xpon_priv p={.hw_sn={'T','E','S','T',0x12,0x34,0x56,0x78}};instance=&p;
 assert(registration_state_show(&d,&a,output)==-EOPNOTSUPP && reads==0);
 p.manual_activation=true;p.diag_sn_requests=7;p.diag_sn_sent=3;
 p.diag_ranging=2;p.diag_ploam=11;p.diag_phy_frames=123;p.diag_phy_bursts=45;
 p.diag_phy_ret=-EIO;
 regs[GPON_VENDOR_ID/4]=get_unaligned_be32(p.hw_sn);
 regs[GPON_VS_SN/4]=get_unaligned_be32(p.hw_sn+4);
 assert(registration_state_show(&d,&a,output)>0);
 assert(strstr(output,"serial_match=1 "));
 assert(strstr(output,"sn_request_batches=7 sn_sent_batches=3 ranging_batches=2 ploam_batches=11"));
 assert(strstr(output,"phy_frames=123 phy_bursts=45 phy_counter_result=-5"));
 assert(!strstr(output,"TEST") && !strstr(output,"12345678"));
 regs[GPON_VS_SN/4]^=1;
 assert(registration_state_show(&d,&a,output)>0);
 assert(strstr(output,"serial_match=0 "));
 puts("Real registration reader: root-only, no control/write API, identity redacted, match/mismatch and telemetry checked");
 return 0;
}
'''
with tempfile.TemporaryDirectory() as work:
 p=Path(work);source=p/'reader.c';binary=p/'reader'
 source.write_text(shim+'\n'+''.join('#define '+n+' '+v+'\n' for n,v in registers)+reader+'\n'+main)
 subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(source),'-o',str(binary)],check=True)
 subprocess.run([str(binary)],check=True)
