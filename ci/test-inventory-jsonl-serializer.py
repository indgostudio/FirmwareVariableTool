#!/usr/bin/env python3
import ast
import json
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text(encoding='utf-8')
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
