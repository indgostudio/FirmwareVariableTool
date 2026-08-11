#!/usr/bin/env python3
import ast
import json
import sys
from pathlib import Path

# Field regression: readable HexPreview32 must close before the common DumpWritten tail.
source_path = Path(sys.argv[1])
source = source_path.read_text(encoding='utf-8')
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
enumerator_c = pkg_root / 'App/Core/InventoryEnumerator.c'
enumerator_h = pkg_root / 'App/Core/InventoryEnumerator.h'
print('--- InventoryEnumerator.c ---')
print(enumerator_c.read_text(encoding='utf-8'))
print('--- InventoryEnumerator.h ---')
print(enumerator_h.read_text(encoding='utf-8'))
print('--- end enumerator evidence ---')

# Investigation-priority RED/contract.
combined = enumerator_c.read_text(encoding='utf-8') + '\n' + enumerator_h.read_text(encoding='utf-8')
expected_names = [
    'SioIt8669eSetup00',
    'AmdSetup',
    'Setup',
    'Custom',
    'D01SetupConfig',
    'D01Custom',
    'AMD_PBS_SETUP',
]
positions = []
for name in expected_names:
    pos = combined.find(name)
    assert pos >= 0, f'missing required supplemental target name: {name}'
    positions.append(pos)
assert positions == sorted(positions), f'supplemental target priority order is wrong: {positions}'
assert 'SystemConfig' not in combined, 'obsolete SystemConfig supplemental target remains'
print('inventory supplemental target priority contract: PASS')
