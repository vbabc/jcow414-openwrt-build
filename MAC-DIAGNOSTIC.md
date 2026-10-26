# TX-inhibited MAC / OMCI registration diagnostic

`mac-diag` / `pon-mac-diag-1` is a fibre-disconnected RAM-test variant. It is not GPON service firmware and is not automatically installed.

It retains the previously RAM-tested calibration guard, single PHY owner of GPIO16, active-high transmitter inhibit, limited frontend telemetry and suppressed PHY/frontend periodic workers. MAC probe requires the diagnostic PHY to report inhibit before resolving GDM2 or mapping/programming MAC registers, and rechecks inhibit after OMCI registration. The mode is restricted to EN7528.

The dedicated xPON MAC and GDM2 device nodes are enabled, with explicit optical-frontend and PHY phandles. The MAC initializes software state, clears/masks its interrupts, requests its IRQs and registers generic xPON/OMCI objects. It skips automatic OMCI transport startup. No optical burst, ONU ranging, OMCC or WAN service is claimed.

Diagnostic guards reject GPON and EPON activation, GDM2 link starts, transmitter enable, upstream FE datapath enable, PLOAM transmission and OMCI T-CONT/GEM/service changes. OMCI transport start and transmit are blocked before calling the Ethernet backend. Identity updates only change volatile software state without scheduling a restart. A read-only `control_diagnostic_state` attribute exposes inhibit, started/mac_enabled flags and the interrupt-enable register.

The agent defaults to disabled, dying-gasp policy disabled and OLT-requested reboot disabled. Board-scoped initial configuration removes automatic WAN/WAN6 startup, uses 192.168.1.5 for LAN management and disables LAN DHCP/RA/DHCPv6. These defaults belong only to this diagnostic image; they do not modify a router until booted. Do not install this image over a working AP configuration.

Local validation applies all eight changed files to the pinned source, checks exact resulting bytes, compiles the board DTB and tests the actual extracted PHY GPIO and MAC transport/TX functions. Four deliberately unsafe guard mutations must fail. CI repeats these checks on the fully prepared kernel before compiling it. Build success still requires artifact/binary review and hardware validation.

The existing diagnostic patch was extended rather than adding a new patch name. Cache classification additionally admits only the four internal MAC/OMCI driver files, never public/UAPI or Ethernet-backend headers. No kernel or target objects are cached. Source/feed/config/compiler/host identities and archive integrity remain mandatory. Reuse is conditional on the exact environment key; a compatible cache is not a timing guarantee.

Before any RAM test, verify image hashes/provenance, raw appended DTB, decompression entry/bounds and compiled guards. Keep fibre disconnected and UART/Ethernet recovery connected. Validate management, interrupt quiescence, registered xPON/OMCI objects, UI reads, telemetry and protected flash/calibration hashes. Then power-cycle to return to the known-working installed firmware and repeat integrity checks. Only later, separately reviewed development can permit activation or an ISP fibre test.
