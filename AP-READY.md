# AP candidate ap-ready-1

Build-only candidate for JCOW414. No deployment is performed by CI.

Includes the corrected raw-appended DTB boot mode, UART path, four LAN PHYs,
LED netdev unnamed-device guard, own-device calibration guard and cumulative
driver changes through activation-test-7. Test7's burst-control hypothesis has
not been hardware-tested and does not establish working Airtel PON.

The final device tree disables I2C, EN7571, optical PHY/MAC and GDM2. The manual
activation UI is omitted. PON does not operate in this AP image.

Defaults configure management 192.168.1.5/24, gateway/DNS 192.168.1.1 and disable
DHCPv4/DHCPv6/RA/NDP and their server startup. Existing secured Wi-Fi configuration
must be retained from a private backup at the later upgrade. No Wi-Fi passwords,
ONU identities or calibration blobs are embedded. Fresh installs need Wi-Fi setup
through Ethernet/LuCI. Existing saved LAN LED sections regain netdev triggers on
the corrected kernel; visible operation requires a RAM hardware test.

Artifacts include initramfs for RAM validation and permanent factory/sysupgrade
formats. Compilation and offline validation do not prove permanent bootability.
Review the partition format, preserve private AP settings and recovery banks,
then RAM-test Ethernet, both Wi-Fi bands, LEDs and client forwarding before a
separately authorized permanent installation. This is not a stable release claim.
