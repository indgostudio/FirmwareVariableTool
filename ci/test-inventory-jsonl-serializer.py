#!/usr/bin/env python3
import ast
import json
import re
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
source = source_path.read_text(encoding='utf-8')

prefix_start = source.index('JSON_LITERAL("{\\\"VariableName\\\":\\\"")')
branch_start = source.index('        if (Readable) {', prefix_start)
else_start = source.index('        } else {', branch_start)
branch_end = source.index('        }\n', else_start + len('        } else {'))

prefix = source[prefix_start:branch_start]
readable = source[branch_start + len('        if (Readable) {'):else_start]
unreadable = source[else_start + len('        } else {'):branch_end]

call_re = re.compile(r'JSON_(LITERAL|TEXT)\(([^;]+?)\);')
values = {
    'JsonName': 'ExampleVar',
    'Guid': 'A339D746-F678-49B3-9FC7-54CE0F9DF226',
    'Attributes': '0x00000007',
    'DataSize': '4',
    'StatusName': 'EFI_SUCCESS',
    'StatusHex': '0x0000000000000000',
    'JsonCrc': '0x12345678',
    'JsonPreview': '00A1B2C3',
    'DumpText': 'true',
}

def render(segment: str) -> str:
    out = []
    for kind, expr in call_re.findall(segment):
        if kind == 'LITERAL':
            out.append(ast.literal_eval(expr.strip()))
            continue
        name = expr.strip()
        if name in values:
            out.append(values[name])
            continue
        rendered = ''.join(out)
        out.append('X' if rendered.endswith('"') else '0')
    return ''.join(out)

# The regression is specifically the boundary between HexPreview32 and
# DumpWritten. Close a representative object immediately after DumpWritten so
# later metadata fields cannot mask or create failures in this focused gate.
readable = readable[:readable.index('JSON_TEXT(DumpText);') + len('JSON_TEXT(DumpText);')]
unreadable = unreadable[:unreadable.index('JSON_TEXT(DumpText);') + len('JSON_TEXT(DumpText);')]

readable_line = render(prefix) + render(readable) + '}'
readable_obj = json.loads(readable_line)
assert readable_obj['HexPreview32'] == '00A1B2C3'
assert readable_obj['DumpWritten'] is True

unreadable_line = render(prefix) + render(unreadable) + '}'
unreadable_obj = json.loads(unreadable_line)
assert unreadable_obj['HexPreview32'] is None
assert unreadable_obj['DumpWritten'] is True

print('inventory JSONL serializer contract: PASS')
