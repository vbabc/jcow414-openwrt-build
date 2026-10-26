# JCOW414 OpenWrt diagnostic builds

Pinned OpenWrt builds for the JioFiber JCOW414 / EcoNet EN7528, with experimental EN7571 optical diagnostics. This is an engineering build, **not working GPON firmware**.

The source is [Sirherobrine23/openwrt](https://github.com/Sirherobrine23/openwrt) at `880b7e32666d8c87aaf30cd5e99d965788c163ac`. Feed revisions are recorded in `feeds.lock.json`. Upstream retains its original licenses; the kernel changes and build scripts here use GPL-2.0-only.

## Build

Open **Actions → Build JCOW414 diagnostics → Run workflow**. Choose:

- **baseline** (default): use the pinned source, feeds and sanitized LXC configuration, with the appended-DTB boot fix, the RAM-tested UART/LAN board corrections and version `pon-dev3`. The captured `config.lxc.seed` remains historical; the build script overrides its original version label. I2C, optical PHY/MAC and GDM2 remain disabled.
- **probe-only**: enable the I2C controller and EN7571 identity/calibration probe. A paired driver patch returns before optical initialization, frontend registration or starting the control worker. Optical PHY/MAC and GDM2 remain disabled.

The workflow uses an Ubuntu 24.04 standard hosted runner, up to four build jobs (bounded by available CPUs), pinned Actions, download caching, a bounded compiler cache for both variants, and three-day artifact retention. A fallback cache key reuses downloads across patch changes; OpenWrt still verifies source hashes and ccache validates compiler/content keys. It uploads firmware, source/configuration records and logs. It performs no deployment. Matching firmware inputs do not promise byte-identical output across different host environments. A compilation success does not establish bootability, optical correctness or ISP interoperability.

Only public source pins, build scripts, patches and synthetic tests belong in this repository. Device dumps, backups, administrator/Wi-Fi/ISP credentials, ONU identities and per-unit optical calibration blobs are excluded. Calibration is read from each device's own NVMEM field at runtime; it is not embedded into the image.

## Changes

- Point the JCOW414 console at its current `/soc/serial@1fbf0000` location, retaining the new driver's 1.8432-MHz UART clock, and enable the four referenced LAN PHY nodes. The original `pon-dev2` could start Linux but lost readable serial output at console handover and left the LAN PHYs disabled (`-ENODEV`). A locally derived initramfs with only the console path and four PHY status changes produced readable 115200-baud startup and attached LAN PHYs in RAM. CI now gates those exact device-tree properties. This is a temporary baseline bring-up result, not permanent-flash or GPON validation.
- Select `CONFIG_MIPS_RAW_APPENDED_DTB` for the raw zImage/append-dtb boot path. The original `pon-dev1` selected ELF-appended DTB mode and failed its first hardware boot with `Kernel panic - not syncing: no dtb found`. CI now checks both the target template and the resolved kernel configuration and exports the latter, System.map and the kernel ELF header. This correction still requires a successful hardware boot before deployment claims.
- Guard LED netdev hardware-control activation when the returned device has no name. Recovery UART captured a separate startup panic at `strlen(NULL)` in `netdev_trig_activate` while LAN LEDs and the switch were registering. This patch skips hardware-control setup for an unnamed device; live recovery uses disabled LAN activity triggers until corrected firmware is tested.
- Add the JCOW414 calibration cell at reservearea-relative offset `0x140477`, length `0xe1` (225 bytes).
- Remove an unresolved generic calibration-package reference from the inherited Jio device recipe.
- Require a loaded, sufficiently sized EN7571 calibration record with the correct family/profile marker and nonblank target/timing fields before frontend initialization.
- For probe-only builds, add `airoha,diagnostic-only` and the matching early-return driver path. **Never use this board property with an unmodified driver**, which would ignore it and initialize the frontend normally.
- Include LuCI and OMCI UI/agent packages for subsequent integration work. Their presence does not establish a usable PON interface.

The synthetic host test accepts a valid-shaped 225-byte GPON record and rejects seven invalid cases. It uses invented test values, not a device calibration record.

## Device validation

Review the image model, boot format, kernel/partition sizes and recovery path before any installation. First diagnostic boot must be tested with ISP fibre disconnected. Verify Ethernet management, persistent configuration, factory NVMEM reads and silicon detection before evaluating optical initialization. Probe-only mode does not itself assert a physical TX-disable pin.

GPON registration, OMCI service mapping, PPPoE/VLAN configuration and ISP interoperability remain separate hardware tests. EPON and XGS-PON support are not claimed.
