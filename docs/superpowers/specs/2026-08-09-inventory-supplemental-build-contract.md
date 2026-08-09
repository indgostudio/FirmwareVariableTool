# Supplemental Inventory Build Contract

Authoritative workflow: `.github/workflows/build-inventory-supplemental.yml`

Source layers, in order:

1. Reviewed MVP source SHA-256: `6d55b8a8afa0a1808379b62c6712bc8b0170b6225a7dd073822e0a38c38442c1`
2. Base inventory delta SHA-256: `b3671b57088a96dd47702c64786e97b5002b89174dd393052f250bf213f642e3`
3. EDK II compatibility patch SHA-256: `ef5e4fbdc1f43be3e4b1cd5a1345782e459a403b4721bfaccfccc64857ada152`
4. Supplemental inventory patch SHA-256: `9c56f881133e7504adb3ea979ff5cce8419ec050acdda27350f3b19ecb5bdd07`

The workflow must fail unless all source layers verify and apply, `InventoryVarTool` remains free of `SetVariable`, all three EFI applications are produced as AMD64 PE/COFF EFI applications, and the InventoryVarTool binary contains zero ASCII/UTF-16LE `SetVariable` matches.
