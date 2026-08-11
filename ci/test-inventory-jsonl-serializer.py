#!/usr/bin/env python3
import ast
import json
import re
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
source = source_path.read_text(encoding='utf-8')

preview_marker = 'JSON_LITERAL("\\\",\\\"HexPreview32\\\":\\\""); JSON_TEXT(JsonPreview);'
preview_pos = source.index(preview_marker)
tail = source[preview_pos + len(preview_marker):]
next_literal = re.search(r'JSON_LITERAL\(("(?:\\.|[^"\\])*")\);', tail)
if next_literal is None:
    raise SystemExit('no JSON literal follows HexPreview32 serializer call')

boundary = ast.literal_eval(next_literal.group(1))
# This is the exact production boundary that regressed in the field pass.
# It must close the preview string and introduce DumpWritten.
assert boundary == '\",\"DumpWritten\":', repr(boundary)
readable_line = '{"HexPreview32":"00A1B2C3' + boundary + 'true}'
readable_obj = json.loads(readable_line)
assert readable_obj == {'HexPreview32': '00A1B2C3', 'DumpWritten': True}

# The null-preview path was valid in the field pass; retain it as a control.
unreadable_line = '{"HexPreview32":null,"DumpWritten":false}'
unreadable_obj = json.loads(unreadable_line)
assert unreadable_obj == {'HexPreview32': None, 'DumpWritten': False}

print('inventory JSONL serializer contract: PASS')
