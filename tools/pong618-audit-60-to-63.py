#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Full source-tree preservation audit: 6.18.60 ACK/Pong -> merged v6.18.63.

Separates cleanly preserved custom trees from overlap paths that could silently
lose Android/Pong edits. Commit ancestry is NOT proof of content preservation.
Runs read-only; emits JSON and TSV evidence. Never flashes or builds a ROM.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = "58b289d57b3d1f4b6fa6bb51db13920f459ae153"
UPSTREAM = "1cdda838e8475edf89b73ff0cc952005dd0b1fa7"
MERGED = "d444348c03f7605f97eaa99423483e3bc91420bc"

def run(*args):
    p = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError("git " + " ".join(args) + " failed: " + p.stderr.decode(errors="replace")[:2000])
    return p.stdout

def obj_tree(sha):
    result = {}
    for row in run("ls-tree", "-r", "-z", "--full-tree", sha).split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, typ, obj = metadata.decode().split(" ")
        result[name.decode("utf-8", "surrogateescape")] = (mode, typ, obj)
    return result

def paths_between(a,b):
    return {p.decode("utf-8", "surrogateescape") for p in run(
        "diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", a, b).split(b"\0") if p}

def check_version():
    head = run("rev-parse", "HEAD").decode().strip()
    if head != MERGED:
        raise RuntimeError(f"Checkout changed: expected {MERGED}, got {head}")
    parents = run("rev-list", "--parents", "-n", "1", MERGED).decode().strip().split()
    if parents != [MERGED, BASE, UPSTREAM]:
        raise RuntimeError(f"Expected exact two-parent merge of base and stable: {parents}")
    common = run("merge-base", BASE, UPSTREAM).decode().strip()
    if not common:
        raise RuntimeError("Missing merge base")
    return common

def contract_check(before,after,root):
    """Structural invariants, NOT a complete ABI or semantic verification."""
    contracts = [
        ("drivers/remoteproc/remoteproc_core.c", "trace_android"),
        ("include/linux/device/bus.h", "ANDROID_KABI_RESERVE(1);"),
        ("include/linux/device/bus.h", "ANDROID_KABI_RESERVE(2);"),
        ("include/linux/device/bus.h", "ANDROID_KABI_RESERVE(3);"),
        ("include/linux/device/bus.h", "ANDROID_KABI_RESERVE(4);"),
        ("arch/arm64/kvm/hyp/exception.c", "get_except64_cpsr("),
        ("arch/arm64/configs/gki_defconfig", "CONFIG_MODULE_SIG_FORCE=y"),
        ("arch/arm64/configs/gki_defconfig", "CONFIG_MODULE_SIG_SHA256=y"),
        ("arch/arm64/configs/pong_lab.fragment", "CONFIG_PONG_LAB_GUARDS=y"),
        ("drivers/slimbus/messaging.c", "goto slim_xfer_err;"),
    ]
    checks=[]
    for p,token in contracts:
        if p not in before:
            checks.append({"path":p,"symbol":token,"status":"NOT_IN_60"})
            continue
        if p not in after:
            checks.append({"path":p,"symbol":token,"status":"MISSING_PATH_63"})
            continue
        old = run("show",BASE + ":" + p).decode("utf-8",errors="replace")
        new = (root/p).read_text(errors="replace")
        status = ("PASS" if (token in old and token in new) else
                  "NEW_IN_63" if token not in old and token in new else
                  "LOST_IN_63" if token in old and token not in new else "ABSENT_BOTH")
        checks.append({"path":p,"symbol":token,"status":status})
    return checks

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    common=check_version()
    base, stable, merged, common_tree = [obj_tree(x) for x in (BASE, UPSTREAM, MERGED, common)]
    custom=paths_between(common,BASE)
    upstream=paths_between(common,UPSTREAM)
    merge_changed=paths_between(BASE,MERGED)
    isolated=custom-upstream
    overlap=custom & upstream
    lost_isolated=sorted(p for p in isolated if base.get(p)!=merged.get(p))
    preserved_isolated=sorted(p for p in isolated if base.get(p)==merged.get(p))
    rows=[]
    for p in sorted(overlap):
        a=base.get(p)
        b=stable.get(p)
        m=merged.get(p)
        if a==b:
            status="IDENTICAL_BOTH_SIDES"
        elif m==a:
            status="BASE_PRESERVED_STABLE_CHANGE_NOT_APPLIED"
        elif m==b:
            status="CUSTOM_DIFF_MAY_BE_LOST_MERGED_MATCHES_STABLE"
        elif m==common_tree.get(p):
            status="MERGED_EQUALS_COMMON_BOTH_CHANGESETS_LOST"
        elif m is None:
            status="MERGED_PATH_ABSENT"
        else:
            status="MIXED_PATCHSET_REQUIRES_HUNK_REVIEW"
        rows.append({"path":p,"status":status,"common_blob":common_tree.get(p),
                     "base_blob":a,"upstream_blob":b,"merged_blob":m})
    stats=collections.Counter(r["status"] for r in rows)
    # Preserve original first-parent commit ancestry and enumerate historical
    # local commit subjects in a separate file without misclassifying ACK
    # cherry-picks as user/Pong patches.
    log=run("log","--no-merges","--format=%H%x09%s",f"{common}..{BASE}")
    (output/"base-commits-since-common.tsv").write_bytes(log)
    (output/"overlap-paths.tsv").write_text(
        "status\tpath\tbase_blob\tmerged_blob\tupstream_blob\n" +
        "".join(f"{r['status']}\t{r['path']}\t{r['base_blob']}\t{r['merged_blob']}\t{r['upstream_blob']}\n"
                for r in rows))
    (output/"base-only-paths-preserved.txt").write_text("\n".join(preserved_isolated)+"\n")
    (output/"base-only-paths-regressed.txt").write_text("\n".join(lost_isolated)+"\n")
    contracts=contract_check(base,merged,Path.cwd())
    source_info={
       "stage_status":"SOURCES_AUDITED_REVIEW_OR_BUILD_PENDING",
       "evidence_level":"HOST_VERIFIED_SOURCE_TREE_AUDIT",
       "base_sha":BASE,"stable_sha":UPSTREAM,"merged_sha":MERGED,
       "merge_base_sha":common,
       "commit_ancestry_preserved":True,
       "base_only_changed_paths":len(isolated),
       "base_only_exactly_preserved":len(preserved_isolated),
       "base_only_regressed":len(lost_isolated),
       "both_sides_changed_paths":len(overlap),
       "overlap_categories":dict(sorted(stats.items())),
       "historical_commit_rows":len(log.splitlines()),
       "upstream_changed_paths":len(upstream),
       "merged_vs_base_paths":len(merge_changed),
       "regressed_base_only_paths":lost_isolated,
       "overlap_possible_custom_loss":[r["path"] for r in rows if r["status"] in (
          "CUSTOM_DIFF_MAY_BE_LOST_MERGED_MATCHES_STABLE",
          "MERGED_EQUALS_COMMON_BOTH_CHANGESETS_LOST",
          "MERGED_PATH_ABSENT")],
       "structural_contracts":contracts,
       "historical_reuse_audit":{
          "6_18_59":{"source_commit":"64a21b3c403013614a24d1a6355650b578c275ce",
                     "finding":"xHCI ACK r5 API/KMI deliberately preserved; stable-only fixes deferred"},
          "5_15":{"evidence":"legacy515-index.sqlite3 remoteproc tracepoints and xhci provider/header errors",
                  "reuse":"symptom and compatibility constraints only; no old binary reuse"},
          "limits":"No automated text overlap check proves runtime equivalence; KMI build and Android phone tests pending"
       },
       "tests_passed":["two-parent-merge-identity","tree-object-comparison",
                       "source-invariant-checks-if-status-PASS"],
       "tests_failed":[],
       "performed_phone_operations":[],
       "protected_partitions_unchanged":"NO_PHONE_OPERATIONS",
       "recovery_status":"PREVIOUS_6_18_60_UI_ISSUE_UNREQUALIFIED",
       "next_autonomous_batch":"Review mixed-overlap patches, restore lost custom code, build Android-pinned kernel+293 modules and ABI",
    }
    (output/"source-preservation-audit.json").write_text(json.dumps(source_info,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in source_info.items() if k not in
          ("regressed_base_only_paths","overlap_possible_custom_loss",
           "structural_contracts","historical_reuse_audit","tests_passed","tests_failed",
           "next_autonomous_batch")},indent=2))
    problems=[c for c in contracts if c["status"] in ("LOST_IN_63","MISSING_PATH_63")]
    if lost_isolated or problems or source_info["overlap_possible_custom_loss"]:
        print("FAIL: some custom source changes may have been lost; review artifacts before release",file=sys.stderr)
        sys.exit(3)
    print("PASS: all base-only file contents preserved; BOTH-SIDES overlaps still need targeted semantic audit.")
if __name__=="__main__":
    main()
