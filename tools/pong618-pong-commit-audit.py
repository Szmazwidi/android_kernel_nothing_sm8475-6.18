#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Track ALL explicitly Pong-labelled baseline commits and source paths across .60->.63.

Read-only: names are based on git history, not presumed patch equivalence.
The whole-tree/301 overlap audits remain independent compulsory release gates.
"""
import argparse,collections,json,re,subprocess
from pathlib import Path
BASE="58b289d57b3d1f4b6fa6bb51db13920f459ae153"
STABLE="1cdda838e8475edf89b73ff0cc952005dd0b1fa7"
COMMON="f45ed76d6791cf72ff1265ee93511175bbbc2f18"
MERGED="d444348c03f7605f97eaa99423483e3bc91420bc"
def git(*args):
    p=subprocess.run(["git",*args],capture_output=True,check=True)
    return p.stdout
def names(a,b):
    return {s.decode(errors="surrogateescape") for s in git("diff","--no-renames","--name-only","-z",a,b).split(b"\0") if s}
def tree(commit):
    entries={}
    for row in git("ls-tree","-r","-z",commit).split(b"\0"):
        if not row:continue
        meta,name=row.split(b"\t",1)
        entries[name.decode(errors="surrogateescape")]=meta.decode().split()
    return entries
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True,type=Path);args=p.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    if git("merge-base",BASE,STABLE).decode().strip()!=COMMON:raise RuntimeError("unexpected ACK/stable merge base")
    head=git("rev-parse","HEAD").decode().strip()
    if subprocess.run(["git","merge-base","--is-ancestor",MERGED,head]).returncode:
        raise RuntimeError("candidate is not descendant of verified 6.18.63 source merge")
    log=git("log","--no-merges","--format=%H%x09%s",COMMON+".."+BASE).decode().splitlines()
    commits=[]
    relevant=set()
    for entry in log:
        sha,subject=entry.split("\t",1)
        if not re.search(r"\bpong\b",subject,re.I):continue
        parents=git("rev-list","--parents","-n1",sha).decode().strip().split()[1:]
        if not parents:raise RuntimeError("commit without parent: "+sha)
        paths=names(parents[0],sha)
        relevant.update(paths)
        commits.append({"sha":sha,"subject":subject,"file_count":len(paths),"paths":sorted(paths)})
    if len(commits)<34:
        raise RuntimeError("Expected at least 34 Pong-labelled baseline commits; got "+str(len(commits)))
    base=tree(BASE);candidate=tree(head);stable=tree(STABLE);common=tree(COMMON)
    active_paths=sorted(p for p in relevant if base.get(p)!=common.get(p))
    rows=[]
    for path in active_paths:
        b,c,s=base.get(path),candidate.get(path),stable.get(path)
        if b==c:status="BYTE_IDENTICAL_PONG_SOURCE_PRESERVED"
        elif s==common.get(path):status="PONG_SOURCE_CHANGED_NOT_BY_STABLE_REVIEW"
        elif c==s:status="MERGED_MATCHES_STABLE_PONG_DIFF_MAY_BE_LOST"
        else:status="PONG_AND_STABLE_CHANGES_MIXED_REVIEW"
        rows.append({"path":path,"status":status,"base_object":b,"candidate_object":c,"stable_object":s})
    summary={
       "stage_status":"PONG_LABELLED_COMMIT_SOURCE_AUDIT",
       "evidence_level":"HOST_VERIFIED_TREE_OBJECTS_NOT_SEMANTIC_EQUIVALENCE",
       "candidate_sha":head,"baseline_sha":BASE,"stable_sha":STABLE,
       "pong_labelled_commits_count":len(commits),
       "baseline_source_paths_touched_by_pong_commits":len(relevant),
       "pong_touched_paths_active_in_6_18_60":len(rows),
       "categories":dict(collections.Counter(r["status"] for r in rows)),
       "needs_review":sorted(r["path"] for r in rows if r["status"]!="BYTE_IDENTICAL_PONG_SOURCE_PRESERVED"),
       "limits":"A label search misses unlabeled custom changes. This audit does NOT prove semantic preservation; evaluate mixed paths against 301-overlap diff and ABI/build tests.",
       "historical_reuse_audit":"U59 xHCI ACK r5 KMI preserve; historic 5.15 SLIMbus/module ABI symptoms no patch copied",
       "performed_phone_operations":[],"protected_partitions_unchanged":"NO_PHONE_WRITES",
       "recovery_status":"NOT_REQUALIFIED"}
    (args.output/"pong-labelled-commits.json").write_text(json.dumps(commits,indent=2)+"\n")
    (args.output/"pong-active-paths.json").write_text(json.dumps(rows,indent=2)+"\n")
    (args.output/"pong-source-preservation-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="needs_review"},indent=2))
    print("needs_review_count",len(summary["needs_review"]))
if __name__=="__main__": main()
