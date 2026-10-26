#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
trap 'result=$?; printf "%s\n" "$result" > "$repository/artifacts/build.exit"' EXIT
cd "$BUILD_ROOT/openwrt"
timed_make() {
  local phase=$1
  shift
  /usr/bin/time -f "$phase %e" -a -o "$repository/artifacts/phase-seconds.txt" \
    make "$@" 2>&1 | tee "$repository/artifacts/$phase.log"
}
jobs=$(nproc)
if (( jobs > 4 )); then jobs=4; fi
printf 'Experiment phase %s, %s jobs\n' "$EXPERIMENT_PHASE" "$jobs"
timed_make download -j8 download
timed_make tools-toolchain -j"$jobs" V=s tools/install toolchain/install
timed_make kernel-prepare -j1 V=s target/linux/prepare
python3 "$repository/ci/validate-kernel.py" 2>&1 | tee "$repository/artifacts/kernel-validation.log"
timed_make firmware -j"$jobs" V=s
python3 "$repository/ci/collect.py"
