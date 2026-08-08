# Firmware Variable Inventory Exporter Design

Date: 2026-08-08
Status: Approved design, pending implementation plan
Branch: `feature/inventory-exporter`

## 1. Objective

Add a third UEFI application, `InventoryVarTool.efi`, to FirmwareVariableTool.

This application is read-only with respect to UEFI variables. It enumerates all variables exposed through `EFI_RUNTIME_SERVICES.GetNextVariableName()`, attempts to read each variable with `GetVariable()`, and exports a machine-parseable inventory plus optional binary dumps to the USB filesystem from which the application was launched.

This work does not add, expose, reuse, or conditionally enable any `SetVariable()` path. Existing `ReadOnlyVarTool.efi` and `WriteVarTool.efi` remain separate applications and are not behaviorally changed by this feature.

## 2. Required USB artifacts

The application writes:

- `\vars.csv`
- `\vars.jsonl`
- `\vars.log`
- optional per-variable binary dumps under `\VarDumps\`

The binary dump threshold is initially 64 KiB (`65536` bytes).

## 3. Application boundary

`InventoryVarTool.efi` is a dedicated UEFI application with its own INF and entry point.

The module contains no `ENABLE_FIRMWARE_WRITES` define and no source file that calls `SetVariable()`.

Portable formatting and policy code is kept separate from UEFI runtime/file-system adapters so it can be exercised by host-side regression tests.

Planned logical components:

- `InventoryVarTool.c`: UEFI application entry point and orchestration.
- `InventoryEnumerator.c/.h`: enumeration state machine and per-variable read policy, expressed so failure-continuation behavior can be host-tested.
- `InventoryFormat.c/.h`: CSV, JSONL, UTF-16 name encoding, EFI status formatting, hex preview, and filename sanitization.
- existing CRC32 implementation, reused where practical; otherwise a portable CRC32 helper with the same polynomial and regression vector.
- existing UEFI file writer abstractions reused only for filesystem output; no firmware-variable write functions are linked into this application.

Exact filenames may be adjusted during implementation to follow existing repository conventions, but these responsibility boundaries are fixed.

## 4. Enumeration algorithm

### 4.1 Initial cursor

Enumeration begins with:

- empty `CHAR16` variable name
- zeroed `EFI_GUID`
- a 1024-`CHAR16` name buffer

### 4.2 `GetNextVariableName()` loop

For every iteration:

1. Preserve the current enumeration cursor name and GUID before the call.
2. Call `GetNextVariableName()` with the current buffer.
3. Log the returned `EFI_STATUS` to `vars.log`.
4. If the status is `EFI_BUFFER_TOO_SMALL`:
   - read the required byte size returned by firmware;
   - allocate a larger name buffer of at least that exact requirement;
   - restore the pre-call cursor name and GUID;
   - retry the same enumeration step.
5. If the status is `EFI_SUCCESS`, process the returned variable and then use it as the cursor for the next iteration.
6. If the status is `EFI_NOT_FOUND`, enumeration is complete.
7. Any other enumeration error is logged. If firmware has not provided a valid next cursor, enumeration cannot safely advance; the loop terminates with a non-success enumeration summary rather than guessing a cursor.

A per-variable `GetVariable()` failure never aborts enumeration.

An unrecoverable failure to allocate or grow the enumeration-name buffer terminates enumeration because forward progress cannot be guaranteed.

## 5. Per-variable read algorithm

For each enumerated `(VariableName, VendorGuid)` pair:

1. Initialize `Attributes = 0` and `DataSize = 0`.
2. Call `GetVariable()` with a `NULL` data buffer to obtain required size and attributes.
3. Log that probe status.
4. If the probe returns `EFI_BUFFER_TOO_SMALL`:
   - allocate exactly `DataSize` bytes;
   - call `GetVariable()` again using that buffer;
   - log the read status.
5. If the probe returns `EFI_SUCCESS` with `DataSize == 0`, treat the zero-length variable as readable without a second allocation/read.
6. If the probe returns another error, mark the variable unreadable, record the returned status and any size/attribute values firmware supplied, and continue enumeration.
7. If the second read fails, mark the variable unreadable, retain the final returned status, release the buffer, and continue enumeration.
8. If readable:
   - compute CRC32 over the complete data buffer;
   - render a hex preview of the first `min(DataSize, 32)` bytes;
   - if `DataSize <= 65536`, attempt a complete binary dump;
   - if larger than the threshold, skip the dump but retain CRC32 and preview.
9. Emit CSV and JSONL records regardless of read success, provided those output sinks remain writable.

`GetVariable status` in CSV/JSONL is the final status describing readability: `EFI_SUCCESS` for readable variables, otherwise the failing probe/read status.

## 6. Inventory schema

### 6.1 Common fields

Every inventory record contains:

- `VariableName`
- `VendorGuid`
- `Attributes`
- `DataSize`
- `GetVariableStatus`
- `GetVariableStatusCode`
- `CRC32`
- `HexPreview32`
- `DumpWritten`

Formatting rules:

- GUID: canonical uppercase `8-4-4-4-12` representation.
- Attributes: `0xXXXXXXXX` hexadecimal.
- EFI status code: full-width hexadecimal appropriate to X64, e.g. `0x8000000000000005`.
- CRC32: `0xXXXXXXXX` when readable; empty in CSV and `null` in JSONL when unreadable.
- Hex preview: uppercase, two hex characters per byte, no separators; empty in CSV and `null` in JSONL when unreadable.
- `DumpWritten`: `true`/`false`.

### 6.2 Variable-name representation

For human readability and deterministic machine parsing:

- printable ASCII UTF-16 code units are emitted literally;
- backslash/control/non-ASCII UTF-16 code units are represented as `\uXXXX` in the logical escaped name;
- CSV then applies RFC 4180-style field quoting to that escaped logical name;
- JSONL applies JSON string escaping to the logical name.

This preserves every UTF-16 code unit without requiring locale-dependent conversion.

### 6.3 CSV

`vars.csv` begins with one header row using the common field names above.

Fields containing comma, quote, CR, or LF are surrounded by double quotes, and embedded double quotes are doubled.

### 6.4 JSONL

`vars.jsonl` contains one valid JSON object per line and no enclosing array.

JSON strings escape quote, backslash, control characters, and encoded UTF-16 content deterministically. Each record is independently parseable.

## 7. `vars.log`

`vars.log` is diagnostic rather than tabular. It records:

- application start and build identity;
- filesystem open/create statuses;
- every `GetNextVariableName()` returned status;
- for every enumerated variable:
  - name and GUID;
  - probe `GetVariable()` status;
  - second-read `GetVariable()` status when performed;
  - data allocation failure if any;
  - dump creation/write status when attempted;
- CSV/JSONL/log write failures;
- final counters and completion status.

All logged EFI statuses include both symbolic text and numeric hexadecimal value.

Unknown EFI status values are rendered as `EFI_STATUS_UNKNOWN` plus their numeric value; they are never dropped or coerced to a known status.

## 8. Dump filenames

Binary dump pattern:

`\VarDumps\<GUID>__<sanitized-variable-name>.bin`

Sanitization rules:

- ASCII letters, digits, `-`, `_`, and `.` are retained.
- characters unsafe or ambiguous for FAT filenames are replaced with `_`.
- if the variable name is empty or contains non-printable UTF-16, the base name uses deterministic `utf16hex_<hex-code-units>` encoding rather than an empty/ambiguous string.
- excessively long filename components are truncated to a safe component length and receive a deterministic CRC32 suffix derived from the original UTF-16 name.
- if sanitization still produces a filename collision for the same GUID, a deterministic CRC32 suffix is appended before `.bin`; existing dumps are never silently overwritten by a different variable identity.

Failure to write one binary dump sets `DumpWritten=false`, logs the filesystem status, and does not stop enumeration.

## 9. Filesystem failure policy

The application must successfully locate the filesystem associated with its loaded image and open the filesystem root before it can satisfy its purpose. Failure at that stage is a terminal application error reported on screen.

`vars.csv`, `vars.jsonl`, and `vars.log` are opened near application start. After enumeration begins, failure of one output sink disables that sink while enumeration and the remaining sinks continue. The final screen summary reports each sink as `Success` or `Failed`.

`\VarDumps` creation failure disables dumps but does not prevent CSV/JSONL/log inventory generation.

## 10. Screen output

Normal successful completion prints:

```text
Firmware Variable Tool - Inventory Mode
Enumerating variables...
Count: N
Readable: N
Unreadable: N
Dumps written: N
vars.csv: Success
vars.jsonl: Success
vars.log: Success
Done.
```

If a sink or enumeration infrastructure step fails, the same summary is printed with the affected result marked `Failed`, plus the relevant EFI status.

## 11. Counters

- `Count`: every variable successfully returned by `GetNextVariableName()`.
- `Readable`: variables whose final `GetVariable` status is `EFI_SUCCESS`.
- `Unreadable`: enumerated variables whose final `GetVariable` status is not `EFI_SUCCESS`, including allocation failures required to perform a read.
- `Dumps written`: successfully completed binary dump files only.

The invariant on normal enumeration completion is `Count == Readable + Unreadable`.

## 12. Read-only safety constraints

For this task:

- no `SetVariable()` calls;
- no patching;
- no variable restoration;
- no interactive editing;
- no delete operations against firmware variables;
- no hidden write-enable compile flag in `InventoryVarTool`;
- no linkage to the existing variable writer adapter unless the linked object can be statically proven not to expose or reference `SetVariable()`.

CI/build verification will include a static source/package check for `SetVariable` references in inventory-specific source and a binary import/string/symbol inspection where practical. The existing writer application is outside this check because it is a separate intentional artifact.

## 13. Host-side regression tests

Host tests are added before firmware implementation for:

1. CSV escaping:
   - plain value;
   - comma;
   - quote;
   - CR/LF;
   - escaped UTF-16 representation.
2. JSONL escaping:
   - quote;
   - backslash;
   - controls;
   - encoded UTF-16 units;
   - resulting line parses as one object.
3. Filename sanitization:
   - FAT-unsafe characters;
   - empty name;
   - non-printable UTF-16;
   - long-name truncation/suffix;
   - deterministic collision handling.
4. CRC32 calculation:
   - empty input;
   - standard `123456789 -> 0xCBF43926` vector.
5. Hex preview formatting:
   - zero bytes;
   - fewer than 32 bytes;
   - exactly 32 bytes;
   - more than 32 bytes truncates at 32.
6. EFI status-to-string mapping:
   - `EFI_SUCCESS`;
   - representative errors including `EFI_BUFFER_TOO_SMALL`, `EFI_NOT_FOUND`, `EFI_ACCESS_DENIED`, `EFI_SECURITY_VIOLATION` where available in the host shim;
   - unknown status fallback preserving numeric code.
7. Continuing enumeration after simulated read failure:
   - simulated variable A reads successfully;
   - variable B returns a read error;
   - variable C still gets processed;
   - final counters reflect all three records.

Existing host regression tests must remain green.

## 14. Build and provenance

The initial build target remains the known-good environment from successful Run #18:

- EDK II commit: `c5aa7e7d94c0e6b3c0202e15dbf7a5c92dd6a01d`
- Windows Server 2022 runner
- Visual Studio 2022 Enterprise toolchain
- X64 RELEASE
- NASM 2.16.03

Expected command target:

`InventoryVarTool.efi`

The CI artifact gate must produce and verify:

- `InventoryVarTool.efi`
- `build.log`
- SHA-256 of `InventoryVarTool.efi`
- exact EDK II commit and toolchain provenance in the log

The build does not pass unless the EFI binary exists, is non-empty, and is independently identified as an x86-64 PE32+ EFI application.

## 15. Out of scope

This feature does not:

- modify any firmware variable;
- interpret vendor-specific variable payloads;
- decode `AMD_PBS_SETUP` or other schemas;
- compare inventories across boots;
- restore dumps;
- expose an interactive browser/editor;
- compress dump files;
- add network output.

Those can be considered separately after the raw inventory capability is validated on the target firmware.
