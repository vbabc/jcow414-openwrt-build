# Isolated toolchain cache experiment

Branch `experiment/toolchain-cache-v1` is based on the frontend-diag firmware
inputs from main commit e5ab43f5eb8931dfb0babe8f99be95968d46efa0. It changes
only the experimental build path, not source/feed pins, firmware seeds,
hardware patches or the existing kernel/DTB/image validation scripts.

The manually dispatched build.yml runs two sequential passes on independent
public Ubuntu runners. Prime builds the complete firmware and saves only a
bounded tools/compiler archive. Warm checks the exact environment/config/source
identity and archive SHA-256, restores it, then freshly prepares/checks/builds
the current kernel and target packages. Neither pass deploys anything.

Source recipe mtimes are normalized to the pinned Git timestamp because the
upstream prepared-stamp hash includes file mtimes. Toolchain objects and their
matching metadata are retained together. Firmware version-label fields are
excluded from compiler compatibility; target/compiler/package config is retained.
Driver-only patches do not invalidate the compiler; changed patch names, header
patches, source/feeds, kernel template, image recipe or host image/compiler do.

The normal downloads/compiler cache is restored read-only. The only cache save
uses the separate jcow414-speed-v1-tools prefix and is limited to 2 GiB compressed.
No existing cache is deleted, and there are no broad restore keys for compiled
tools. Kernel and target objects are excluded. A missing warm cache, incompatible
environment, oversized archive or checksum error fails the experiment explicitly.
The default 10 GiB repository cache allowance is shared, so inspect usage before
dispatch. No paid runner, storage-limit increase or billing change is required.

Phase timings and transfer/compression times are saved in separately named
artifacts. The first pass pays the cache creation cost; only the second measures
reuse. Results must be measured before merging anything into main. Matching
inputs do not promise bit-identical firmware across runner environments.

Local checks: `python3 tests/test-toolchain-cache.py`, Python syntax, Bash syntax,
manual/reusable workflow structure, pinned Actions and publication allowlist scan.
These tests use synthetic tools and small archives, not router data or a local
firmware compilation. Full kernel compilation and warm-cache behavior are tested
by the isolated GitHub workflow.
