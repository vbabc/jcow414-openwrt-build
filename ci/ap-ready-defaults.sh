#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# No per-unit identity, passwords or calibration are included in this image.
[ "$(cat /tmp/sysinfo/board_name)" = 'jiofiber,jcow414' ] || exit 0
uci -q delete network.wan
uci -q delete network.wan6
uci set network.lan.proto='static'
uci set network.lan.ipaddr='192.168.1.5'
uci set network.lan.netmask='255.255.255.0'
uci set network.lan.gateway='192.168.1.1'
uci -q delete network.lan.dns
uci add_list network.lan.dns='192.168.1.1'
uci set network.lan.delegate='0'
uci set dhcp.lan.ignore='1'
uci set dhcp.lan.ra='disabled'
uci set dhcp.lan.dhcpv6='disabled'
uci set dhcp.lan.ndp='disabled'
uci commit network
uci commit dhcp
/etc/init.d/dnsmasq disable
/etc/init.d/odhcpd disable
# Restore saved LAN LED sections only on the corrected kernel.
for port in 1 2 3 4; do
    for color in amber green; do
        section="led_lan${port}_${color}"
        if [ "$(uci -q get system.$section)" = 'led' ]; then
            uci set system.$section.trigger='netdev'
        fi
    done
done
uci commit system
# Existing secured Wi-Fi settings are retained through the later upgrade.
# Fresh installs need Wi-Fi configured in LuCI; never create an open network.
exit 0
