# Inventory Investigation Target Priority Update

## Status
Approved by the human owner on 2026-08-10.

## Objective
Keep InventoryVarTool strictly read-only while updating the post-enumeration missing-pair supplemental target priority for the next thermal-shutdown investigation pass.

## Investigation model
Live firmware evidence shows `AMD_PBS_SETUP` CPU CRT at offset `0x49` is `0x64` (100), not `0x46` (70). `AMD_PBS_SETUP` is retained only as a low-priority continuity target and is no longer the leading thermal suspect.

## Required supplemental exact Name+GUID order
After ordinary `GetNextVariableName()` enumeration, directly read only exact pairs not already observed, in this order:

1. `SioIt8669eSetup00` / `4AD60EB9-67F6-4DAF-AF67-995E909263CB`
2. `AmdSetup` / `3A997502-647A-4C82-998E-52EF9486A247`
3. `Setup` / `A04A27F4-DF00-4D42-B552-39511302113D`
4. `Custom` / `A04A27F4-DF00-4D42-B552-39511302113D`
5. `D01SetupConfig` / `EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1`
6. `D01Custom` / `EA4AEFC7-D0AC-48DE-A246-BE73D9C1EDC1`
7. `AMD_PBS_SETUP` / `A339D746-F678-49B3-9FC7-54CE0F9DF226` (continuity only)

`SystemConfig / A04A27F4-DF00-4D42-B552-39511302113D` is removed from the supplemental list because the live exact probe already returned `EFI_NOT_FOUND`.

## Invariants
- Normal enumeration always runs first.
- Exact Name+GUID matching determines whether a supplemental read is skipped.
- Read failure does not abort later targets.
- Existing source/status/dump-status reporting remains unchanged.
- `vars.csv`, `vars.jsonl`, and `vars.log` remain mandatory USB-root reports.
- Existing JSONL correction remains mandatory.
- No `SetVariable`, write-enable flag, patch operation, or writer source may be added.
- `WriteVarTool.efi` is not an investigation action; there is no approved write target.

## Acceptance
- Regression proves the exact seven target pairs and order.
- Regression proves obsolete `SystemConfig` is absent from the supplemental table.
- Existing host tests pass.
- X64 RELEASE VS2022/EDK II build passes.
- All three EFI artifacts are present.
- Inventory source and binary `SetVariable` scans remain zero.
- The rebuilt InventoryVarTool binary contains all seven target names.
