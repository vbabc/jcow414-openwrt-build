# TX-inhibited digital-PHY diagnostic

This is a bench bring-up variant, not GPON WAN service. Keep fibre disconnected
and test a verified initramfs from RAM with serial/Ethernet recovery available.
Source/feed pins and all existing per-unit calibration, appended-DTB, UART/LAN
and image validation checks are retained.

The PHY is the only GPIO16 owner in this variant. The EN7571 node references it
with phys/phy-names instead of requesting that GPIO. Supplier probe asserts
TX-disable high; the client verifies the diagnostic mode and reads back high
before programming the analog frontend. After analog initialization it acquires
the PHY lifecycle, configures GPON mode and powers on the digital PHY. Inhibit
is checked again before frontend registration. Managed cleanup powers off/exits
the PHY on client failure/removal.

The PHY's central GPIO setter forces inhibit in diagnostic mode, including its
normal power_on release call. Exported requests to enable transmission return
EPERM. The readback API refuses non-diagnostic suppliers. A read-only
diagnostic_state attribute reports power/inhibit/state/LOS; no status-register
read occurs there while unpowered. Both the PHY recovery worker and the
frontend control worker are omitted. Frontend transmit callbacks/debug controls
remain absent. The monitor name uses underscores to avoid the earlier warning.

Only the existing EN7528 0x600-byte PHY resource is enabled. Optical MAC and
GDM2 remain disabled; no OMCI/registration/data service is claimed. The optional
VCC-disable signal is not added because its board wiring/polarity has not been
independently validated.

CI applies and inspects the actual prepared kernel source, compiles extracted
GPIO functions against simulated pins, exercises normal/diagnostic/error paths,
and verifies that two unsafe guard mutations fail the tests. It compiles/checks
the actual DTB for one GPIO owner, correct provider/consumer phandles, active-high
GPIO16, EN7528 resource bounds, disabled MAC/GDM2 and retained UART/LAN settings.
The full kernel build is still required. Before a RAM test, review the resulting
compiled branches and current register/reset/pinmux assumptions against the unit.

Hardware validation and independent physical voltage/optical-emission measurement
remain pending. There is no automatic firmware installation in this workflow.
