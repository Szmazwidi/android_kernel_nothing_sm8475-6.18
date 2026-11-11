#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only hunk signal audit of all common/ACK/PONG/6.18.63 overlap paths.

A missing exact source line is NOT necessarily a lost behavior; this tool
identifies candidates for manual port/semantic review. Results are evidence,
never permission to flash or assume patch equivalence.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

COMMON="f45ed76d6791cf72ff1265ee93511175bbbc2f18"
BASE="58b289d57b3d1f4b6fa6bb51db13920f459ae153"
STABLE="1cdda838e8475edf89b73ff0cc952005dd0b1fa7"
INTEGRATION="d444348c03f7605f97eaa99423483e3bc91420bc"

def git(*args):
    p=subprocess.run(["git",*args],capture_output=True)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace')[:1500]}")
    return p.stdout

def changed(a,b):
    return {x.decode(errors="surrogateescape") for x in git("diff","--no-renames","--name-only","-z",a,b).split(b"\0") if x}

def lines_at(ref,path):
    p=subprocess.run(["git","show",ref+":"+path],capture_output=True)
    if p.returncode:
        return None
    data=p.stdout
    if len(data)>2_000_000 or b"\0" in data:
        return None
    try:
        return {line.strip() for line in data.decode("utf-8").splitlines()
                if len(line.strip())>=15 and
                   not re.match(r"^[{};)(,/* +\t-]+$",line.strip())}
    except UnicodeDecodeError:
        return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    head=git("rev-parse","HEAD").decode().strip()
    if subprocess.run(["git","merge-base","--is-ancestor",INTEGRATION,head]).returncode:
        raise RuntimeError("Expected candidate descendant of verified source integration")
    if subprocess.run(["git","merge-base","--is-ancestor",BASE,head]).returncode:
        raise RuntimeError("Candidate lost Android base ancestry")
    if subprocess.run(["git","merge-base","--is-ancestor",STABLE,head]).returncode:
        raise RuntimeError("Candidate lost upstream 6.18.63 ancestry")
    ours=changed(COMMON,BASE)
    upstream=changed(COMMON,STABLE)
    overlap=sorted(ours&upstream)
    rows=[]
    for path in overlap:
        common,old,cand = [lines_at(ref,path) for ref in (COMMON,BASE,head)]
        if old is None or common is None or cand is None:
            rows.append({"path":path,"status":"SKIPPED_NON_TEXT_OR_LARGE"});continue
        added=old-common
        removed=common-old
        lost=sorted(added-cand)
        resurrected=sorted(removed&cand)
        severity=("HIGH_REVIEW" if (lost or resurrected) and
            path.startswith(("drivers/","arch/arm64/","fs/","kernel/","net/","rust/")) else
            "REVIEW" if (lost or resurrected) else "NO_EXACT_LINE_LOSS_DETECTED")
        rows.append({"path":path,"status":severity,
                    "unique_baseline_additions":len(added),
                    "missing_added_count":len(lost),
                    "restored_removed_count":len(resurrected),
                    "missing_additions_sample":lost[:16],
                    "resurrected_removals_sample":resurrected[:16]})
    by_status=Counter(x["status"] for x in rows)
    critical=sorted(
       (x for x in rows if x["status"]=="HIGH_REVIEW"),
       key=lambda r: (0 if r["path"].startswith(
          ("drivers/remoteproc/","drivers/usb/","drivers/scsi/ufs/","fs/f2fs/",
           "kernel/sched/","net/netfilter/","rust/")) else 1,
           -(r.get("missing_added_count",0)+r.get("restored_removed_count",0)),
           r["path"]))
    report={
      "stage_status":"SUSPECT_PATCH_OVERLAPS_REVIEW_REQUIRED",
      "evidence_level":"HOST_VERIFIED_HEURISTIC_SOURCE_SCAN",
      "candidate_sha":head,"base_sha":BASE,"stable_sha":STABLE,
      "overlap_paths":len(overlap),
      "groups":dict(by_status),
      "critical_review_paths":[r["path"] for r in critical],
      "first_critical_examples":critical[:25],
      "limits":"Exact-line heuristic; unchanged lines need not mean semantic equivalence; renamed/modified lines can be correct stable ports.",
      "highest_verified_boot_stage":"Android 17 6.18.60 only",
      "historical_reuse_audit":"U59 xHCI ACK r5 KMI decision and 5.15 driver/header/ABI failures, not direct patches",
      "performed_phone_operations":[],
      "protected_partitions_unchanged":"NO_PHONE_WRITES",
      "recovery_status":"BROKEN_UI_NOT_REQUALIFIED",
      "next_autonomous_batch":"Human/API review high-risk source hunks; rebuild with pinned Android17 Kleaf, 293 signed modules and KMI checks"
    }
    (a.output/"overlap-hunk-review.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    (a.output/"overlap-hunk-rows.json").write_text(json.dumps(rows,indent=2,ensure_ascii=False)+"\n")
    (a.output/"high-priority-paths.txt").write_text("\n".join(r["path"] for r in critical)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in
        ("critical_review_paths","first_critical_examples","historical_reuse_audit",
         "next_autonomous_batch")},indent=2))
    print("HIGHEST_RISK_PATHS:")
    for r in critical[:25]:
        print(r["path"],"lost+",r["missing_added_count"],"restored-",r["restored_removed_count"])
    # Record all findings, including heuristic false positives; not a functional gate.
if __name__=="__main__":
    main()
