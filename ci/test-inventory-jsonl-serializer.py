#!/usr/bin/env python3
import ast
import json
import re
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
source = source_path.read_text(encoding='utf-8')

# Field regression: readable HexPreview32 must close before the common DumpWritten tail.
preview = 'JSON_LITERAL("\\\",\\\"HexPreview32\\\":\\\""); JSON_TEXT(JsonPreview);'
close = ' JSON_LITERAL("\\\"");'
common = 'JSON_LITERAL(",\\\"DumpWritten\\\":");'
preview_pos = source.index(preview)
else_pos = source.index('} else {', preview_pos)
common_pos = source.index(common, else_pos)
assert source[preview_pos + len(preview):].startswith(close), 'readable HexPreview32 string is not closed inside readable branch'
assert common_pos > else_pos, 'DumpWritten must remain in common tail after readable/unreadable branch'
close_literal = ast.literal_eval('"\\\""')
common_literal = ast.literal_eval('",\\\"DumpWritten\\\":"')
readable = '{"HexPreview32":"00A1B2C3' + close_literal + common_literal + 'true}'
unreadable = '{"HexPreview32":null' + common_literal + 'false}'
assert json.loads(readable) == {'HexPreview32': '00A1B2C3', 'DumpWritten': True}
assert json.loads(unreadable) == {'HexPreview32': None, 'DumpWritten': False}
print('inventory JSONL serializer contract: PASS')

pkg_root = source_path.parent.parent
c_text = (pkg_root / 'App/Core/InventoryEnumerator.c').read_text(encoding='utf-8')
h_text = (pkg_root / 'App/Core/InventoryEnumerator.h').read_text(encoding='utf-8')

assert '#define FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT 7u' in h_text
assert '#define FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT 5u' not in h_text
assert 'SystemConfig' not in c_text

expected = [
    ('kSioIt8669eSetup00Name', 'SioIt8669eSetup00', 17, [0x4A,0xD6,0x0E,0xB9,0x67,0xF6,0x4D,0xAF,0xAF,0x67,0x99,0x5E,0x90,0x92,0x63,0xCB]),
    ('kAmdSetupName', 'AmdSetup', 8, [0x3A,0x99,0x75,0x02,0x64,0x7A,0x4C,0x82,0x99,0x8E,0x52,0xEF,0x94,0x86,0xA2,0x47]),
    ('kSetupName', 'Setup', 5, [0xA0,0x4A,0x27,0xF4,0xDF,0x00,0x4D,0x42,0xB5,0x52,0x39,0x51,0x13,0x02,0x11,0x3D]),
    ('kCustomName', 'Custom', 6, [0xA0,0x4A,0x27,0xF4,0xDF,0x00,0x4D,0x42,0xB5,0x52,0x39,0x51,0x13,0x02,0x11,0x3D]),
    ('kD01SetupConfigName', 'D01SetupConfig', 14, [0xEA,0x4A,0xEF,0xC7,0xD0,0xAC,0x48,0xDE,0xA2,0x46,0xBE,0x73,0xD9,0xC1,0xED,0xC1]),
    ('kD01CustomName', 'D01Custom', 9, [0xEA,0x4A,0xEF,0xC7,0xD0,0xAC,0x48,0xDE,0xA2,0x46,0xBE,0x73,0xD9,0xC1,0xED,0xC1]),
    ('kAmdPbsSetupName', 'AMD_PBS_SETUP', 13, [0xA3,0x39,0xD7,0x46,0xF6,0x78,0x49,0xB3,0x9F,0xC7,0x54,0xCE,0x0F,0x9D,0xF2,0x26]),
]

def decode_name(symbol: str) -> str:
    match = re.search(
        rf'static const uint16_t {re.escape(symbol)}\[\] = \{{\s*(.*?)\s*\}};',
        c_text,
        re.DOTALL,
    )
    assert match, f'missing name array: {symbol}'
    chars = re.findall(r"'(?:\\.|[^'])+'", match.group(1))
    return ''.join(ast.literal_eval(token) for token in chars)

table_match = re.search(
    r'static const FW_INVENTORY_KEY kSupplementalTargets\[FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT\] = \{\s*(.*?)\s*\};',
    c_text,
    re.DOTALL,
)
assert table_match, 'supplemental target table missing'
entry_re = re.compile(r'\{\s*(k\w+),\s*(\d+)u,\s*\{\s*([^}]*)\s*\}\s*\}')
entries = []
for symbol, units, guid_text in entry_re.findall(table_match.group(1)):
    guid = [int(token, 16) for token in re.findall(r'0x([0-9A-Fa-f]{2})', guid_text)]
    entries.append((symbol, int(units), guid))

assert len(entries) == 7, f'expected 7 supplemental entries, got {len(entries)}'
for index, (symbol, name, units, guid) in enumerate(expected):
    assert decode_name(symbol) == name, (symbol, decode_name(symbol), name)
    assert entries[index] == (symbol, units, guid), (index, entries[index], symbol, units, guid)

print('inventory supplemental target priority contract: PASS')
