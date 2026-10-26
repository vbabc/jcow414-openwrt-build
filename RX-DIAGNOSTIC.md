# Passive GPON MAC receive diagnostic

`rx-diag` / `pon-rx-diag-1` extends the guarded MAC registration variant. It is a fibre-disconnected RAM bench test, not working GPON service firmware.

All existing single-owner GPIO16, per-unit calibration, transmitter, transport, PLOAM/service and agent-off guards remain. The normal gpon_enable()/epon_enable() and OMCI transport are still blocked. The diagnostic does not enable FE/GDM2 channels, transmit calibration/TGEN, PLOAM activation, IRQs, link/recovery workers or WAN startup.

A separate passive startup verifies the PHY inhibit, masks interrupts, uses the existing EN7528 MAC reset sequence, rechecks inhibit and resets activation context to O1. It releases only MBI/MPI RX stop requests while preserving both TX stop requests. A bounded register poll requires those request bits and MPI_TX_STOP_DONE. A final GPIO-inhibit readback must pass before rx_started is set. Post-admission failures and driver removal stop both directions and leave interrupts masked. An initial admission failure returns before any MAC writes.

A failed RX attempt is reported as a diagnostic result; the registered control device remains available for inspection, rather than repeatedly retrying. Read-only rx_diagnostic_state reports requested/started/result, MBI/MPI stop bits, activation, interrupt enable/raw status, FIFO depth and RX GTC counter. The existing control/PHY status attributes retain their format. The old misleading pre-guard 'starting OMCI transport' log is moved to the actual non-diagnostic startup path.

CI tests the actual extracted RX functions with simulated MMIO and injected initial/post-reset/final inhibit failures, reset/init errors and missing TX-stop acknowledgement. Two unsafe mutations must fail, in addition to the existing four PHY/MAC mutations. The exact applied source and compiled board are checked before the full kernel build.

Hardware behavior remains unverified. TX stop request/readback and GPIO status are software observations, not physical voltage or optical-emission measurements. Keeping the fibre disconnected is required for the first RAM test. Even successful startup will not prove downstream decoding under light: FE DMA/transport is stopped and received traffic may back up. A later reviewed passive fibre test can examine LOS, PHY lock and MAC observations before any transmitter/OLT registration work.

No ISP identity is set, no factory calibration is overwritten and no deployment occurs. Use new image-specific artifact/binary verification and RAM helpers, preserve protected hashes and power-cycle back to installed firmware after testing. Compiled tools may be reused only on the exact existing cache key; runtime kernel/target objects remain fresh.
