#!/usr/bin/env python3
import re
import sys
from pathlib import Path

main_path = Path(sys.argv[1])
pkg_root = main_path.parent.parent
enumerator_c = pkg_root / 'App/Core/InventoryEnumerator.c'
enumerator_h = pkg_root / 'App/Core/InventoryEnumerator.h'

# Preserve the accepted JSONL fix.
data = main_path.read_bytes()
bad = b'JSON_LITERAL("\\",\\"HexPreview32\\":\\""); JSON_TEXT(JsonPreview);'
good = bad + b' JSON_LITERAL("\\"");'
bad_count = data.count(bad)
close_count = data.count(good)
if bad_count != 1:
    raise SystemExit(f'expected exactly one readable HexPreview32 serializer sequence, found {bad_count}')
if close_count != 0:
    raise SystemExit(f'readable HexPreview32 serializer unexpectedly already closed ({close_count})')
fixed = data.replace(bad, good, 1)
if fixed.count(good) != 1:
    raise SystemExit('JSONL readable-preview quote closure postcondition failed')
common = b'JSON_LITERAL(",\\"DumpWritten\\":");'
if fixed.count(common) != 1:
    raise SystemExit(f'expected one common DumpWritten tail, found {fixed.count(common)}')
main_path.write_bytes(fixed)

# Replace only the fixed supplemental name/table block.
c_text = enumerator_c.read_text(encoding='utf-8')
pattern = re.compile(
    r'static const uint16_t kAmdPbsSetupName\[\] = \{.*?'
    r'static const FW_INVENTORY_KEY kSupplementalTargets\[FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT\] = \{.*?'
    r'\n\};',
    re.DOTALL,
)
replacement = '''static const uint16_t kSioIt8669eSetup00Name[] = {
    'S','i','o','I','t','8','6','6','9','e','S','e','t','u','p','0','0'
};
static const uint16_t kAmdSetupName[] = {
    'A','m','d','S','e','t','u','p'
};
static const uint16_t kSetupName[] = {
    'S','e','t','u','p'
};
static const uint16_t kCustomName[] = {
    'C','u','s','t','o','m'
};
static const uint16_t kD01SetupConfigName[] = {
    'D','0','1','S','e','t','u','p','C','o','n','f','i','g'
};
static const uint16_t kD01CustomName[] = {
    'D','0','1','C','u','s','t','o','m'
};
static const uint16_t kAmdPbsSetupName[] = {
    'A','M','D','_','P','B','S','_','S','E','T','U','P'
};

static const FW_INVENTORY_KEY kSupplementalTargets[FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT] = {
    { kSioIt8669eSetup00Name, 17u, { 0x4A,0xD6,0x0E,0xB9,0x67,0xF6,0x4D,0xAF,0xAF,0x67,0x99,0x5E,0x90,0x92,0x63,0xCB } },
    { kAmdSetupName, 8u, { 0x3A,0x99,0x75,0x02,0x64,0x7A,0x4C,0x82,0x99,0x8E,0x52,0xEF,0x94,0x86,0xA2,0x47 } },
    { kSetupName, 5u, { 0xA0,0x4A,0x27,0xF4,0xDF,0x00,0x4D,0x42,0xB5,0x52,0x39,0x51,0x13,0x02,0x11,0x3D } },
    { kCustomName, 6u, { 0xA0,0x4A,0x27,0xF4,0xDF,0x00,0x4D,0x42,0xB5,0x52,0x39,0x51,0x13,0x02,0x11,0x3D } },
    { kD01SetupConfigName, 14u, { 0xEA,0x4A,0xEF,0xC7,0xD0,0xAC,0x48,0xDE,0xA2,0x46,0xBE,0x73,0xD9,0xC1,0xED,0xC1 } },
    { kD01CustomName, 9u, { 0xEA,0x4A,0xEF,0xC7,0xD0,0xAC,0x48,0xDE,0xA2,0x46,0xBE,0x73,0xD9,0xC1,0xED,0xC1 } },
    { kAmdPbsSetupName, 13u, { 0xA3,0x39,0xD7,0x46,0xF6,0x78,0x49,0xB3,0x9F,0xC7,0x54,0xCE,0x0F,0x9D,0xF2,0x26 } }
};'''
c_fixed, count = pattern.subn(replacement, c_text, count=1)
if count != 1:
    raise SystemExit(f'expected exactly one supplemental target block, found {count}')
if 'kSystemConfigName' in c_fixed or "'S','y','s','t','e','m','C','o','n','f','i','g'" in c_fixed:
    raise SystemExit('obsolete SystemConfig supplemental target remains after replacement')
enumerator_c.write_text(c_fixed, encoding='utf-8', newline='\n')

# Expand the fixed-size seen set through its existing count macro.
h_text = enumerator_h.read_text(encoding='utf-8')
old_count = '#define FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT 5u'
new_count = '#define FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT 7u'
if h_text.count(old_count) != 1:
    raise SystemExit(f'expected exactly one old supplemental target count, found {h_text.count(old_count)}')
if new_count in h_text:
    raise SystemExit('supplemental target count unexpectedly already updated')
enumerator_h.write_text(h_text.replace(old_count, new_count, 1), encoding='utf-8', newline='\n')

print('inventory JSONL fix and investigation target priority update applied')
