# Expiring JCOW414 GPON activation RAM experiment

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
