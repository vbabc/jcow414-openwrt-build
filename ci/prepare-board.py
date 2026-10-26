"""Apply the first, non-transmitting JCOW414 diagnostic board change."""
import argparse
import difflib
import json
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument('source', type=pathlib.Path)
args = parser.parse_args()
source = args.source.resolve()
assert (source / 'target/linux/airoha/en7528/target.mk').is_file(), 'Unexpected source checkout'
patches = []

def record(relative, modify):
    path = source / relative
    before = path.read_text()
    after = modify(before)
    if before != after:
        patches.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile='a/'+relative, tofile='b/'+relative))
        path.write_text(after)

addition = '''
/* RAM-tested board fixes: select the actual UART and enable LAN PHYs. */
/ {
	chosen {
		stdout-path = "/soc/serial@1fbf0000:115200";
	};
};

&gsw_phy1 { status = "okay"; };
&gsw_phy2 { status = "okay"; };
&gsw_phy3 { status = "okay"; };
&gsw_phy4 { status = "okay"; };

/*
 * JCOW414 factory optical calibration, recovered offline from this unit's
 * stock production record. The stock exporter writes 225 bytes from this
 * field; EN7571 GPON magic is at field-relative 0x94.
 *
 * This diagnostic change only exposes the existing calibration
 * through NVMEM. Optical MAC/PHY and frontend activation remain disabled.
 */
&spi {
	flash@0 {
		partitions {
			partition@ddc0000 {
				nvmem-layout {
					jcow414_optical_bob: calibration@140477 {
						reg = <0x140477 0xe1>;
					};
				};
			};
		};
	};
};
'''

def amend_board(before):
    assert 'jiofiber,jcow414' in before and '#include "en7528_jiofiber.dtsi"' in before
    assert 'calibration@140477' not in before, 'Board patch already applied'
    return before.rstrip() + '\n' + addition

record('target/linux/airoha/dts/en7528_jiofiber_jcow414.dts', amend_board)

def amend_image(before):
    # This pinned tree references this package but contains no definition for
    # it. Per-unit calibration will come from NVMEM, not a generic blob.
    needle = 'kmod-mt7663-firmware-ap \\\n                     airoha-en7571-firmware'
    assert needle in before, 'Unexpected JCOW image recipe'
    return before.replace(needle, 'kmod-mt7663-firmware-ap', 1)

record('target/linux/airoha/image/en7528.mk', amend_image)


def amend_kernel_config(before):
    # This image recipe appends the board DTB to a raw zImage. The MIPS
    # decompressor only carries that DTB into the kernel in RAW mode.
    needle = 'CONFIG_MIPS_ELF_APPENDED_DTB=y\n'
    assert before.count(needle) == 1, 'Unexpected EN7528 appended-DTB configuration'
    assert 'CONFIG_MIPS_RAW_APPENDED_DTB=y' not in before
    return before.replace(needle, '# CONFIG_MIPS_ELF_APPENDED_DTB is not set\nCONFIG_MIPS_RAW_APPENDED_DTB=y\n', 1)


record('target/linux/airoha/en7528/config-6.18', amend_kernel_config)
output = source.parent / 'jcow414-diagnostic-board.patch'
output.write_text(''.join(patches))
print(json.dumps({'patch': str(output), 'optical_activation_enabled': False, 'factory_data_written': False}))
