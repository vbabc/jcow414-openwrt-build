#!/bin/sh
# Temporary diagnostic images only: management LAN, no automatic WAN startup.
[ "$(cat /tmp/sysinfo/board_name)" = 'jiofiber,jcow414' ] || exit 0
uci -q delete network.wan
uci -q delete network.wan6
uci set network.lan.ipaddr='192.168.1.5/24'
uci set dhcp.lan.ignore='1'
uci set dhcp.lan.ra='disabled'
uci set dhcp.lan.dhcpv6='disabled'
uci commit network
uci commit dhcp
exit 0
