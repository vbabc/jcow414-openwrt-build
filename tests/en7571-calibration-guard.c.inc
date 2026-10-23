/* Require factory calibration before initializing the optical transmitter. */
static bool en7571_factory_calibration_ready(struct airoha_lddla *lddla)
{
	static const u32 required[] = {
		EN7571_FL_IAV_IMOD, EN7571_FL_PAV_P1, EN7571_FL_T0CT1C,
	};
	u32 magic, profile, word;
	unsigned int i;

	if (!lddla->bob_valid ||
	    lddla->bob_len < EN7571_FL_LUT_END + sizeof(u32))
		return false;

	magic = lddla_flash_read(lddla, EN7571_FL_MAGIC);
	if (!AIROHA_LDDLA_BOB_MAGIC_VALID(magic, EN7571_BOB_VARIANT))
		return false;
	profile = AIROHA_LDDLA_BOB_MAGIC_PROFILE(magic);
	if (profile != AIROHA_LDDLA_BOB_PROFILE_GPON &&
	    profile != AIROHA_LDDLA_BOB_PROFILE_EPON &&
	    profile != AIROHA_LDDLA_BOB_PROFILE_XPON)
		return false;

	for (i = 0; i < 3; i++) {
		word = lddla_flash_read(lddla, required[i]);
		if (!word || word == EN7571_FLASH_ERASED)
			return false;
	}

	return true;
}
