# Pong / Android 17: Linux 6.18.60 -> 6.18.63

**Status: source-upgrade preparation only. Not a built kernel, matching module bank, OTA or hardware-tested release.**

Verified public upstream: Linux stable `v6.18.63` (2026-11-10), commit `1cdda838e8475edf89b73ff0cc952005dd0b1fa7`.
Baseline source is `pong-a17-6.18.60`, which reports `SUBLEVEL = 60`.
The existing companion vendor-module repository and Pong device-kernel prebuilt repository remain targeted to 6.18.60.
The experimental CLG74 system currently has an unresolved recovery UI/display failure. **No new device writes are approved by this source-prep work.**

## Step 1 — safely integrate the real upstream stable history

On a Linux host with Git, GNU Make, sufficient network/disk space and permission to clone the public source repository:

```sh
git clone --branch pong-a17-6.18.63-prep \
  https://github.com/Szmazwidi/android_kernel_nothing_sm8475-6.18.git \
  pong-kernel-6.18.63-prep
cd pong-kernel-6.18.63-prep
bash tools/pong618-sync-stable-6.18.63.sh
```

The script checks the pristine clone, fetches exact official stable tags, verifies the pinned upstream 6.18.63 commit, validates that this is a true descendant of 6.18.60, and makes **a separate worktree** and branch `pong-a17-6.18.63-integration`.

It attempts an actual Git merge, **not** a cosmetic Makefile version edit. A conflict, missing tag, incompatible ancestry or unexpected release SHA stops the batch, preserving conflict evidence rather than force-merging or discarding custom changes. It records upstream file lists, targeted commit titles, merged file lists, patch statistics, kernel version and a stage summary in a sibling `pong-kernel-6.18.63-reports/` directory.

A clean merge verifies source integration only: it does **not** establish Android kernel KMI, compiled module ABI, bootability or energy improvement.

## Step 2 — Android 17 and vendor modules

Before preparing a boot image:

1. Identify the **exact tested CLG74** kernel/modules/device/prebuilt commits and the 293 selected modules (209 vendor + 84 GKI; 100 first-stage); do not use older 262/277-module examples as a current binary bank.
2. Re-pin the companion modules workspace and Android 17 manifest to the new merged kernel source. Check vendor source API/ABI, module imports and symbol CRCs against the **new** kernel. Fix incompatible source interfaces rather than disabling KMI checks.
3. Re-run the existing project's two-pass freeze/build/sign/verify pipeline for the complete selected module set, including positive/negative admission checks, BTF/signature/ABI checks and QEMU boot-smoke regression. Maintain `CONFIG_MODULE_SIG_FORCE=y`.
4. Rebuild the **matching** Android boot, vendor_boot, dtbo, recovery and AVB/OTA image set using the qualified Android 17 product configuration. Do not mix developer and release signing identities or splice old 6.18.60 `.ko` files into 6.18.63.
5. Verify hashes, signed image identifiers, platform firmware baseline, A/B and `super` metadata before any authorized test on the phone.

**Important:** the source-only script does not claim to run these steps, does not change ROM/APEX/SELinux, and does not write to phone partitions.

## Step 3 — targeted regression checks

- Android boot: `sys.boot_completed=1`, SELinux Enforcing; first boot and cold reboot, /data and FBE checkpoint.
- The known broken recovery UI: first establish working recovery and tested restoration without touching protected partitions.
- IPA/rmnet: quantify `IPA_CLIENT_APPS_WAN_LOW_LAT_CONS`, `rmnet_ctl`, suspend failures and modem activity; validate LTE/5G, voice, SMS, Wi-Fi, hotspot and airplane-mode transitions.
- SLIMbus/QDSP6: check PM get/put balance, failure paths, audio routes and DSP state; distinguish upstream fix presence from a verified device-level improvement.
- UFS and F2FS: I/O, retries, recovery behavior, filesystem errors and clean boot.
- CPUIdle/TEO, schedutil, 4 KiB memory settings, module memory/CPU hot-add and camera.
- Matched screen-off, untethered overnight drain versus CLG72 (71 mAh in 9h38m, ~7.37 mA) and CLG74 (~297 mAh in 6h37m30s, ~44.8 mA). Keep radio conditions and setup state comparable.

## Safety / release gates

No wipe, slot changes, protected partition writes, ROM/recovery flash, or bootloader relock is authorized by this branch or script. The device reportedly had a malformed recovery screen; verify rescue images, backup, hashes, bootloader/fastboot access and a working recovery path **before requesting a separately scoped destructive-operation authorization**.

A successful source merge is **not** a qualified community OTA. Publishing a new version string without actually building/signing/test-booting the source would be misleading.

## historical_reuse_audit

- **CLG72:** observed good overnight drain after a UFS-related fix; retain as the comparator only.
- **CLG74:** measured excessive overnight drain and frequent IPA/rmnet wakeups; do not attribute root cause to a stable patch without an A/B test.
- **5.10 / 5.15 history:** earlier `IPA_CLIENT_APPS_WAN_LOW_LAT_CONS rmnet_ctl` wakeup signatures exist (e.g. indexed Pong 317 logs); the historical index contains related `RPMH_POWER` and `STORAGE_MEMORY` evidence but the currently retrieved excerpts do not prove a compatible tested correction.
- **6.6 / 6.12 ports:** retain as code/API references if exact source and commit are accessible; no binary/module transfer, no assumed equivalence.
- **Compatibility with 6.18.63:** **unverified until actual merge, full build and hardware tests**.

## Batch report (2026-11-11)

- `stage_status`: PREPARED_NOT_EXECUTED
- `evidence_level`: HOST_VERIFIED for GitHub source identity and script commit; not for merge/build
- `highest_verified_boot_stage`: existing CLG74 baseline had boot-completed Android 17; 6.18.63 has **NOT** booted here
- `new_progress`: independent preparation branch, pinned upstream stable commit and conflict-safe worktree script
- `regressions`: no code/phone regression tested in this batch
- `remaining_blockers`: actual source merge, ABI and module rebuild, QEMU, recovery restore, physical tests
- `tests_passed`: upstream release exists; 6.18.60 Makefile verified; prep source files stored
- `tests_failed`: none executed; no claims of build success
- `performed_phone_operations`: 0
- `protected_partitions_unchanged`: no operations attempted, no hardware readback
- `recovery_status`: unresolved prior UI/display failure
- `next_autonomous_batch`: run integration script on host, inspect conflicts and ABI exposure, re-pin full module workspace, compile/sign/test host artifacts; hardware only after separate safety authorization
