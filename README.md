# FirmwareVariableTool

A focused x64 UEFI diagnostic and guarded patch tool for the Dell Inspiron 5675 `AMD_PBS_SETUP` variable.

The design deliberately separates `ReadOnlyVarTool.efi` from `WriteVarTool.efi`. The read-only build does not compile the `SetVariable` path. The writer requires a USB backup with CRC32 read-back verification, a validated patch file, an expected-old-value match, an exact operator confirmation phrase, and an immediate post-write re-read.

## Host tests

```bash
cmake -S host -B build-host
cmake --build build-host
ctest --test-dir build-host --output-on-failure
```

## EDK II build

Place or symlink `UefiVarToolPkg` into an EDK II workspace, initialize EDK II, then build the X64 release package. See `docs/operator-runbook.md` for field use.
