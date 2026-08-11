# Inventory Supplemental Direct Reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add missing-pair supplemental direct reads, explicit record provenance/dump status, and mandatory root reports to `InventoryVarTool.efi` without adding any firmware write capability.

**Architecture:** Preserve the current enumerator as the primary discovery pass. Record exact enumerated name/GUID pairs, then run a fixed supplemental target pass that calls `GetVariable()` by explicit key through a cursor-independent adapter path. Extend the record/sink contract so enumerated and supplemental outcomes, including read and dump failures, are machine-readable in all mandatory root reports.

**Tech Stack:** C11-compatible host core, EDK II UEFI application, `gRT->GetNextVariableName`, `gRT->GetVariable`, EDK II `BaseMemoryLib`, host CMake/CTest-style verification, GitHub Actions Windows Server 2022 + VS2022 X64 RELEASE.

## Global Constraints

- `InventoryVarTool` remains read-only; no `SetVariable` source or binary references.
- Existing `ReadOnlyVarTool` and `WriteVarTool` behavior is unchanged.
- Supplemental targets are exactly the five approved name/GUID pairs.
- Supplemental reads occur only for exact name/GUID pairs not observed during enumeration.
- `\vars.csv`, `\vars.jsonl`, and `\vars.log` are mandatory USB-root outputs.
- `\VarDumps` remains optional/non-fatal; dump failures must be recorded.
- Full binary dump threshold remains 64 KiB.
- Continue after individual enumeration read failures, supplemental read failures, and dump failures.
- Preserve the existing source and binary zero-`SetVariable` safety gates.

---

### Task 1: Extend inventory record provenance and dump-status model

**Files:**
- Modify: `UefiVarToolPkg/App/Core/InventoryEnumerator.h`
- Modify: `UefiVarToolPkg/App/Core/InventoryFormat.h`
- Modify: `UefiVarToolPkg/App/Core/InventoryFormat.c`
- Modify: `host/tests/test_inventory_format.c`

**Interfaces:**
- Consumes: existing inventory key/status/record model.
- Produces: record fields `Source`, `DumpAttempted`, `DumpStatus`, `DumpStatusCode`, while retaining `DumpWritten`.

- [ ] **Step 1: Write failing serialization tests**

Add tests that serialize an enumerated success record and a supplemental dump-failure record and assert that CSV and JSONL contain provenance and exact dump status fields.

Expected conceptual assertions:

```c
assert(strstr(csv, "enumerated") != NULL);
assert(strstr(csv, "supplemental") != NULL);
assert(strstr(json, "\"DumpAttempted\":true") != NULL);
assert(strstr(json, "\"DumpWritten\":false") != NULL);
assert(strstr(json, "\"DumpStatus\":\"EFI_DEVICE_ERROR\"") != NULL);
```

- [ ] **Step 2: Run host verification and confirm RED**

Run the repository host verification command. Expected: inventory-format tests fail because the new fields are absent.

- [ ] **Step 3: Add minimal model/serializer support**

Add a source enum/string contract with exactly:

```c
typedef enum {
    FW_INVENTORY_SOURCE_ENUMERATED = 0,
    FW_INVENTORY_SOURCE_SUPPLEMENTAL = 1
} FW_INVENTORY_SOURCE;
```

Extend the record with dump-attempt/status metadata and serialize it in CSV/JSONL. Preserve existing field names/semantics.

- [ ] **Step 4: Run host verification and confirm GREEN**

Expected: all existing tests plus new serialization tests pass.

- [ ] **Step 5: Commit**

```bash
git add UefiVarToolPkg/App/Core/InventoryEnumerator.h UefiVarToolPkg/App/Core/InventoryFormat.h UefiVarToolPkg/App/Core/InventoryFormat.c host/tests/test_inventory_format.c
git commit -m "feat: expose inventory source and dump status"
```

---

### Task 2: Track exact enumerated name/GUID pairs and select missing supplemental targets

**Files:**
- Modify: `UefiVarToolPkg/App/Core/InventoryEnumerator.h`
- Modify: `UefiVarToolPkg/App/Core/InventoryEnumerator.c`
- Modify: `host/tests/test_inventory_enumerator.c`

**Interfaces:**
- Consumes: `FW_INVENTORY_KEY` values returned by enumeration.
- Produces: exact-pair seen tracking and a deterministic missing-target decision.

- [ ] **Step 1: Write failing seen-set tests**

Cover:

```text
AMD_PBS_SETUP + AMD GUID seen => supplemental AMD_PBS_SETUP skipped
AMD_PBS_SETUP + different GUID seen => approved AMD target still missing
SystemConfig seen => Custom alias still missing
read failure after enumeration still counts pair as enumerated
```

- [ ] **Step 2: Run host verification and confirm RED**

Expected: failure because exact-pair seen tracking/missing-target selection does not exist.

- [ ] **Step 3: Implement bounded exact-pair tracking**

Track the five approved supplemental targets with booleans rather than accumulating every firmware variable in memory. On every successful `GetNextVariableName()` result, compare the enumerated key against those five exact pairs and mark matching candidates seen before attempting the variable read.

Expose a helper usable by host tests, for example:

```c
void FwInventoryMarkSupplementalTargetSeen(
    FW_SUPPLEMENTAL_SEEN_SET* Seen,
    const FW_INVENTORY_KEY* Key);

int FwInventorySupplementalTargetWasSeen(
    const FW_SUPPLEMENTAL_SEEN_SET* Seen,
    size_t TargetIndex);
```

- [ ] **Step 4: Run host verification and confirm GREEN**

Expected: exact-pair tests and existing continuation regression all pass.

- [ ] **Step 5: Commit**

```bash
git add UefiVarToolPkg/App/Core/InventoryEnumerator.h UefiVarToolPkg/App/Core/InventoryEnumerator.c host/tests/test_inventory_enumerator.c
git commit -m "feat: track supplemental inventory targets"
```

---

### Task 3: Add cursor-independent exact GetVariable reads and supplemental pass

**Files:**
- Modify: `UefiVarToolPkg/App/InventoryUefiAdapter.h`
- Modify: `UefiVarToolPkg/App/InventoryUefiAdapter.c`
- Modify: `UefiVarToolPkg/App/InventoryVarTool.c`
- Modify: `host/tests/test_inventory_enumerator.c`

**Interfaces:**
- Consumes: exact `FW_INVENTORY_KEY` for one supplemental target.
- Produces: read status/attributes/data size/data buffer independent of `GetNextVariableName` cursor.

- [ ] **Step 1: Write failing supplemental-continuation test**

Simulate enumeration followed by missing supplemental targets where the first supplemental direct read fails and a later target succeeds. Assert both records are emitted and processing continues.

- [ ] **Step 2: Run host verification and confirm RED**

Expected: failure because no post-enumeration supplemental pass exists.

- [ ] **Step 3: Implement explicit-key UEFI read helper**

Add a helper that converts the portable key into the exact `CHAR16*` name and `EFI_GUID` target and performs the two-call `GetVariable()` sequence directly. Do not consult the enumeration cursor.

- [ ] **Step 4: Run five-target supplemental pass after enumeration**

Define the approved targets in deterministic order:

```text
AMD_PBS_SETUP / A339D746-F678-49B3-9FC7-54CE0F9DF226
SystemConfig  / A04A27F4-DF00-4D42-B552-39511302113D
Custom        / A04A27F4-DF00-4D42-B552-39511302113D
D01SetupConfig/ EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1
D01Custom     / EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1
```

For each not-seen pair, emit a `Source=supplemental` record regardless of read success. Continue after errors.

- [ ] **Step 5: Run host verification and confirm GREEN**

Expected: supplemental continuation regression and all previous inventory tests pass.

- [ ] **Step 6: Commit**

```bash
git add UefiVarToolPkg/App/InventoryUefiAdapter.h UefiVarToolPkg/App/InventoryUefiAdapter.c UefiVarToolPkg/App/InventoryVarTool.c host/tests/test_inventory_enumerator.c
git commit -m "feat: directly read missing firmware targets"
```

---

### Task 4: Make root reports mandatory and record dump failures

**Files:**
- Modify: `UefiVarToolPkg/App/InventoryFileSink.h`
- Modify: `UefiVarToolPkg/App/InventoryFileSink.c`
- Modify: `UefiVarToolPkg/App/InventoryVarTool.c`
- Add/modify host-side sink policy tests as supported by the existing host harness.

**Interfaces:**
- Consumes: inventory records and optional dump data.
- Produces: mandatory `\vars.csv`, `\vars.jsonl`, `\vars.log`; explicit dump status for every attempted dump.

- [ ] **Step 1: Write failing policy tests**

Test that mandatory report-open failure prevents enumeration start, while `VarDumps` directory/write failure does not abort record emission and produces:

```text
DumpAttempted=true
DumpWritten=false
DumpStatus=<exact status>
DumpStatusCode=<exact numeric status>
```

- [ ] **Step 2: Run host verification and confirm RED**

- [ ] **Step 3: Enforce mandatory report creation**

Open/create all three root reports before enumeration. If any fails, close already-open handles, print/log the exact failure possible on screen, and return failure without calling enumeration.

- [ ] **Step 4: Return exact dump attempt status to the record emitter**

A dump at or below 64 KiB sets `DumpAttempted=true`; directory/create/write/flush failure sets the exact EFI status and leaves `DumpWritten=false`. Oversize or unreadable variables use `DumpAttempted=false` with a non-error neutral dump status.

- [ ] **Step 5: Run host verification and confirm GREEN**

- [ ] **Step 6: Commit**

```bash
git add UefiVarToolPkg/App/InventoryFileSink.h UefiVarToolPkg/App/InventoryFileSink.c UefiVarToolPkg/App/InventoryVarTool.c host/tests
git commit -m "feat: require inventory reports and expose dump failures"
```

---

### Task 5: Safety, source overlay, and pinned EDK II build

**Files:**
- Modify: versioned inventory feature overlay/payload files under `ci/` or add a new SHA-verified follow-on feature patch.
- Modify: `.github/workflows/build-edk2-vs2022.yml` only as required to materialize the approved source revision and preserve the mandatory inventory acceptance contract.

**Interfaces:**
- Consumes: tested inventory source changes.
- Produces: new `InventoryVarTool.efi`, build log, hashes, unchanged read-only safety evidence.

- [ ] **Step 1: Run complete host regression suite**

Expected: all old and new tests pass with zero failures.

- [ ] **Step 2: Run static source safety gate**

Expected: zero `SetVariable` references in inventory source; forbidden writer modules/defines absent from `InventoryVarTool.inf`.

- [ ] **Step 3: Regenerate or layer the inventory source patch deterministically**

Verify it applies cleanly to reviewed source SHA-256:

```text
6d55b8a8afa0a1808379b62c6712bc8b0170b6225a7dd073822e0a38c38442c1
```

Preserve the existing proven `BuildDumpFileName -> CopyMem` EDK II compatibility fix.

- [ ] **Step 4: Trigger pinned build**

Build with:

```text
EDK II c5aa7e7d94c0e6b3c0202e15dbf7a5c92dd6a01d
Windows Server 2022
VS2022
X64 RELEASE
NASM 2.16.03
build -a X64 -b RELEASE -t VS2022 -p UefiVarToolPkg\UefiVarToolPkg.dsc
```

- [ ] **Step 5: Verify mandatory artifact contract**

Require non-empty valid AMD64 EFI applications:

```text
ReadOnlyVarTool.efi
WriteVarTool.efi
InventoryVarTool.efi
```

- [ ] **Step 6: Run independent InventoryVarTool binary safety scan**

Scan ASCII and UTF-16LE binary strings for `SetVariable`; expected total matches: `0`.

- [ ] **Step 7: Independently inspect final artifact**

Recompute SHA-256, validate PE32+ EFI x86-64 identity, confirm `InventoryVarTool` appears in the build log, and inspect the acceptance manifest before delivery.
