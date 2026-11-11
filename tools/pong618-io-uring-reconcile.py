#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reconcile mismatched io_uring 6.18.63 stable task-work code with Android .60 ABI.

Fail closed on any unexpected 6.18.60 or merged source blobs. Isolated
source-only edit. Preserve .63 xarray accounting, restore verified Android
r5/PONG io_queue_iowq logic matching include/linux/io_uring_types.h.
"""
from pathlib import Path
import subprocess
import hashlib
import json

BASE="58b289d57b3d1f4b6fa6bb51db13920f459ae153"
OLD_BLOB="0837ec81223546948ec302c26d59e369f5d1ff38"
MERGED_BLOB="24052e0768fd77a152e77e5b4b3494201380a4cd"
ANDROID_TYPE_BLOB="974a3f29ec3d578a820afc2dee71356a011b0a1d"
FILE=Path("io_uring/io_uring.c")
TYPE=Path("include/linux/io_uring_types.h")
def git(*args):
    proc=subprocess.run(["git",*args],capture_output=True,check=True)
    return proc.stdout

def abort(reason):
    raise SystemExit("STOP: "+reason)

if git("hash-object",str(FILE)).decode().strip()!=MERGED_BLOB:
    abort("Candidate io_uring.c source changed")
if git("hash-object",str(TYPE)).decode().strip()!=ANDROID_TYPE_BLOB:
    abort("Android io_uring_types.h layout changed")
old=git("show",BASE+":"+str(FILE)).decode()
cur=FILE.read_text()
if git("rev-parse",BASE+":"+str(FILE)).decode().strip()!=OLD_BLOB:
    abort("Expected 6.18.60 io_uring base blob differs")
start="static void io_queue_iowq("
end="static void io_req_queue_iowq_tw("
a,b=old.index(start),old.index(end)
c,d=cur.index(start),cur.index(end)
if any(s in old[a:b] for s in ("struct io_tw_req", "tw.cancel")):
    abort("Baseline task-work implementation is not the pinned Android variant")
if "struct io_tw_req" not in cur[c:d] or "tw.cancel" not in cur[c:d]:
    abort("Unexpected stable task-work implementation")
if "struct io_tw_req {" in TYPE.read_text() or "bool cancel;" in TYPE.read_text():
    abort("The Android header now supports upstream types; revisit replacement")
merged=cur[:c]+old[a:b]+cur[d:]
if "io_queue_iowq_foreign_tw" in merged or "tw.cancel" in merged:
    abort("Unexpected stable task-work symbols remain")
for invariant in ("XA_FLAGS_ALLOC1 | XA_FLAGS_ACCOUNT", "xa_destroy(&ctx->personalities)"):
    if invariant not in merged:
        abort("Lost independent stable fix: "+invariant)
if merged.count(start)!=1:
    abort("Broken queue declaration or duplicate function")
FILE.write_text(merged)
report={
    "stage_status":"ANDROID_IO_URING_ABI_CONFLICT_RECONCILED_SOURCE_ONLY",
    "evidence_level":"HOST_VERIFIED_SOURCE_ONLY",
    "base_source_blob":OLD_BLOB,
    "incompatible_merge_blob":MERGED_BLOB,
    "candidate_file_sha256":hashlib.sha256(FILE.read_bytes()).hexdigest(),
    "policy":"Restore Android 6.18.60 io_queue_iowq task work API, keep stable 6.18.63 xarray accounting",
    "historical_reuse_audit":"PONG U59 commit 014f1f8fde8d - io_uring types affect KMI CRCs. Base Android r5 ABI retained. Stable task-work rework deferred pending full Android/KMI tests.",
    "compiler":"NOT_TESTED",
    "module_kmi":"NOT_TESTED",
    "phone_operations":0,
    "protected_partitions_unchanged":"NO_PHONE_WRITES",
    "recovery_status":"NOT_REQUALIFIED"
}
out=Path("pong61863-io-uring-reconciliation.json")
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
