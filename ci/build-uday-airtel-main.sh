#!/usr/bin/env bash
set -euo pipefail

source_url=https://github.com/UdayKhare09/jcow414-openwrt.git
source_revision=8c465baef3247c4673d12de94891f9ee2e15b54a
workspace=$(pwd -P)
artifacts="$workspace/artifacts"
source_dir="$RUNNER_TEMP/jcow414-airtel-main"
feeds="$workspace/ci/uday-airtel-feeds.conf"

mkdir -p "$artifacts" "$workspace/.cache/downloads"
exec > >(tee "$artifacts/build.log") 2>&1
trap 'code=$?; printf "%s\n" "$code" > "$artifacts/build.exit"' EXIT

git init --quiet "$source_dir"
cd "$source_dir"
git remote add origin "$source_url"
git fetch --depth=1 origin "$source_revision"
git checkout --detach FETCH_HEAD
test "$(git rev-parse HEAD)" = "$source_revision"
grep -Fq '!is_omcc && encrypt_mode == 3' target/linux/airoha/patches-6.18/930-409-airoha_en7528_omci_tx_and_control_fix.patch
test ! -e target/linux/airoha/patches-6.18/930-415-airoha_en7528_gpon_alcl_olt_support.patch

printf 'source=%s\nrevision=%s\nbuilder=%s\n' "$source_url" "$source_revision" "$GITHUB_SHA" > "$artifacts/provenance.txt"
cp "$feeds" feeds.conf
cp "$feeds" "$artifacts/feeds.lock.conf"
ln -s "$workspace/.cache/downloads" dl
./scripts/feeds update -a
while read -r type feed locked_url; do
    test "$type" = src-git
    test "$(git -C "feeds/$feed" rev-parse HEAD)" = "${locked_url##*^}"
done < "$feeds"
./scripts/feeds install -a

cp jcow414.defconfig .config
make defconfig
grep -xq 'CONFIG_TARGET_airoha_en7528_DEVICE_jiofiber_jcow414=y' .config
grep -xq 'CONFIG_JSON_OVERVIEW_IMAGE_INFO=y' .config
cp .config "$artifacts/resolved.config"

make -j"$(nproc)" || make -j1 V=s

target=bin/targets/airoha/en7528
mkdir -p "$artifacts/firmware"
images=("$target"/*jiofiber_jcow414*squashfs-sysupgrade.bin)
test "${#images[@]}" -eq 1
test -s "${images[0]}"
cp "${images[0]}" "$artifacts/firmware/"
cp "$target"/*jiofiber_jcow414*.manifest "$artifacts/firmware/"
cp "$target"/{profiles.json,config.buildinfo,feeds.buildinfo,version.buildinfo} "$artifacts/"
(cd "$artifacts/firmware" && sha256sum -- *) > "$artifacts/SHA256SUMS"
