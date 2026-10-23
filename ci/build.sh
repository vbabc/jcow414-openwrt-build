#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$repository/artifacts"
trap 'result=$?; printf "%s\n" "$result" > "$repository/artifacts/build.exit"' EXIT
python3 "$repository/ci/prepare.py" "${VARIANT:?}" 2>&1 | tee "$repository/artifacts/prepare.log"
cd "$BUILD_ROOT/openwrt"
make -j8 download 2>&1 | tee "$repository/artifacts/download.log"
make -j1 V=s target/linux/prepare 2>&1 | tee "$repository/artifacts/kernel-prepare.log"
python3 "$repository/ci/validate-kernel.py" 2>&1 | tee "$repository/artifacts/kernel-validation.log"
jobs=$(nproc)
if (( jobs > 4 )); then jobs=4; fi
printf 'Building with %s jobs\n' "$jobs"
make -j"$jobs" V=s 2>&1 | tee "$repository/artifacts/build.log"
python3 "$repository/ci/collect.py"
