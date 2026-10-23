# JCOW414 OpenWrt diagnostic builds

Pinned OpenWrt builds for the JioFiber JCOW414 / EcoNet EN7528, with experimental EN7571 optical diagnostics. This is an engineering build, **not working GPON firmware**.

The source is [Sirherobrine23/openwrt](https://github.com/Sirherobrine23/openwrt) at `880b7e32666d8c87aaf30cd5e99d965788c163ac`. Feed revisions are recorded in `feeds.lock.json`. Upstream retains its original licenses; the kernel changes and build scripts here use GPL-2.0-only.

## Build

Open **Actions → Build JCOW414 diagnostics → Run workflow**. Choose:

- **baseline**: expose the existing factory calibration cell; I2C, optical PHY/MAC and GDM2 remain disabled.
- **probe-only**: enable the I2C controller and EN7571 identity/calibration probe. A paired driver patch returns before optical initialization, frontend registration or starting the control worker. Optical PHY/MAC and GDM2 remain disabled.

The workflow uses an Ubuntu 24.04 standard hosted runner, up to four build jobs, pinned Actions, bounded download/ccache storage, and three-day artifact retention. It uploads firmware, source/configuration records and logs. It performs no deployment. A compilation success does not establish bootability, optical correctness or ISP interoperability.

Only public source pins, build scripts, patches and synthetic tests belong in this repository. Device dumps, backups, administrator/Wi-Fi/ISP credentials, ONU identities and per-unit optical calibration blobs are excluded. Calibration is read from each device's own NVMEM field at runtime; it is not embedded into the image.

## Changes

- Add the JCOW414 calibration cell at reservearea-relative offset `0x140477`, length `0xe1` (225 bytes).
- Remove an unresolved generic calibration-package reference from the inherited Jio device recipe.
- Require a loaded, sufficiently sized EN7571 calibration record with the correct family/profile marker and nonblank target/timing fields before frontend initialization.
- For probe-only builds, add `airoha,diagnostic-only` and the matching early-return driver path. **Never use this board property with an unmodified driver**, which would ignore it and initialize the frontend normally.
- Include LuCI and OMCI UI/agent packages for subsequent integration work. Their presence does not establish a usable PON interface.

The synthetic host test accepts a valid-shaped 225-byte GPON record and rejects seven invalid cases. It uses invented test values, not a device calibration record.

## Device validation

Review the image model, boot format, kernel/partition sizes and recovery path before any installation. First diagnostic boot must be tested with ISP fibre disconnected. Verify Ethernet management, persistent configuration, factory NVMEM reads and silicon detection before evaluating optical initialization. Probe-only mode does not itself assert a physical TX-disable pin.

GPON registration, OMCI service mapping, PPPoE/VLAN configuration and ISP interoperability remain separate hardware tests. EPON and XGS-PON support are not claimed.
