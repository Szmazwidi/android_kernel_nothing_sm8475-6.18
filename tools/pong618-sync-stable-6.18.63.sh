#!/usr/bin/env bash
# Pong / Android 17 / Linux 6.18.60 -> v6.18.63 source-only integration.
# Safe by design: no phone operations, no signing, no module-bank updates, no ROM packaging.
# This script deliberately aborts rather than guessing a non-standard ACK/stable base.
set -Eeuo pipefail
export LC_ALL=C

BASE_REF="${PONG_61863_BASE_REF:-pong-a17-6.18.60}"
STABLE_URL="${PONG_61863_STABLE_URL:-https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git}"
STABLE_TAG="v6.18.63"
BASE_TAG="v6.18.60"
EXPECTED_63="1cdda838e8475edf89b73ff0cc952005dd0b1fa7"
INTEGRATION_BRANCH="${PONG_61863_INTEGRATION_BRANCH:-pong-a17-6.18.63-integration}"

die() { printf 'STOP: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }
for cmd in git make awk grep date tee; do need "$cmd"; done

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)" || die "Not in a Git checkout"
cd "$REPO"
WORKTREE="${PONG_61863_WORKTREE:-$(dirname "$REPO")/pong-kernel-6.18.63-integration}"
LOG_DIR="${PONG_61863_REPORT_DIR:-$(dirname "$REPO")/pong-kernel-6.18.63-reports}"
mkdir -p "$LOG_DIR"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/$RUN_ID.log"
REPORT="$LOG_DIR/$RUN_ID-summary.txt"
exec > >(tee -a "$LOG") 2>&1

printf 'PONG_61863_SOURCE_ONLY_PREP\n'
printf 'utc=%s\nrepo=%s\nworktree=%s\nreport=%s\n' "$RUN_ID" "$REPO" "$WORKTREE" "$REPORT"

# Do not rewrite a dirty original checkout or reuse an old experimental worktree.
[[ -z "$(git status --porcelain)" ]] || die "Original checkout is dirty; keep all local changes and rerun after reviewing them"
if ! git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null; then
    # A fresh checkout of the preparation branch may not have a local baseline branch.
    if [[ "$BASE_REF" == "pong-a17-6.18.60" ]] && git remote get-url origin >/dev/null 2>&1; then
        git fetch origin "+refs/heads/pong-a17-6.18.60:refs/remotes/origin/pong-a17-6.18.60"
        BASE_REF="refs/remotes/origin/pong-a17-6.18.60"
    fi
fi
git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null || die "Missing base ref $BASE_REF"
BASE_SHA="$(git rev-parse "${BASE_REF}^{commit}")"
printf 'base_ref=%s\nbase_sha=%s\n' "$BASE_REF" "$BASE_SHA"

if [[ -e "$WORKTREE" ]] || git show-ref --verify --quiet "refs/heads/$INTEGRATION_BRANCH"; then
    die "Candidate worktree or branch exists; inspect/resume manually, never overwrite it automatically"
fi

printf '\n[1/5] Fetch official Linux stable release tags\n'
# The upstream release SHA was separately verified against the stable branch on 2026-11-11.
# Fetch both tags explicitly, without rewriting local history or the source branch.
git fetch --no-tags "$STABLE_URL" \
    "refs/tags/$BASE_TAG:refs/tags/$BASE_TAG" \
    "refs/tags/$STABLE_TAG:refs/tags/$STABLE_TAG"
TAG_SHA="$(git rev-parse "${STABLE_TAG}^{commit}")"
printf 'stable_63_commit=%s\n' "$TAG_SHA"
[[ "$TAG_SHA" == "$EXPECTED_63" ]] || die "Upstream v6.18.63 identity mismatch; refusing integration"

printf '\n[2/5] Check upstream ancestry: a version-string edit is NOT an update\n'
git merge-base --is-ancestor "${BASE_TAG}^{commit}" "${STABLE_TAG}^{commit}" ||
    die "Upstream v6.18.60 is not an ancestor of v6.18.63"
git merge-base --is-ancestor "${BASE_TAG}^{commit}" "$BASE_SHA" ||
    die "Custom source is not a descendant of upstream v6.18.60. Review ACK history/patch provenance; do not blind-merge or force."
PATCH_COUNT="$(git rev-list --count "${BASE_TAG}..${STABLE_TAG}")"
printf 'upstream_commits_60_to_63=%s\n' "$PATCH_COUNT"
(( PATCH_COUNT > 0 && PATCH_COUNT < 10000 )) || die "Unexpected patch-series size"
git diff --name-only "$BASE_TAG" "$STABLE_TAG" > "$LOG_DIR/$RUN_ID-upstream-files.txt"
git log --format='%h %s' "$BASE_TAG..$STABLE_TAG" -- \
    drivers/slimbus drivers/scsi/ufs drivers/ufs sound/soc/qcom \
    drivers/cpufreq kernel/power mm fs/f2fs \
    > "$LOG_DIR/$RUN_ID-targeted-upstream-commits.txt"

printf '\n[3/5] Make independent worktree and integrate actual stable commits\n'
git worktree add -b "$INTEGRATION_BRANCH" "$WORKTREE" "$BASE_SHA"
if ! git -C "$WORKTREE" merge --no-ff --no-edit "$STABLE_TAG"; then
    git -C "$WORKTREE" status --short > "$LOG_DIR/$RUN_ID-merge-conflicts.txt" || true
    printf '\nmerge_status=FAILED_OR_CONFLICT\n'
    printf 'preserved_worktree=%s\n' "$WORKTREE"
    die "Manual conflict analysis required. Nothing on the original branch or phone was modified."
fi

printf '\n[4/5] Source-level checks (NOT a build or phone verification)\n'
MERGED_SHA="$(git -C "$WORKTREE" rev-parse HEAD)"
VERSION="$(make -s -C "$WORKTREE" kernelversion)"
printf 'candidate_sha=%s\nreported_kernelversion=%s\n' "$MERGED_SHA" "$VERSION"
[[ "$VERSION" == "6.18.63" ]] || die "Merged source does not identify as 6.18.63"
git -C "$WORKTREE" merge-base --is-ancestor "$TAG_SHA" HEAD ||
    die "Candidate does not contain the v6.18.63 stable commit"
git -C "$WORKTREE" diff --check "$BASE_SHA" HEAD ||
    die "git diff --check failed"
git -C "$WORKTREE" status --short > "$LOG_DIR/$RUN_ID-status.txt"
git -C "$WORKTREE" diff --stat "$BASE_SHA" HEAD > "$LOG_DIR/$RUN_ID-diffstat.txt"
git -C "$WORKTREE" diff --name-only "$BASE_SHA" HEAD \
    > "$LOG_DIR/$RUN_ID-merged-files.txt"

printf '\n[5/5] Preserve qualification report; NO flashing\n'
{
    printf 'stage_status=SOURCE_INTEGRATION_DONE_BUILD_PENDING\n'
    printf 'evidence_level=HOST_VERIFIED_SOURCE_ONLY\n'
    printf 'base=%s\nbase_sha=%s\n' "$BASE_REF" "$BASE_SHA"
    printf 'upstream_tag=%s\nupstream_commit=%s\n' "$STABLE_TAG" "$TAG_SHA"
    printf 'candidate_branch=%s\ncandidate_sha=%s\n' "$INTEGRATION_BRANCH" "$MERGED_SHA"
    printf 'kernelversion=%s\nupstream_commits=%s\n' "$VERSION" "$PATCH_COUNT"
    printf 'module_ABI=NOT_TESTED\nmodule_signatures=NOT_TESTED\n'
    printf 'android_build=NOT_TESTED\nphone_boot=NOT_TESTED\n'
    printf 'protected_partitions_unchanged=NO_PHONE_OPERATIONS\n'
    printf 'recovery_status=PREVIOUSLY_REPORTED_BROKEN_UI_NOT_REQUALIFIED\n'
    printf 'historical_reuse_audit=Preserve CLG72/CLG74 IPA-rmnet SLIMbus UFS history; no old binary modules or patches copied\n'
    printf 'next_autonomous_batch=Re-pin Android17 vendor-module workspace to candidate source, rebuild kernel and ALL modules, validate ABI/signatures/AVB and QEMU; no flash until recovery qualified\n'
} > "$REPORT"
cat "$REPORT"
printf '\nREPORT: %s\nMERGED_SOURCE: %s\n' "$REPORT" "$WORKTREE"
