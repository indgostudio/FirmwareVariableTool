#!/usr/bin/env python3
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = path.read_bytes()
bad = b'JSON_LITERAL(",\\"DumpWritten\\":");'
good = b'JSON_LITERAL("\\",\\"DumpWritten\\":");'

bad_count = data.count(bad)
good_count = data.count(good)
if bad_count != 1:
    raise SystemExit(f'expected exactly one malformed readable DumpWritten delimiter, found {bad_count}')
if good_count != 0:
    raise SystemExit(f'corrected readable DumpWritten delimiter unexpectedly already present ({good_count})')

fixed = data.replace(bad, good, 1)
if fixed.count(bad) != 0 or fixed.count(good) != 1:
    raise SystemExit('JSONL serializer replacement postcondition failed')
path.write_bytes(fixed)
print('inventory JSONL serializer delimiter fixed')
