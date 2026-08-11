# Inventory Supplemental Direct Reads Design

## Goal

Extend `InventoryVarTool.efi` so firmware variables that are directly readable by name/GUID but omitted by `GetNextVariableName()` are still captured as explicit supplemental inventory records, while preserving a strict read-only boundary.

## Scope

This change affects only `InventoryVarTool`. `ReadOnlyVarTool` and `WriteVarTool` behavior is unchanged. No `SetVariable`, patching, restore, or interactive edit capability is added.

## Supplemental targets

After normal `GetNextVariableName()` enumeration completes, attempt exact direct reads for each target that was not observed as the same exact name/GUID pair during enumeration:

- `AMD_PBS_SETUP` / `A339D746-F678-49B3-9FC7-54CE0F9DF226`
- `SystemConfig` / `A04A27F4-DF00-4D42-B552-39511302113D`
- `Custom` / `A04A27F4-DF00-4D42-B552-39511302113D`
- `D01SetupConfig` / `EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1`
- `D01Custom` / `EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1`

Do not collapse aliases. Each candidate is independently probed unless its exact name/GUID pair was already enumerated.

## Enumeration evidence

Track exact name/GUID pairs returned by `GetNextVariableName()`. This tracking is only used to suppress duplicate supplemental records. It must not alter enumeration order, retry behavior, or error continuation.

## Direct-read behavior

Supplemental reads call `GetVariable()` with the explicit target name and GUID rather than relying on the enumeration cursor. Use the same two-call sizing/read sequence as enumerated variables:

1. `GetVariable(..., Data=NULL)` to obtain attributes and required size.
2. On `EFI_BUFFER_TOO_SMALL`, allocate the exact size and call `GetVariable()` again.
3. Compute CRC32 and the first-32-byte preview when readable.
4. Attempt a full dump when readable and at or below the existing 64 KiB dump threshold.
5. Continue to later supplemental targets after read or dump failure.

## Record model

Every CSV/JSONL record includes the existing fields plus:

- `Source`: `enumerated` or `supplemental`
- `DumpAttempted`: boolean
- `DumpStatus`: symbolic EFI status string
- `DumpStatusCode`: numeric EFI status value

`DumpWritten` remains present.

Read failures must still emit records. Dump failures must still emit records with `DumpAttempted=true`, `DumpWritten=false`, and the exact dump status/code.

## Root reports

The following files are mandatory and are always created at the USB filesystem root:

- `\vars.csv`
- `\vars.jsonl`
- `\vars.log`

If any mandatory report cannot be opened/created, the tool must fail before enumeration begins rather than run without complete evidence. Failure to create `\VarDumps` is non-fatal; affected dump attempts are represented in the mandatory reports.

## Logging

`vars.log` records:

- all `GetNextVariableName()` statuses relevant to control flow,
- each enumerated variable read status,
- each supplemental direct-read status,
- dump attempt status when attempted,
- final counts including enumerated records, supplemental records, readable/unreadable records, dump attempts, dumps written, and dump failures,
- mandatory root-report open/create status.

## Safety

`InventoryVarTool` remains read-only:

- no `SetVariable` source reference,
- no `SetVariable` binary text/symbol reference,
- no writer-only modules in `InventoryVarTool.inf`,
- no `ENABLE_FIRMWARE_WRITES` define,
- existing source and binary safety gates remain mandatory.

## Tests

Add host-side regression coverage for:

1. exact name/GUID seen-set matching,
2. supplemental target suppression only when exact pair was enumerated,
3. missing supplemental target direct-read processing after enumeration,
4. supplemental read failure still emits a record and continues,
5. dump failure fields (`DumpAttempted`, `DumpStatus`, `DumpStatusCode`, `DumpWritten=false`),
6. CSV/JSONL serialization of `Source` and dump-status fields,
7. mandatory report-open failure aborts before enumeration,
8. existing seven inventory regressions remain green,
9. zero-`SetVariable` source/binary gates remain green.
