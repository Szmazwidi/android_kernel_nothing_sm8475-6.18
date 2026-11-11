#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply exact, reviewed source-only resolutions for the 6.18.60 -> 6.18.63 merge.

Inputs must match all 15 conflict-marked files of 2026-11-11 byte-for-byte.
Any unexpected upstream/ACK base, missing stage, or changed conflict FAILS CLOSED.
High-risk ACK ABI, pKVM, Qualcomm remoteproc and xHCI code is retained;
deferred stable fixes require later focused ports. This is NOT ABI/build/boot proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

EXPECTED = {
    "arch/arm64/kvm/hyp/exception.c": ("dbc0df29e7d4fc46f711d1a0fea0b8dc935c51e0e85eebd71e613e14ec4a2166", 2, "ack"),
    "arch/x86/kvm/vmx/vmx.c": ("b40b6124791ebdfca1584b79bffcf6b92f31cf63e7175f98de4fff20349299f6", 5, "ack"),
    "arch/x86/kvm/x86.c": ("45689ab808a816acd46b8364db35a117e0779be7fb505a1e5ca534f00177ea65", 1, "ack"),
    "drivers/media/rc/rc-ir-raw.c": ("a0be0cd759f7d4b52caeae95ea6d3af0aef3651a68a1e92339f6ef462862412f", 2, "stable"),
    "drivers/remoteproc/remoteproc_core.c": ("1473e5c6370cec4a7760e926315078ba1b7ecb895b739fc56b11705dbe1eca9f", 1, "ack"),
    "drivers/usb/host/xhci-ring.c": ("f83ce8e63856bc09c0794d2b4b27ec0c803f7758ae01ad1cc66c50557efd55b2", 1, "ack"),
    "fs/backing-file.c": ("699331b8743f9074e05c607ebdb952ca9ac85549449758b564257112ed5208ef", 1, "ack-plus-real-inode-guard"),
    "include/linux/device/bus.h": ("28873f180f723b9a39141d277c80e1d62142287bd1d3b978084490031a8f6541", 1, "ack"),
    "kernel/sched/ext.c": ("f76235653ff6b3858db957c92feb39bd5feac2ae1c2b78fe1c160e6f045621a1", 2, "stable-hunks"),
    "mm/madvise.c": ("ec79260ed6b0cc28cdfddcd2c22ce8e4ee5b18adae328bbe30274a8e11b2f08d", 1, "android-reclaim-plus-resched"),
    "net/netfilter/nf_conntrack_netlink.c": ("ef382652609465f81f5851821362afc95f82991ede6cbef7275253ef7881e1d0", 1, "stable"),
    "net/netfilter/nf_conntrack_sip.c": ("af0b56f7f698bf798b9d0c5c50b7e0b0d98f4120ff50698036a881e04656e5c4", 1, "stable"),
    "rust/bindgen_parameters": ("079b0e95df2faa0e68a718de256cd286e213a8521b2440712582826ac6be6e93", 1, "combine-enums"),
    "rust/kernel/bitmap.rs": ("b18ff6eec2f1a2a486bdb6250789958cb789367778f04b6dfafa58427a0feaa8", 1, "stable"),
    "rust/kernel/id_pool.rs": ("e2a5c8ac9fc54eba1be4e6e0bc6b547440ea2c0618ca8bbb464c971c9dadc95c", 1, "stable"),
}
CONFLICT = re.compile(r"^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>> v6\.18\.63\n", re.M | re.S)

def fatal(message):
    raise SystemExit("STOP REVIEWED MERGE: " + message)

def git_bytes(worktree, *args):
    proc = subprocess.run(["git", "-C", str(worktree), *args], capture_output=True)
    if proc.returncode:
        fatal("git " + " ".join(args) + ": " + proc.stderr.decode(errors="replace")[:1200])
    return proc.stdout

def sha(data):
    return hashlib.sha256(data).hexdigest()

def resolve(data, ours, theirs, count, policy):
    source = data.decode("utf-8")
    hunks = list(CONFLICT.finditer(source))
    if len(hunks) != count:
        fatal("Unexpected number of conflict hunks: " + str((policy, len(hunks), count)))
    if policy == "ack":
        final = ours.decode("utf-8")
    elif policy == "stable":
        final = theirs.decode("utf-8")
    elif policy == "ack-plus-real-inode-guard":
        final = ours.decode("utf-8")
        old = "\tstruct file *f;\n\tint error;\n\n\tf = alloc_empty_backing_file(flags, cred);"
        new = (
            "\tstruct inode *real_inode = d_inode(real_path->dentry);\n"
            "\tstruct file *f;\n\tint error;\n\n"
            "\t/* Honor immutable and append-only state of the backing inode. */\n"
            "\tif ((flags & O_ACCMODE) != O_RDONLY) {\n"
            "\t\tif (IS_IMMUTABLE(real_inode))\n\t\t\treturn ERR_PTR(-EPERM);\n"
            "\t\tif (IS_APPEND(real_inode) && !(flags & O_APPEND))\n"
            "\t\t\treturn ERR_PTR(-EPERM);\n\t}\n\n"
            "\tf = alloc_empty_backing_file(flags, cred);"
        )
        if final.count(old) != 2:
            fatal("Unexpected backing-file Android API layout")
        final = final.replace(old, new, 1)
        if "file_user_path(user_file)" in final or "alloc_empty_backing_file(flags, cred, user_file)" in final:
            fatal("Upstream backing_file user_file API leaked into Android path-based ABI")
    else:
        if policy == "stable-hunks":
            changes = [h.group(2) for h in hunks]
        elif policy == "android-reclaim-plus-resched":
            if "__reclaim_pages(&folio_list, private->private);" not in hunks[0].group(1):
                fatal("Unexpected Android private reclaim call")
            changes = ["\t\t\t__reclaim_pages(&folio_list, private->private);\n\t\tcond_resched();\n"]
        elif policy == "combine-enums":
            if "--newtype-enum lru_status" not in hunks[0].group(1):
                fatal("Missing Android bindgen CFI enum")
            changes = [hunks[0].group(1) + hunks[0].group(2)]
        else:
            fatal("Unknown resolution policy: " + policy)
        final = source
        for h, replacement in reversed(list(zip(hunks, changes))):
            final = final[:h.start()] + replacement + final[h.end():]
    if re.search(r"(?m)^(?:<<<<<<< |=======|>>>>>>> )", final):
        fatal("Conflict markers survive the reviewed merge")
    return final.encode("utf-8")

def assert_contracts(resolved):
    txt = lambda p: resolved[p].decode("utf-8")
    if not all(f"ANDROID_KABI_RESERVE({i});" in txt("include/linux/device/bus.h") for i in range(1, 5)):
        fatal("Android bus_type KMI reserves absent")
    if "trace_android" not in txt("drivers/remoteproc/remoteproc_core.c"):
        fatal("ACK remoteproc Android hook absent")
    if "get_except64_cpsr(" not in txt("arch/arm64/kvm/hyp/exception.c"):
        fatal("ACK arm64 pKVM CPSR helper absent")
    if "__reclaim_pages(&folio_list, private->private);" not in txt("mm/madvise.c"):
        fatal("Android reclaim hook/private handling absent")
    if "scx_flush_disable_work(sch);" not in txt("kernel/sched/ext.c"):
        fatal("New sched_ext disable API absent")
    if "--newtype-enum lru_status" not in txt("rust/bindgen_parameters") or "--newtype-enum irqreturn" not in txt("rust/bindgen_parameters"):
        fatal("Bindgen parameter union incomplete")
    if "IS_IMMUTABLE(real_inode)" not in txt("fs/backing-file.c"):
        fatal("Backing-inode stable security gate absent")
    if "assign_helper" not in txt("net/netfilter/nf_conntrack_sip.c"):
        fatal("New netfilter expectation helper API absent")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    worktree = opts.worktree.resolve()
    if not (worktree / ".git").exists():
        fatal("Not a worktree")
    unstaged = git_bytes(worktree, "diff", "--name-only", "--diff-filter=U", "-z")
    actual = {p.decode() for p in unstaged.split(b"\0") if p}
    if actual != set(EXPECTED):
        fatal("Changed unmerged path set: " + repr(sorted(actual.symmetric_difference(EXPECTED))))
    if git_bytes(worktree, "rev-parse", "--verify", "HEAD").decode().strip() != "58b289d57b3d1f4b6fa6bb51db13920f459ae153":
        fatal("Unexpected baseline commit HEAD")
    observed_merge_head = git_bytes(worktree, "rev-parse", "--verify", "MERGE_HEAD").decode().strip()
    expected_merge_head = "1cdda838e8475edf89b73ff0cc952005dd0b1fa7"
    print("MERGE_IDENTITY_DIAGNOSTIC:", json.dumps({
        "observed_merge_head": observed_merge_head,
        "expected_stable_commit": expected_merge_head,
        "upstream_tag_commit": git_bytes(worktree, "rev-parse", "--verify", "v6.18.63^{commit}").decode().strip(),
        "git_version": git_bytes(worktree, "--version").decode().strip(),
    }), flush=True)
    if observed_merge_head != expected_merge_head:
        fatal("Unexpected upstream MERGE_HEAD: observed=" + repr(observed_merge_head)
              + " expected=" + expected_merge_head)

    results = {}
    for path, (expected, count, policy) in sorted(EXPECTED.items()):
        raw = (worktree / path).read_bytes()
        if sha(raw) != expected:
            fatal("Conflict text changed: " + path + " got " + sha(raw))
        ours = git_bytes(worktree, "show", ":2:" + path)
        theirs = git_bytes(worktree, "show", ":3:" + path)
        final = resolve(raw, ours, theirs, count, policy)
        results[path] = final
    assert_contracts(results)
    summary = {
        "stage_status": "REVIEWED_CONFLICT_RESOLUTIONS_READY" if opts.dry_run else "REVIEWED_CONFLICTS_STAGED_COMMIT_PENDING",
        "evidence_level": "HOST_VERIFIED_SOURCE_ONLY",
        "upstream_commit": "1cdda838e8475edf89b73ff0cc952005dd0b1fa7",
        "base_commit": "58b289d57b3d1f4b6fa6bb51db13920f459ae153",
        "resolved_paths": [{"path": path, "mode": EXPECTED[path][2], "sha256": sha(blob)} for path, blob in sorted(results.items())],
        "deferred_stable_file_fixes": [p for p, r in EXPECTED.items() if r[2] == "ack"],
        "build": "NOT_TESTED",
        "module_abi": "NOT_TESTED",
        "phone_operations": 0,
        "historical_reuse_audit": "U59 xHCI ACK r5/KMI preservation, 5.15 remoteproc and module ABI observations; no binary reuse",
    }
    if not opts.dry_run:
        for path, blob in results.items():
            (worktree / path).write_bytes(blob)
        git_bytes(worktree, "add", "--", *sorted(results))
        if git_bytes(worktree, "ls-files", "-u").strip():
            fatal("Index remains unmerged")
        # Check whitespace in the reviewed files only. Full stable source checks follow.
        git_bytes(worktree, "diff", "--cached", "--check", "--", *sorted(results))
    opts.report.parent.mkdir(parents=True, exist_ok=True)
    opts.report.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="resolved_paths"}, indent=2))
    print("reviewed_files=" + str(len(results)) + " reviewed_hunks=" + str(sum(v[1] for v in EXPECTED.values())))
if __name__ == "__main__":
    main()
