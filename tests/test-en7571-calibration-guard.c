/* Host test of the exact guard body used by the kernel patch; no hardware IO. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
struct airoha_lddla { bool bob_valid; size_t bob_len; unsigned char bob[512]; };
#define EN7571_FL_IAV_IMOD 0x000
#define EN7571_FL_PAV_P1 0x004
#define EN7571_FL_T0CT1C 0x00c
#define EN7571_FL_MAGIC 0x094
#define EN7571_FL_LUT_END 0x0dc
#define EN7571_BOB_VARIANT 1
#define EN7571_FLASH_ERASED 0xffffffffu
#define AIROHA_LDDLA_BOB_PROFILE_GPON 0x07
#define AIROHA_LDDLA_BOB_PROFILE_EPON 0xe7
#define AIROHA_LDDLA_BOB_PROFILE_XPON 0xa7
#define AIROHA_LDDLA_BOB_MAGIC_VALID(magic, variant) (((magic) & 0x00ffffffu) == (0x00050700u | (variant)))
#define AIROHA_LDDLA_BOB_MAGIC_PROFILE(magic) (((magic) >> 24) & 0xff)
static u32 lddla_flash_read(struct airoha_lddla *lddla, u32 offset)
{
	if (offset + 4 > lddla->bob_len) return EN7571_FLASH_ERASED;
	return (u32)lddla->bob[offset] | ((u32)lddla->bob[offset+1] << 8) |
	       ((u32)lddla->bob[offset+2] << 16) | ((u32)lddla->bob[offset+3] << 24);
}
#include "en7571-calibration-guard.c.inc"
static void put(struct airoha_lddla *lddla, u32 offset, u32 word)
{
	unsigned int i;
	for (i=0; i<4; i++) lddla->bob[offset+i]=(unsigned char)(word >> (i*8));
}
int main(void)
{
	struct airoha_lddla good, test;
	memset(&good, 0, sizeof(good));
	good.bob_valid=true; good.bob_len=225;
	put(&good, EN7571_FL_MAGIC, 0x07050701u);
	put(&good, EN7571_FL_IAV_IMOD, 0x00100010u);
	put(&good, EN7571_FL_PAV_P1, 0x00100010u);
	put(&good, EN7571_FL_T0CT1C, 0x101000aau);
	assert(en7571_factory_calibration_ready(&good));
	test=good; test.bob_valid=false; assert(!en7571_factory_calibration_ready(&test));
	test=good; test.bob_len=161; assert(!en7571_factory_calibration_ready(&test));
	test=good; put(&test, EN7571_FL_MAGIC, 0x07050700u); assert(!en7571_factory_calibration_ready(&test));
	test=good; put(&test, EN7571_FL_MAGIC, 0x12050701u); assert(!en7571_factory_calibration_ready(&test));
	test=good; put(&test, EN7571_FL_IAV_IMOD, 0xffffffffu); assert(!en7571_factory_calibration_ready(&test));
	test=good; put(&test, EN7571_FL_PAV_P1, 0); assert(!en7571_factory_calibration_ready(&test));
	test=good; put(&test, EN7571_FL_T0CT1C, 0xffffffffu); assert(!en7571_factory_calibration_ready(&test));
	puts("EN7571 calibration guard: valid 225-byte GPON record accepted; seven invalid cases rejected");
	return 0;
}
