# Inventory Investigation Target Priority Implementation Plan

**Goal:** Update only the read-only supplemental target table/order for the next field inventory pass while preserving accepted enumeration, reporting, JSONL, and safety behavior.

## Task 1 — Regression contract
- Extend the existing source-contract test to inspect `App/Core/InventoryEnumerator.c` and `.h`.
- Require `FW_INVENTORY_SUPPLEMENTAL_TARGET_COUNT 7u`.
- Require the exact seven Name+GUID entries in approved order.
- Require `SystemConfig` to be absent.
- Verify the current five-target source fails this contract (RED).

## Task 2 — Minimal source overlay
- Keep the accepted supplemental payload unchanged.
- Extend the existing hash-verified post-overlay transform to replace only the supplemental name/table block and the `5u` count macro.
- Preserve the JSONL quote fix in the same transform invocation.
- Do not alter enumeration loops, exact-pair matching, direct read implementation, report writing, or dump logic.

## Task 3 — GREEN verification
- Run the source-contract test and existing host verification.
- Confirm exact target order and count.
- Confirm source `SetVariable` matches remain zero.

## Task 4 — Authoritative EDK II build
- Update only the transform provenance hash in the authoritative workflow.
- Build X64 RELEASE with pinned VS2022/EDK II/NASM environment.
- Require ReadOnlyVarTool.efi, WriteVarTool.efi, and InventoryVarTool.efi.
- Require PE32+/AMD64 validation and zero InventoryVarTool binary `SetVariable` matches.

## Task 5 — Independent artifact inspection
- Download the accepted EFI artifact.
- Verify InventoryVarTool PE identity and SHA-256.
- Verify all seven target names are present in the binary.
- Re-run ASCII/UTF-16LE `SetVariable` scans.
- Deliver the replacement InventoryVarTool only; do not authorize WriteVarTool execution.

## Provenance
- Target-priority + JSONL transform SHA-256: `89736ffa3673578d155b050295d8883a7187ad5f0697108a220437c805bf99d0`
- Authoritative workflow pin updated on `main` in commit `e735469f0ff10fa7713dda5fb39964a727980c4a`.
