#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only Android 6.18.60 Rust IdPool API compatibility smoke test."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import json

root=Path(__file__).resolve().parent.parent
idpool=root/"rust/kernel/id_pool.rs"
bitmap=root/"rust/kernel/bitmap.rs"
source=idpool.read_text()
bm=bitmap.read_text()
expected_idpool_sha256="573e9b4209aaefbd2c25e52714931de9d7bb58b55c31e14feda8958759100afa"
problems=[]
if hashlib.sha256(idpool.read_bytes()).hexdigest()!=expected_idpool_sha256:
    problems.append("IdPool baseline source checksum no longer matches validated .60 artifact")
for name in ("pub fn new() -> Self", "pub fn with_capacity(num_ids: usize, flags: Flags)",
             "pub fn find_unused_id(&mut self, offset: usize) -> Option<UnusedId<'_>>",
             "pub struct UnusedId<'pool>", "pub fn acquire(self) -> usize"):
    if name not in source:
        problems.append("Missing Android IdPool API: "+name)
if "pub fn new_inline() -> Self" not in bm:
    problems.append("BitmapVec::new_inline constructor absent")
if "pub fn new(nbits: usize, flags: Flags)" not in bm:
    problems.append("Stable BitmapVec::new() constructor absent")

files=subprocess.run(["git","ls-files","-z","--","*.rs"],cwd=root,capture_output=True,check=True).stdout
bad_users=[]
count=0
for raw_path in files.split(b"\0"):
    if not raw_path:
        continue
    path=raw_path.decode("utf-8",errors="surrogateescape")
    txt=(root/path).read_text(errors="replace")
    for match in re.finditer(r"\bIdPool::new\s*\(([^)]*)\)",txt):
        count+=1
        if match.group(1).strip():
            bad_users.append({"path":path,"call":match.group(0)})
    if path!="rust/kernel/id_pool.rs" and re.search(r"\.acquire_next_id\s*\(",txt):
        bad_users.append({"path":path,"call":"acquire_next_id"})
if bad_users:
    problems.append("Stale stable-only Rust clients require API migration")
report={"stage_status":"RUST_ANDROID_API_STATIC_AUDIT",
        "evidence_level":"HOST_VERIFIED_STATIC_ONLY",
        "baseline_api_sha256":expected_idpool_sha256,
        "rust_id_pool_new_calls_seen":count,
        "incompatible_rust_call_sites":bad_users,
        "problems":problems,
        "kernel_compilation":"NOT_TESTED",
        "rust_compilation":"NOT_TESTED",
        "module_bank":"NOT_TESTED",
        "phone_operations":0}
out=root/"pong61863-rust-api-report.json"
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
if problems:
    sys.exit(3)
