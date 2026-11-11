# Nothing Phone (2) / 6.18.63: checked baselines and historical reuse audit

Date: 2026-11-11. **This report documents source inspection, not a successful integration, build, phone boot or battery fix.**

## Verified repository baselines

| Component | Branch | HEAD |
| --- | --- | --- |
| Kernel / 6.18.60 | `pong-a17-6.18.60` | `58b289d57b3d1f4b6fa6bb51db13920f459ae153` |
| Companion modules / CLG74 | `pong-a17-6.18.60-community-clg74` | `935e1cf587ada4e684c48b89f04f93cd4b5ad86f` |
| Companion modules / baseline | `pong-a17-6.18.60` | `0f15844829dd2d719e983dc2080fe15e7eae5f5e` |
| Device kernel prebuilt / CLG74 | `pong-kernel-clg74` | `c263ba37903f04698f1a26214fc420cf3daea1f7` |
| Official Linux stable release | `v6.18.63` | `1cdda838e8475edf89b73ff0cc952005dd0b1fa7` |

The baseline kernel `Makefile` reports `SUBLEVEL = 60`; the preparation branch does too. The 6.18.63 candidate requires **actual stable commit integration**. The CLG74 vendor-module branch is 19 commits ahead of its 6.18.60 module baseline and must not be replaced by the older 262-module or 277-module cohort.

## Specific source observation

In the current 6.18.60 `drivers/slimbus/messaging.c`, `slim_do_transfer()` calls `pm_runtime_get_sync()` and returns directly when `slim_alloc_txn_tid()` fails. This bypasses the common runtime-PM put at `slim_xfer_err`; it matches the failure-path class of the upstream 6.18.63 SLIMbus PM-vote fix. The existence of that source path is verified; its execution on Pong and any effect on real-world power draw are **HYPOTHESIS**.

The CLG74 modules head separately contains `slimbus: initialize NGD up work before publishing SSR/PDR notifiers`. These are different changes. Do not conflate the two or revert the vendor-side fix when updating stable core.

## historical_reuse_audit — SQLite index, 5.15 archive

Read-only source: `legacy515-index.sqlite3`, indexed from 49,555 files and 286,054 extracted snippets (index generated 2026-10-18). Queries were limited to indexed evidence snippets; not a complete source-code audit.

- `IPA_CLIENT_APPS_WAN_LOW_LAT_CONS`: 2 indexed snippets, both in the stage `pong317-nokaslr-trial-nlt_vafn` 5.10 dmesg captures. They show `Pending Wakeup Sources: IPA_CLIENT_APPS_WAN_LOW_LAT_CONS rmnet_ctl`. Analogous symptom, **no proven same root cause or portable fix**.
- `slimbus`: 54 snippets, including `pong-publish14-vendor-build-bridge.json` and `pong-publish15-verified-api-batch.json`, which record missing `linux/slimbus/slimbus.h` during a 5.15 vendor audio build. This was an API/header problem, **not** evidence of the same runtime-PM vote leak.
- `ufshcd`: 445 snippets, including `pong225-audit-udn7oze1.zip`, which references older `ufshcd-crypto-qti.ko` artifacts. **Do not reuse binary modules**.
- `Module.symvers`: 4,191 snippets, including `pong-publish13-kbuild-config-includes.json`, recording unresolved exports and missing symbol-version metadata. Audit imported CRCs and providers after rebuilding the full 6.18.63 bank.
- `vermagic`: 74 snippets, including `pong199g-waipio-rpmh-joint-modpost-report.txt`. Old 5.15 module identity cannot establish 6.18.63 loadability.

No historical item above is a verified code-level fix suitable for direct transfer. The 6.6/6.12 source branches were not examined in this batch.

## Safety and next gates

1. Run the conflict-safe stable integration workflow on the preparation branch and verify its **actual** result, branch SHA and complete merge content.
2. Once source integration is successful, re-pin a separate CLG74-based module worktree and rebuild **all** selected vendor/GKI modules; require KMI, BTF, `Module.symvers`, signature and QEMU checks.
3. Reproduce a matching complete Android 17 image set and rescue procedure; **no phone flash or partition write** is authorized.
4. Recovery UI on the prior CLG74 experiment was reported broken; independently requalify fastboot/recovery and off-phone backups before physical installation.
5. Hardware regression criteria include `sys.boot_completed=1`, full phone functions and controlled screen-off drain. Neither a merge nor QEMU results meet that threshold.

## Current evidence status

- `stage_status`: SOURCE_INTEGRATION_AUTOMATION_PREPARED
- `evidence_level`: HOST_VERIFIED (repository content/index queries); HYPOTHESIS (power fix)
- `highest_verified_boot_stage`: historical CLG74 full Android 17 on 6.18.60; 6.18.63 not booted
- `new_progress`: exact source baselines pinned; SLIMbus failure path verified
- `regressions`: NOT_TESTED
- `remaining_blockers`: merge result, build, ABI, signatures, QEMU, recovery, hardware tests
- `tests_passed`: branch and source inspection, index search
- `tests_failed`: none executed in this batch
- `performed_phone_operations`: 0
- `protected_partitions_unchanged`: no phone operations; no fresh device readback
- `recovery_status`: previously reported CLG74 UI problem, not requalified
- `next_autonomous_batch`: obtain source integration workflow result, then start CLG74-pinned full build
