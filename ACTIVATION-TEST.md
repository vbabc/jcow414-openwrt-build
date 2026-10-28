# Expiring JCOW414 GPON activation RAM experiment

## Stock rev2 burst-control comparison: pon-activation-test-7

Test6 applied the stock delay normalization but still reached only O3. All72
complete active frontend snapshots showed DUMMY bit10 clear. Exact JCOW414 R2.52
phy.ko en7571_link_reg(1) calls en7571_burst_ctrl after rev2 delay setup; the
callee reads0x015c and ORs byte1 with0x04, preserving other bits. The generic
helper exists but its rev2 link path omits that call.

Test7 adds only a checked byte RMW in rev2 frontend rearm, after the existing
delay step and before DCL/rogue/safe operations: DUMMY+1, keep0xfb, set0x04.
An I2C error returns immediately. Reset/id/neighboring bits, other revisions,
TGEN/T0C/T1C, laser targets, factory calibration, identity, guard20, RX delay and
negotiated preamble are unchanged. The symbolic name burst-control-off does not
by itself establish the hardware gate's physical behavior or valid OLT reception.
This is a same-hardware stock-sequence hypothesis, not a demonstrated GPON fix.

Actual-function tests cover all65536 delay/DUMMY-byte pairs, idempotent rearm,
other revisions, eight bus-error positions and nine rejected mutations. Existing
gate/identity/expiry, preamble, guard, RX-delay and board checks remain required.
The firmware remains default-off, manually armed and limited to180seconds.
The next hardware admission must verify the bit under inhibit without fibre,
then use one recorded owner-controlled optical attempt. No permanent flash.
An owner-requested clean handover will also leave the previous ONT powered off
before fibre transfer; this external procedure is not a kernel change. Success
would require a later controlled comparison before assigning cause to either.

## Stock rev2 link-timing comparison: pon-activation-test-6

Test5 still reached O3 without O4/O5. The exact JCOW414 R2.52 phy.ko
`en7571_init()` calls GPON TGEN before `en7571_link_reg(1)`. Its rev2 branch
calls `en7571_T1delay_setting(0)`, which preserves T1DELAY byte0 bits7:4 and
clears bits3:0. Our frontend's rev2 link helper omits that operation, while
late runtime TGEN leaves byte0 at0xaa on this unit.

Test6 adds only that rev2 byte normalization at the start of frontend TX
rearm:0xaa becomes0xa0. It checks and propagates I2C errors before DCL,
rogue-latch clearing or safe-circuit reset. The high nibble and other three
timing bytes, including factory T0C/T1C and ERC/reset bits, are preserved.
Other revisions keep their existing behavior. Burst-control, power, calibration,
serial/PLOAM, guard20, measured RX delay and negotiated preamble remain unchanged.
This is a stock-derived hypothesis, not a demonstrated Airtel registration fix.
It does not copy the stock manufacturing calibration routine or write flash.

Local tests compile the real frontend rearm and byte RMW functions. They cover
all256 initial delay-byte values, other revisions, six bus-error positions,
unchanged neighboring bytes and operation ordering. Five unsafe mutations
are rejected. Earlier MAC/PHY, identity/lease, preamble, guard, RX-delay and
DTB checks also pass. Full compilation, compiled-code and artifact review,
and a no-fibre RAM test must precede a recorded optical attempt. The manual
identity gate, default-off transmitter and180-second nonrenewable lease remain.

## Stock guard-default comparison: pon-activation-test-5

Test4 exercised the measured RX-delay correction but still received no matching
ONU-ID assignment. Test5 changes only the EN7528 match-data guard override from
unset to the existing value 20. Exact JCOW414 R2.52 xpon.ko initializes its guard
byte to 20 and passes that byte literally to PHY preamble bits 7:0 and MAC guard
bits 7:0. A separate debug command accepts a runtime byte override. No startup
caller was found in the preserved filesystem; this does not prove the value used
on every stock boot or establish Airtel compatibility.

This is one bounded comparison against the stock default, not a timing sweep or
a confirmed registration fix. Serial, PLOAM, RX-delay arithmetic, preamble retry,
optical calibration and all transmitter/identity/expiry controls are unchanged.
The EN7528 match-data object also serves the en751627 compatible in the source;
this build targets JCOW414 only and makes no validation claim for other boards.
EN7523 and EN751221 match-data objects remain unchanged.

Local tests compile the real MAC callback and PHY writer together and exercise
announced guard values 0, 20, 32 and 255. Four mutations are rejected: missing
override, another board's 24, MAC retaining the announced value, and PHY dropping
the guard. Existing RX-delay, preamble, activation lifecycle and DTB checks pass.
Full firmware compilation, artifact review and hardware tests remain pending.

## Measured MAC RX-delay candidate: pon-activation-test-4

Test3 restored the negotiated preamble on15 hardware retries but still stalled at O3. This candidate changes only the EN7528 match-data flag that admits the existing `gpon_adjust_mac_rx_delay()` routine. JCOW414 stock R2.52 xpon.ko invokes its equivalent from the broadcast upstream-overhead handler in O2 before entering O3: select the RX-delay probe, halve its measured value, compensate response-time excess above0x577 and program the masked fixed-RX-delay field.

The stock module is a Jio-network hardware reference, not an Airtel provisioning template. This candidate copies no subscriber identity, OLT profile, calibration, laser power, fixed measured delay or alternate board defaults. The OLT-announced guard remains unchanged; stock's default guard20 is a separate untested lead. Active response-time0x577 and fine-delay0x1c were already consistent with the exact stock module and stay unchanged.

All function bodies, PHY/frontend/API, runtime identity, preamble cache, Start/Stop, default-off controls and180s non-renewing lease remain unchanged from test3. Only the EN7528 data flag changes in the activation-only overlay. Actual-function tests cover measured half-delay, response compensation, preservation of unrelated bits, disabled-family behavior and three rejected negative mutations. Existing preamble, reader, lifecycle and board checks remain required. Artifact/compiled review and a no-fibre RAM test precede any new optical attempt. This is not a confirmed Airtel fix.


## Negotiated-preamble retry candidate: pon-activation-test-3

A second bounded optical test with the owner's serial and PLOAM value matched still cycled O2/O3, despite serial grants and hardware TX counters. No O4/O5 or OMCI exchange was observed. Protected hashes matched and the test expired with TX inhibited.

Audit of the complete pinned PLOAM FSM found that O2 clears PHY extended-T3 lengths/mode. The next Upstream_Overhead enters O3 without restoring them, while Extended_Burst_Length is accepted only in O3. This candidate caches only successfully programmed negotiated lengths, restores them before the MAC O3/O4 activation write, retains the cache across same-session TO1 retries and invalidates it on O1/O7 or full hardware reset. Restore failure or blocked admission disables TX and skips the MAC activation write. No other board's lengths, laser power or calibration are copied.

The PHY/frontend/API source and ten safety/lifecycle functions remain byte-identical to test2. The actual-C test exercises the unmodified PLOAM handlers, changed MAC callback prefix and actual PHY functions: repeated retries, new length values, stale-session invalidation and fail-closed errors. Three unsafe preamble mutations and the existing eight unsafe gate mutations are rejected. The callback tail after the MAC activation write is unchanged and excluded from that unit harness. Full compilation, compiled-code verification and RAM hardware validation remain necessary. No claim of a confirmed registration fix.

The private-safe root-only reader adds cache-validity/negotiated-length/restore-count fields. Existing Start/Stop and 180-second expiry remain unchanged. No identity, password, BOB data or packet payloads are in these public inputs.

## Diagnostic follow-up: pon-activation-test-2

The first owner-controlled 180-second active RAM trial reached O3 repeatedly, with stable downstream lock, but no O4/O5 or OMCI packets. It ended automatically with PHY/MAC off and TX inhibited; protected flash/calibration hashes matched. The cause is unresolved. Detailed serial-event logs were compiled out and runtime dynamic debug is unavailable.

This follow-up adds root-only `registration_state` (0400) beside `activation`. It reports hardware/configured serial equality as a boolean, serial-request/serial-sent/ranging/PLOAM IRQ-work **batches**, existing PLOAM/assignment counters, cached PHY transmit counters and safe MAC timing/status snapshots. It never returns subscriber identity bytes or PLOAM payloads. Batches can coalesce multiple interrupts; snapshots are not transactionally coherent. PHY counters include a sample count and result code and are cached from the already-existing serial-event reader; reading sysfs does not enable counters, write registers, clear interrupts, drain a FIFO or control activation.

The calibrated PHY/frontend and PHY API are byte-identical to test1 source. Eleven lifecycle/serial/timing functions were compared unchanged, including Start/Stop/expiry/shutdown and serial register programming. The 180-second lease and default-off identity gate remain unchanged. The earlier canonical-path ACL and LuCI module/menu fix is included. This is diagnostic instrumentation, not a demonstrated registration fix or flashable production firmware. Use only the verified initramfs for the next RAM test.

`activation-test` / `pon-activation-test-1` is a separately selected engineering variant. It is not verified working GPON/Internet firmware and must not be flashed. The previous RX and other diagnostic variants retain their exact original patch inputs.

## Default state and controls

GPIO16 is still owned only by the PHY and requested high. Both the PHY and MAC have the manual-activation property. Probe registers the OMCI device but never starts its transport; default WAN/WAN6 startup is removed, management is192.168.1.5/24, LAN DHCP/RA is off, and the agent/dying-gasp/OLT-reboot policies default off. The optical frontend must load and validate the unit's own factory225-byte calibration before initialization; it verifies PHY inhibit before and after initialization. This variant restores normal calibrated frontend ops and its normal control worker. The digital PHY is initialized/powered by the normal GPON start lifecycle, not by the frontend diagnostic reference.

An explicit runtime serial configuration from NETLINK or SYSFS is mandatory before starting. Default/driver/device-tree/NVMEM identity alone cannot arm the experiment. Actual subscriber identity and WAN credentials are never build inputs.

LuCI: **Network -> OMCI -> Activation test**. Apply the GPON serial through the existing OMCI General settings UI first. Enable its baseline agent for OMCI responses when ready for the registration test. **Start3-minute test** writes1 to the root-only activation attribute; **Stop test** writes0. The page polls a non-sensitive status line and has no automatic start. Access is restricted to that exact sysfs file, plus kernel CAP_NET_ADMIN.

The control is `/sys/bus/platform/devices/1fb60000.xmac/activation`. It reports armed/identity-configured, fixed180s maximum lease, MAC/IRQ/activation/FIFO/RX state and GPIO inhibit readback. Repeated Start while armed returns EALREADY and cannot extend the lease. The lease is not a displayed countdown.

## Startup, stop and failure ordering

A mutex serializes manual control/expiry. Start requires explicit identity and TX-disable readback1, grants permission at the PHY without releasing the pin, then admits normal OMCI/Ethernet/GPON startup. Normal GPON/FE/PLOAM/service and OMCI transmit paths remain blocked until manually armed. EPON stays prohibited for this variant.

PHY power-on keeps TX-disable asserted before/after configuration, even when armed. The EN7528 match data requests normal transmitter timing calibration; it runs with the inhibit held. The normal GPON downstream-overhead path rearms the calibrated frontend and may release TX-disable for protocol-controlled upstream bursts. This is the first activation-capable experiment: it intentionally permits optical transmission after explicit Start, unlike the RX variant.

A180s delayed worker, Stop, startup failure, driver removal and platform shutdown close software admission and assert physical inhibit before draining OMCI/GPON work; interrupts and all RX/TX stop requests are then quiesced and FE is disabled. The PHY GPIO setter and arm/disarm use the same mutex, preventing a stale enable from releasing GPIO after disarm returns. Stop propagates inhibit/FE readback errors. This is software protection; physical emission is not measured by these tests.

## Validation and rollout

Local tests apply the exact five-file overlay onto the reviewed RX source, compile the actual PHY/manual lifecycle/transport/sysfs functions with fake hardware and injected failures, and reject eight unsafe mutations. Identity-source truth cases include driver/default refusal and explicit NETLINK/SYSFS acceptance. Compiled board phandles, single GPIO owner, management UART/LAN and resource ranges pass. Existing five cache tests pass. Full CI/kernel compilation, artifact/provenance/compiled-instruction/rootfs verification and hardware tests remain required.

The overlay is `ci/activation-kernel.patch`, copied as kernel patch1004 only for this variant. Preparation rejects it unless it touches only the existing kernel-driver allowlist. Its exact SHA256 is recorded in provenance and the patch is retained as an artifact. It does not affect compiled host/tools/compiler inputs; runtime kernel and packages are always built fresh. No package-selection, source/feed pin, workflow permissions, runner class or cache-admission relaxation is introduced.

First boot and explicit Start/Stop/expiry fault checks must use RAM with fibre disconnected. Only after those checks pass should an owner-controlled short ISP registration test use the owner's private identity, independent internet and UART recovery. O5 registration, OMCI provisioning, VLAN/PPPoE WAN, UI application/persistence and eventual permanent installation remain unproven. Keep the known installed firmware and protected partitions intact; full power-off clears temporary optical state.

## Initial hardware admission and UI correction

The first build booted from RAM on one JCOW414. Default-off, refusal before runtime identity, synthetic serial application through LuCI, calibrated no-fibre Start, manual Stop and automatic expiry were observed. No OLT registration or WAN is established. MPI stop acknowledgement warnings remain unresolved; a shutdown-time RX telemetry timeout later recovered. The initial UI used a sysfs alias that failed the RPC file ACL. The corrected UI and ACL use the canonical /sys/devices/platform/soc/1fb60000.xmac/activation path and a fresh activation-test module name. These UI-only corrections were validated as temporary RAM file changes; they need inclusion in the next packaged build. Kernel overlay is unchanged.
