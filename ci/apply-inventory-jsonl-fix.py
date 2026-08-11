#!/usr/bin/env python3
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
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
path.write_bytes(fixed)
print('inventory JSONL readable preview quote fixed')
