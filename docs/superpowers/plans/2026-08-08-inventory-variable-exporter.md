# Firmware Variable Inventory Exporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `InventoryVarTool.efi`, a strictly read-only UEFI variable inventory exporter that enumerates runtime variables, records machine-parseable metadata/data summaries, optionally dumps readable variables up to 64 KiB, and continues after per-variable read failures.

**Architecture:** Add a third UEFI application with a portable inventory core and UEFI-only runtime/filesystem adapters. The portable core owns formatting, status rendering, dump-name sanitization, counters, and continuation policy; the UEFI layer owns `GetNextVariableName()`, `GetVariable()`, allocation, filesystem handles, and screen output. Existing ReadOnly/Write behavior remains unchanged.

**Tech Stack:** C17 host tests with CMake/CTest; EDK II UEFI application; `EFI_RUNTIME_SERVICES`; `EFI_SIMPLE_FILE_SYSTEM_PROTOCOL`; Visual Studio 2022 X64 RELEASE; NASM 2.16.03.

## Global Constraints

- No `SetVariable()` calls or firmware mutation path in `InventoryVarTool`.
- No patching, restore, delete-variable behavior, or interactive edit mode.
- Enumerate with `GetNextVariableName()` starting from empty name + zero GUID.
- Start with 1024 `CHAR16` name capacity and grow on `EFI_BUFFER_TOO_SMALL`.
- Per-variable `GetVariable()` failures must never abort enumeration.
- Full dump threshold is exactly 65536 bytes.
- Required USB outputs: `\\vars.csv`, `\\vars.jsonl`, `\\vars.log`, optional `\\VarDumps\\...`.
- Build target remains EDK II commit `c5aa7e7d94c0e6b3c0202e15dbf7a5c92dd6a01d`, Windows Server 2022, VS2022, X64 RELEASE, NASM 2.16.03.
- Existing host tests must remain green.

---

## File Structure

**Create:**
- `UefiVarToolPkg/App/Core/InventoryFormat.h` — portable inventory record/status/escaping interfaces.
- `UefiVarToolPkg/App/Core/InventoryFormat.c` — CSV/JSONL escaping, UTF-16 logical-name encoding, EFI status mapping, preview formatting, dump-name sanitization.
- `UefiVarToolPkg/App/Core/InventoryEnumerator.h` — portable callback contracts and summary counters.
- `UefiVarToolPkg/App/Core/InventoryEnumerator.c` — continuation-safe enumeration driver.
- `UefiVarToolPkg/App/InventoryUefiAdapter.h` — UEFI callback/context definitions.
- `UefiVarToolPkg/App/InventoryUefiAdapter.c` — `GetNextVariableName()`/`GetVariable()` adapter and dynamic name/data allocation.
- `UefiVarToolPkg/App/InventoryFileSink.h` — streaming CSV/JSONL/log/dump interface.
- `UefiVarToolPkg/App/InventoryFileSink.c` — USB filesystem root discovery, file creation, stream writes, dump writes.
- `UefiVarToolPkg/App/InventoryVarTool.c` — application entry point, sink setup, orchestration, summary screen output.
- `UefiVarToolPkg/InventoryVarTool.inf` — strictly read-only application module manifest.
- `host/tests/test_inventory_format.c` — CSV, JSONL, filename, status, preview tests.
- `host/tests/test_inventory_enumerator.c` — simulated A-success/B-fail/C-success continuation test.

**Modify:**
- `UefiVarToolPkg/App/Core/FwCompat.h` — add portable `uint64_t` alias required for X64 EFI status values.
- `UefiVarToolPkg/UefiVarToolPkg.dsc` — add the new component while retaining known-good library mappings.
- `host/CMakeLists.txt` — compile the two new portable core files and register two new tests.
- `host/verify.sh` — add inventory-specific static read-only checks.
- `.github/workflows/build-edk2-vs2022.yml` — consume the new reviewed source archive, build/stage/hash `InventoryVarTool.efi`, and preserve exact provenance.
- `ci/source.part00.b64` ... `ci/source.part04.b64` — regenerate from the new reviewed source archive after tests pass.

---

### Task 1: Portable Inventory Formatting Core

**Files:**
- Create: `UefiVarToolPkg/App/Core/InventoryFormat.h`
- Create: `UefiVarToolPkg/App/Core/InventoryFormat.c`
- Modify: `UefiVarToolPkg/App/Core/FwCompat.h`
- Create: `host/tests/test_inventory_format.c`
- Modify: `host/CMakeLists.txt`

**Interfaces:**
- Produces:
  - `const char* FwInventoryStatusName(uint64_t status);`
  - `size_t FwInventoryEncodeName(const uint16_t* name, size_t units, char* out, size_t outSize);`
  - `size_t FwInventoryCsvEscape(const char* text, char* out, size_t outSize);`
  - `size_t FwInventoryJsonEscape(const char* text, char* out, size_t outSize);`
  - `size_t FwInventoryHexPreview(const uint8_t* data, size_t size, char* out, size_t outSize);`
  - `size_t FwInventorySanitizeDumpName(const uint16_t* name, size_t units, char* out, size_t outSize);`
  - portable constants for `EFI_SUCCESS`, `EFI_BUFFER_TOO_SMALL`, `EFI_NOT_FOUND`, `EFI_ACCESS_DENIED`, `EFI_SECURITY_VIOLATION` using their X64 numeric values.

- [ ] **Step 1: Add failing formatting tests**

Create `host/tests/test_inventory_format.c` with assertions equivalent to:

```c
static void test_csv_escape(void) {
    char out[128];
    assert(FwInventoryCsvEscape("plain", out, sizeof(out)) > 0u);
    assert(strcmp(out, "plain") == 0);
    assert(FwInventoryCsvEscape("a,b", out, sizeof(out)) > 0u);
    assert(strcmp(out, "\"a,b\"") == 0);
    assert(FwInventoryCsvEscape("a\"b", out, sizeof(out)) > 0u);
    assert(strcmp(out, "\"a\"\"b\"") == 0);
    assert(FwInventoryCsvEscape("a\r\nb", out, sizeof(out)) > 0u);
    assert(strcmp(out, "\"a\r\nb\"") == 0);
}

static void test_json_escape(void) {
    char out[128];
    assert(FwInventoryJsonEscape("a\"b\\c\n", out, sizeof(out)) > 0u);
    assert(strcmp(out, "a\\\"b\\\\c\\n") == 0);
}

static void test_status_mapping(void) {
    assert(strcmp(FwInventoryStatusName(FW_EFI_SUCCESS), "EFI_SUCCESS") == 0);
    assert(strcmp(FwInventoryStatusName(FW_EFI_BUFFER_TOO_SMALL), "EFI_BUFFER_TOO_SMALL") == 0);
    assert(strcmp(FwInventoryStatusName(FW_EFI_NOT_FOUND), "EFI_NOT_FOUND") == 0);
    assert(strcmp(FwInventoryStatusName(FW_EFI_ACCESS_DENIED), "EFI_ACCESS_DENIED") == 0);
    assert(strcmp(FwInventoryStatusName(FW_EFI_SECURITY_VIOLATION), "EFI_SECURITY_VIOLATION") == 0);
    assert(strcmp(FwInventoryStatusName(UINT64_C(0x80000000DEADBEEF)), "EFI_STATUS_UNKNOWN") == 0);
}

static void test_preview(void) {
    uint8_t bytes[40];
    for (size_t i = 0; i < 40u; ++i) bytes[i] = (uint8_t)i;
    char out[65];
    assert(FwInventoryHexPreview(bytes, 40u, out, sizeof(out)) == 64u);
    assert(strcmp(out, "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F") == 0);
}
```

Also test:
- zero-byte preview => empty string;
- fewer than 32 bytes;
- exactly 32 bytes;
- UTF-16 non-ASCII encoding such as `{ 'A', 0x263A } -> "A\\u263A"`;
- empty dump name -> `utf16hex_empty`;
- unsafe names such as `A:B` and `A?B` produce FAT-safe, deterministic, distinct outputs;
- long names are truncated with deterministic CRC32 suffix.

- [ ] **Step 2: Register the test and verify RED**

Modify `host/CMakeLists.txt`:

```cmake
add_fwtool_test(test_inventory_format tests/test_inventory_format.c)
```

Run:

```bash
./host/verify.sh
```

Expected: compile failure because `InventoryFormat.h` / functions do not yet exist.

- [ ] **Step 3: Add `uint64_t` portability support**

Modify `FwCompat.h`:

```c
#ifdef FW_UEFI_BUILD
#include <Base.h>
typedef UINTN size_t;
typedef UINT8 uint8_t;
typedef UINT16 uint16_t;
typedef UINT32 uint32_t;
typedef UINT64 uint64_t;
#else
#include <stddef.h>
#include <stdint.h>
#endif
```

- [ ] **Step 4: Implement minimal formatting core**

`InventoryFormat.h` must define the exact function signatures above and X64 status constants. `InventoryFormat.c` must:
- avoid libc outside the host-compat boundary;
- use bounded character emit helpers;
- RFC-4180 quote CSV only when comma/quote/CR/LF exists;
- JSON-escape quote/backslash/control bytes;
- encode non-printable/non-ASCII UTF-16 units as literal `\\uXXXX` in logical names;
- render at most 32 bytes in uppercase hex without separators;
- sanitize FAT names deterministically and add CRC suffix when sanitization/truncation could collide.

- [ ] **Step 5: Run formatting tests to GREEN**

Run:

```bash
./host/verify.sh
```

Expected: original 5 tests + `test_inventory_format` all PASS.

- [ ] **Step 6: Commit**

```bash
git add UefiVarToolPkg/App/Core/FwCompat.h \
        UefiVarToolPkg/App/Core/InventoryFormat.[ch] \
        host/CMakeLists.txt host/tests/test_inventory_format.c
git commit -m "feat: add portable inventory formatting core"
```

---

### Task 2: Continuation-Safe Portable Enumeration Driver

**Files:**
- Create: `UefiVarToolPkg/App/Core/InventoryEnumerator.h`
- Create: `UefiVarToolPkg/App/Core/InventoryEnumerator.c`
- Create: `host/tests/test_inventory_enumerator.c`
- Modify: `host/CMakeLists.txt`

**Interfaces:**

```c
typedef struct {
    const uint16_t* Name;
    size_t NameUnits;
    uint8_t VendorGuid[16];
} FW_INVENTORY_KEY;

typedef struct {
    uint32_t Attributes;
    size_t DataSize;
    uint64_t Status;
    const uint8_t* Data;
} FW_INVENTORY_READ_RESULT;

typedef struct {
    size_t Count;
    size_t Readable;
    size_t Unreadable;
    uint64_t EnumerationStatus;
} FW_INVENTORY_SUMMARY;

typedef uint64_t (*FW_INVENTORY_NEXT_FN)(void* context, FW_INVENTORY_KEY* key);
typedef uint64_t (*FW_INVENTORY_READ_FN)(void* context, const FW_INVENTORY_KEY* key, FW_INVENTORY_READ_RESULT* result);
typedef void (*FW_INVENTORY_EMIT_FN)(void* context, const FW_INVENTORY_KEY* key, const FW_INVENTORY_READ_RESULT* result);
typedef void (*FW_INVENTORY_RELEASE_FN)(void* context, FW_INVENTORY_READ_RESULT* result);

uint64_t FwInventoryEnumerate(
    void* context,
    FW_INVENTORY_NEXT_FN nextFn,
    FW_INVENTORY_READ_FN readFn,
    FW_INVENTORY_EMIT_FN emitFn,
    FW_INVENTORY_RELEASE_FN releaseFn,
    FW_INVENTORY_SUMMARY* summary
);
```

- [ ] **Step 1: Write the failing continuation regression**

Create a fake sequence A/B/C where:
- `nextFn` returns A, B, C, then `FW_EFI_NOT_FOUND`;
- A read returns success;
- B read returns `FW_EFI_ACCESS_DENIED`;
- C read returns success;
- `emitFn` records every key observed.

Assertions:

```c
assert(summary.Count == 3u);
assert(summary.Readable == 2u);
assert(summary.Unreadable == 1u);
assert(summary.EnumerationStatus == FW_EFI_NOT_FOUND);
assert(fake.Emitted == 3u);
assert(fake.EmittedNames[0] == 'A');
assert(fake.EmittedNames[1] == 'B');
assert(fake.EmittedNames[2] == 'C');
```

- [ ] **Step 2: Register test and verify RED**

Add both portable sources to `fwtool_core` and register:

```cmake
add_fwtool_test(test_inventory_enumerator tests/test_inventory_enumerator.c)
```

Run `./host/verify.sh` and confirm failure before implementation.

- [ ] **Step 3: Implement the enumeration loop**

Required loop semantics:

```c
for (;;) {
    FW_INVENTORY_KEY key;
    uint64_t nextStatus = nextFn(context, &key);
    if (nextStatus == FW_EFI_NOT_FOUND) {
        summary->EnumerationStatus = nextStatus;
        return FW_EFI_SUCCESS;
    }
    if (nextStatus != FW_EFI_SUCCESS) {
        summary->EnumerationStatus = nextStatus;
        return nextStatus;
    }

    summary->Count += 1u;

    FW_INVENTORY_READ_RESULT result = {0};
    result.Status = readFn(context, &key, &result);
    if (result.Status == FW_EFI_SUCCESS) summary->Readable += 1u;
    else summary->Unreadable += 1u;

    emitFn(context, &key, &result);
    if (releaseFn != 0) releaseFn(context, &result);
}
```

Validate required callback pointers and initialize summary deterministically.

- [ ] **Step 4: Run all host tests to GREEN**

Run `./host/verify.sh`.

Expected: 7 host test executables PASS.

- [ ] **Step 5: Commit**

```bash
git add UefiVarToolPkg/App/Core/InventoryEnumerator.[ch] \
        host/CMakeLists.txt host/tests/test_inventory_enumerator.c
git commit -m "feat: add continuation-safe inventory enumerator"
```

---

### Task 3: UEFI Runtime Adapter, Streaming File Sinks, and Application Entry Point

**Files:**
- Create: `UefiVarToolPkg/App/InventoryUefiAdapter.h`
- Create: `UefiVarToolPkg/App/InventoryUefiAdapter.c`
- Create: `UefiVarToolPkg/App/InventoryFileSink.h`
- Create: `UefiVarToolPkg/App/InventoryFileSink.c`
- Create: `UefiVarToolPkg/App/InventoryVarTool.c`

**Interfaces:**

`InventoryUefiAdapter.h`:

```c
typedef struct {
    CHAR16* CursorName;
    UINTN CursorCapacityBytes;
    EFI_GUID CursorGuid;
} INVENTORY_UEFI_CURSOR;

EFI_STATUS InventoryUefiInit(INVENTORY_UEFI_CURSOR* cursor);
VOID InventoryUefiFree(INVENTORY_UEFI_CURSOR* cursor);
uint64_t InventoryUefiNext(void* context, FW_INVENTORY_KEY* key);
uint64_t InventoryUefiRead(void* context, const FW_INVENTORY_KEY* key, FW_INVENTORY_READ_RESULT* result);
void InventoryUefiRelease(void* context, FW_INVENTORY_READ_RESULT* result);
```

`InventoryFileSink.h` must expose open/write/close operations for CSV, JSONL, log, and dumps using persistent EFI file handles rather than reopening root for every record.

- [ ] **Step 1: Implement `GetNextVariableName()` adapter exactly**

Behavior:
1. Allocate 1024 `CHAR16` units (`2048` bytes) for the cursor.
2. Initialize name to empty and GUID to zero.
3. Before each runtime call, preserve current cursor name/GUID.
4. Call `gRT->GetNextVariableName(&nameBytes, nameBuffer, &guid)`.
5. On `EFI_BUFFER_TOO_SMALL`, allocate at least returned byte size, restore cursor, retry.
6. On success, update cursor to returned name/GUID and expose a temporary `FW_INVENTORY_KEY` valid until next call.
7. On `EFI_NOT_FOUND`, return termination status.
8. On any other status, return it without guessing the next cursor.

No call to `SetVariable` is permitted in this file.

- [ ] **Step 2: Implement two-stage `GetVariable()` adapter**

Pseudo-code:

```c
UINTN size = 0;
UINT32 attributes = 0;
EFI_STATUS status = gRT->GetVariable(name, guid, &attributes, &size, NULL);

if (status == EFI_SUCCESS && size == 0) {
    result->Status = EFI_SUCCESS;
    result->Attributes = attributes;
    result->DataSize = 0;
    result->Data = NULL;
    return EFI_SUCCESS;
}

if (status != EFI_BUFFER_TOO_SMALL) {
    result->Status = status;
    result->Attributes = attributes;
    result->DataSize = size;
    return status;
}

VOID* data = AllocatePool(size);
if (data == NULL) {
    result->Status = EFI_OUT_OF_RESOURCES;
    result->Attributes = attributes;
    result->DataSize = size;
    return EFI_OUT_OF_RESOURCES;
}

status = gRT->GetVariable(name, guid, &attributes, &size, data);
```

Return final status and release allocated data only through `InventoryUefiRelease()`.

- [ ] **Step 3: Implement persistent output sinks**

`InventoryFileSink.c` must:
- locate the filesystem from `gImageHandle` through `gEfiLoadedImageProtocolGuid` and `gEfiSimpleFileSystemProtocolGuid`;
- open root once;
- recreate `vars.csv`, `vars.jsonl`, `vars.log`;
- create/open `VarDumps` directory once;
- expose bounded append writes and `Flush()` on final close;
- disable only the failed sink after a write error;
- permit dump failure without disabling CSV/JSONL/log.

Filesystem deletion/recreation applies only to USB files, never firmware variables.

- [ ] **Step 4: Implement record emission**

For each readable variable:
- CRC32 over full data using `FwCrc32`;
- preview using `FwInventoryHexPreview`;
- dump only if `DataSize <= 65536`;
- derive dump filename from canonical GUID + sanitized logical name;
- set `DumpWritten=true` only after full write succeeds.

For unreadable variables:
- CRC32 empty/null;
- preview empty/null;
- dump false.

CSV header must be exactly:

```text
VariableName,VendorGuid,Attributes,DataSize,GetVariableStatus,GetVariableStatusCode,CRC32,HexPreview32,DumpWritten
```

JSONL must emit one object per line with the same field names.

- [ ] **Step 5: Implement screen summary**

`InventoryVarTool.c` prints:

```text
Firmware Variable Tool - Inventory Mode
Enumerating variables...
Count: N
Readable: N
Unreadable: N
Dumps written: N
vars.csv: Success|Failed
vars.jsonl: Success|Failed
vars.log: Success|Failed
Done.
```

Use `FwInventoryEnumerate()` with the UEFI callbacks. Per-variable read errors are emitted and enumeration continues.

- [ ] **Step 6: Compile strict host-portable sources**

Run:

```bash
./host/verify.sh
```

Expected: all portable tests PASS; UEFI-only files are not part of host compilation.

- [ ] **Step 7: Commit**

```bash
git add UefiVarToolPkg/App/Inventory*.c UefiVarToolPkg/App/Inventory*.h
git commit -m "feat: add read-only UEFI inventory application"
```

---

### Task 4: EDK II Module Integration and Static Read-Only Gates

**Files:**
- Create: `UefiVarToolPkg/InventoryVarTool.inf`
- Modify: `UefiVarToolPkg/UefiVarToolPkg.dsc`
- Modify: `host/verify.sh`

**Interfaces:**
- Produces EDK II module `InventoryVarTool` with entry point `InventoryVarToolMain`.

- [ ] **Step 1: Create strictly read-only INF**

Required structure:

```ini
[Defines]
  INF_VERSION    = 0x00010005
  BASE_NAME      = InventoryVarTool
  FILE_GUID      = <new unique GUID>
  MODULE_TYPE    = UEFI_APPLICATION
  VERSION_STRING = 0.1
  ENTRY_POINT    = InventoryVarToolMain

[Sources]
  App/InventoryVarTool.c
  App/InventoryUefiAdapter.c
  App/InventoryFileSink.c
  App/Core/InventoryEnumerator.c
  App/Core/InventoryFormat.c
  App/Core/Crc32.c

[Packages]
  MdePkg/MdePkg.dec
  UefiVarToolPkg/UefiVarToolPkg.dec

[LibraryClasses]
  UefiApplicationEntryPoint
  UefiLib
  UefiBootServicesTableLib
  UefiRuntimeServicesTableLib
  MemoryAllocationLib
  BaseMemoryLib
  BaseLib
  PrintLib

[Protocols]
  gEfiLoadedImageProtocolGuid
  gEfiSimpleFileSystemProtocolGuid

[BuildOptions]
  MSFT:*_*_*_CC_FLAGS = /DFW_UEFI_BUILD=1
  GCC:*_*_*_CC_FLAGS  = -DFW_UEFI_BUILD=1
```

There must be no `ENABLE_FIRMWARE_WRITES` define.

- [ ] **Step 2: Add component and preserve known-good DSC mappings**

The DSC must contain the successful Run #18 dependency mappings:

```ini
DevicePathLib|MdePkg/Library/UefiDevicePathLib/UefiDevicePathLib.inf
RegisterFilterLib|MdePkg/Library/RegisterFilterLibNull/RegisterFilterLibNull.inf
CpuLib|MdePkg/Library/BaseCpuLib/BaseCpuLib.inf
PcdLib|MdePkg/Library/BasePcdLibNull/BasePcdLibNull.inf
StackCheckLib|MdePkg/Library/StackCheckLibNull/StackCheckLibNull.inf
```

and:

```ini
[Components]
  UefiVarToolPkg/ReadOnlyVarTool.inf
  UefiVarToolPkg/WriteVarTool.inf
  UefiVarToolPkg/InventoryVarTool.inf
```

- [ ] **Step 3: Add static inventory safety checks**

Extend `host/verify.sh` so Python verifies:

```python
inventory_files = [
    root/'UefiVarToolPkg/App/InventoryVarTool.c',
    root/'UefiVarToolPkg/App/InventoryUefiAdapter.c',
    root/'UefiVarToolPkg/App/InventoryFileSink.c',
    root/'UefiVarToolPkg/App/Core/InventoryEnumerator.c',
    root/'UefiVarToolPkg/App/Core/InventoryFormat.c',
]
for path in inventory_files:
    text = path.read_text()
    if 'SetVariable' in text:
        raise SystemExit(f'FAIL: inventory source references SetVariable: {path}')

inf = (root/'UefiVarToolPkg/InventoryVarTool.inf').read_text()
if 'ENABLE_FIRMWARE_WRITES' in inf:
    raise SystemExit('FAIL: InventoryVarTool enables firmware writes')
if 'UefiRuntimeAdapter.c' in inf or 'PatchModel.c' in inf or 'PatchFile.c' in inf:
    raise SystemExit('FAIL: InventoryVarTool links write/patch implementation')
```

Also assert `InventoryVarTool.inf` is present in the DSC.

- [ ] **Step 4: Run full host/static gate**

Run `./host/verify.sh`.

Expected: 7 tests PASS and both existing + new static safety checks PASS.

- [ ] **Step 5: Commit**

```bash
git add UefiVarToolPkg/InventoryVarTool.inf \
        UefiVarToolPkg/UefiVarToolPkg.dsc host/verify.sh
git commit -m "build: integrate read-only inventory EFI module"
```

---

### Task 5: Produce New Reviewed Source Archive and Update CI

**Files:**
- Modify: `ci/source.part00.b64` ... `ci/source.part04.b64`
- Modify: `.github/workflows/build-edk2-vs2022.yml`

**Interfaces:**
- Produces deterministic reviewed source ZIP SHA consumed by CI.

- [ ] **Step 1: Run all local verification before packaging**

Run:

```bash
./host/verify.sh
git diff --check
```

Expected: all tests/static gates PASS; no whitespace errors.

- [ ] **Step 2: Build deterministic source archive**

Create a ZIP rooted at `FirmwareVariableTool/` containing source/docs/host tests but excluding `.git` and build outputs. Compute:

```bash
sha256sum FirmwareVariableTool-source.zip
```

Record the new SHA-256 in the workflow as `SOURCE_SHA256`.

- [ ] **Step 3: Regenerate exactly five base64 source parts**

Encode the archive, split into five ordered `ci/source.partNN.b64` files, and verify concatenation decodes byte-identically to the ZIP.

Required verification:

```bash
cat ci/source.part*.b64 | base64 -d > reconstructed.zip
cmp FirmwareVariableTool-source.zip reconstructed.zip
sha256sum reconstructed.zip
```

- [ ] **Step 4: Simplify source preparation to use integrated source fixes**

Because the new reviewed archive contains the Run #18 build-required DSC/INF/BaseMemory fixes directly, remove CI-time source mutation blocks for those historical fixes. CI must reconstruct, hash-check, extract, then copy `UefiVarToolPkg` unchanged into EDK II.

- [ ] **Step 5: Extend artifact gate for InventoryVarTool**

The workflow must verify:

```powershell
$inventory = Join-Path $out 'InventoryVarTool.efi'
if (-not (Test-Path $inventory)) { throw "Missing artifact: $inventory" }
if ((Get-Item $inventory).Length -le 0) { throw 'InventoryVarTool.efi is empty' }
Copy-Item $inventory 'efi-artifacts/InventoryVarTool.efi'
Get-FileHash 'efi-artifacts/InventoryVarTool.efi' -Algorithm SHA256 |
  Format-Table -AutoSize | Out-String | Add-Content 'efi-artifacts/build.log'
```

Keep ReadOnly/Write artifact verification too, as regression coverage.

- [ ] **Step 6: Add binary read-only sanity inspection where practical**

After build, inspect `InventoryVarTool.efi` with available Windows tooling for PE/COFF identity and scan printable strings/symbol output for `SetVariable`. Fail if an inventory-specific `SetVariable` reference is found. Do not apply this check to `WriteVarTool.efi`.

- [ ] **Step 7: Commit**

```bash
git add ci/source.part*.b64 .github/workflows/build-edk2-vs2022.yml
git commit -m "ci: build and verify inventory EFI artifact"
```

---

### Task 6: Pinned Windows Build and Delivery Verification

**Files:**
- No source changes unless the real build exposes a concrete compiler/linker defect.

- [ ] **Step 1: Trigger feature-branch PR build**

Open/reuse a draft PR targeting `main` so the `pull_request` workflow runs against the pinned Windows environment.

- [ ] **Step 2: Require all build stages to pass**

Confirm:
- source SHA verification PASS;
- VS2022 detection PASS;
- NASM 2.16.03 PASS;
- pinned EDK II checkout PASS;
- `build -a X64 -b RELEASE -t VS2022 -p UefiVarToolPkg\\UefiVarToolPkg.dsc` PASS;
- artifact verification PASS;
- EFI upload PASS.

- [ ] **Step 3: If build fails, fix only the first concrete error**

Download `FirmwareVariableTool-build-log`, extract the first real EDK II error, make the minimum source/build correction justified by that error, rerun host tests, and retrigger. Do not add speculative libraries or firmware behavior changes.

- [ ] **Step 4: Download and independently verify artifacts**

Download `FirmwareVariableTool-efi` and diagnostics. Verify locally:

```bash
file InventoryVarTool.efi
sha256sum InventoryVarTool.efi
```

Expected `file` classification: PE32+ executable for EFI (application), x86-64.

Also verify:
- non-zero size;
- local SHA-256 equals workflow-recorded SHA-256;
- build log records exact EDK II commit/toolchain;
- `InventoryVarTool.efi` contains no obvious `SetVariable` string/symbol reference.

- [ ] **Step 5: Deliver required artifacts**

Return:
- `InventoryVarTool.efi`;
- `build.log`;
- SHA-256;
- exact EDK II commit;
- Windows/VS/MSVC/NASM provenance;
- host regression count/results;
- concise statement that inventory-specific static/binary checks found no write path.

- [ ] **Step 6: Field-use boundary**

State that `InventoryVarTool.efi` is the next field executable and produces `vars.csv`, `vars.jsonl`, `vars.log`, and optional `VarDumps`; do not instruct use of `WriteVarTool.efi` as part of this task.
