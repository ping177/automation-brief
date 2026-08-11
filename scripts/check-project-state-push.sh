#!/bin/sh
set -eu

repo_root=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
input_file=$(mktemp "${TMPDIR:-/tmp}/project-state-push-input.XXXXXX")
expected_file=$(mktemp "${TMPDIR:-/tmp}/project-state-push-expected.XXXXXX")
tag_file=$(mktemp "${TMPDIR:-/tmp}/project-state-push-tag.XXXXXX")
conflict_file=$(mktemp "${TMPDIR:-/tmp}/project-state-push-conflict.XXXXXX")
trailer_file=$(mktemp "${TMPDIR:-/tmp}/project-state-push-trailer.XXXXXX")
version_baseline_file=$(mktemp "${TMPDIR:-/tmp}/project-state-version-baseline.XXXXXX")
version_tip_file=$(mktemp "${TMPDIR:-/tmp}/project-state-version-tip.XXXXXX")
version_baseline_sorted_file=$(mktemp "${TMPDIR:-/tmp}/project-state-version-baseline-sorted.XXXXXX")
version_tip_sorted_file=$(mktemp "${TMPDIR:-/tmp}/project-state-version-tip-sorted.XXXXXX")
version_new_file=$(mktemp "${TMPDIR:-/tmp}/project-state-version-new.XXXXXX")

cleanup() {
  rm -f "$input_file" "$expected_file" "$tag_file" "$conflict_file" "$trailer_file" \
    "$version_baseline_file" "$version_tip_file" "$version_baseline_sorted_file" \
    "$version_tip_sorted_file" "$version_new_file"
}

trap cleanup 0 HUP INT TERM

is_zero_oid() {
  case "$1" in
    "" | *[!0]*) return 1 ;;
    *) return 0 ;;
  esac
}

fail() {
  printf '%s\n' "$*" >&2
  exit 1
}

extract_formal_version_tokens() {
  awk '
    function clean_token(token) {
      gsub(/`/, "", token)
      sub(/[—:：｜].*$/, "", token)
      return token
    }

    /^#{1,6}[[:space:]]+/ {
      heading = $0
      sub(/^#{1,6}[[:space:]]+/, "", heading)
      sub(/[[:space:]]+$/, "", heading)
      if (heading == "Current version" || heading == "当前版本") {
        section = "current"
      } else if (heading == "Version Index") {
        section = "index"
      } else {
        section = ""
      }
      next
    }

    section == "current" && $0 !~ /^[[:space:]]*$/ && !current_seen {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      split(line, parts, /[[:space:]]+/)
      token = clean_token(parts[1])
      if (token ~ /^v/) print "current\t" token
      current_seen = 1
      next
    }

    section == "index" && $0 ~ /^[[:space:]]*[-*][[:space:]]+/ {
      line = $0
      sub(/^[[:space:]]*[-*][[:space:]]+/, "", line)
      split(line, parts, /[[:space:]]+/)
      token = clean_token(parts[1])
      if (token ~ /^v/) print "index\t" token
    }
  '
}

is_canonical_version_token() {
  printf '%s\n' "$1" | grep -Eq '^v(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))+$'
}

check_version_governance() {
  baseline=$1
  commit=$2

  # Forward-only: compare only newly introduced formal slots. Existing legacy
  # tokens remain grandfathered and are never rewritten or revalidated here.
  git -C "$repo_root" show "$baseline:docs/PROJECT_STATE.md" 2>/dev/null |
    extract_formal_version_tokens > "$version_baseline_file" || true
  git -C "$repo_root" show "$commit:docs/PROJECT_STATE.md" 2>/dev/null |
    extract_formal_version_tokens > "$version_tip_file" || true
  sort -u "$version_baseline_file" > "$version_baseline_sorted_file"
  sort -u "$version_tip_file" > "$version_tip_sorted_file"
  comm -23 "$version_tip_sorted_file" "$version_baseline_sorted_file" > "$version_new_file"

  while IFS="$(printf '\t')" read -r location token || [ -n "${location}${token}" ]; do
    [ -n "$token" ] || continue
    if ! is_canonical_version_token "$token"; then
      fail "Push rejected: version governance requires a new formal token to be canonical numeric; found $token in $location."
    fi
  done < "$version_new_file"
}

resolve_commit() {
  git -C "$repo_root" rev-parse --verify "$1^{commit}" 2>/dev/null
}

read_trailer() {
  commit=$1
  git -C "$repo_root" show -s --format=%B "$commit" |
    git -C "$repo_root" interpret-trailers --parse > "$trailer_file"

  trailer_count=0
  trailer_value=""
  while IFS= read -r trailer_line || [ -n "$trailer_line" ]; do
    case "$trailer_line" in
      Project-State-Review:*)
        trailer_count=$((trailer_count + 1))
        case "$trailer_line" in
          "Project-State-Review: updated") trailer_value=updated ;;
          "Project-State-Review: verified-current") trailer_value=verified-current ;;
          *) fail "Project-State-Review trailer on $commit must have a valid value." ;;
        esac
        ;;
    esac
  done < "$trailer_file"

  [ "$trailer_count" -eq 1 ] || fail "Commit $commit must contain exactly one Project-State-Review trailer."

  printf '%s\n' "$trailer_value"
}

record_branch_expectation() {
  commit=$1
  expected=$2
  remote_ref=$3
  printf '%s\t%s\t%s\n' "$commit" "$expected" "$remote_ref" >> "$expected_file"
}

check_branch_conflicts() {
  awk -F '\t' '
    !($1 in first_expected) { first_expected[$1] = $2; next }
    first_expected[$1] != $2 { conflicted[$1] = 1 }
    END { for (commit in conflicted) print commit }
  ' "$expected_file" > "$conflict_file"

  [ ! -s "$conflict_file" ] || {
    while IFS= read -r commit; do
      printf 'Push rejected: conflicting Project-State-Review expectations for commit %s:\n' "$commit" >&2
      awk -F '\t' -v commit="$commit" '$1 == commit { printf "  %s: %s\n", $3, $2 }' "$expected_file" >&2
    done < "$conflict_file"
    exit 1
  }
}

cat > "$input_file"
[ -s "$input_file" ] || exit 0

while IFS=' ' read -r local_ref local_oid remote_ref remote_oid extra ||
  [ -n "${local_ref}${local_oid}${remote_ref}${remote_oid}${extra}" ]; do
  [ -n "$local_ref" ] || continue
  [ -n "$local_oid" ] && [ -n "$remote_ref" ] && [ -n "$remote_oid" ] && [ -z "$extra" ] ||
    fail "Push rejected: malformed pre-push input line."

  if is_zero_oid "$local_oid"; then
    continue
  fi

  case "$remote_ref" in
    refs/heads/*)
      commit=$(resolve_commit "$local_oid") ||
        fail "Push rejected: local ref $local_ref does not resolve to a commit."

      if is_zero_oid "$remote_oid"; then
        baseline=$(git -C "$repo_root" hash-object -t tree /dev/null)
      else
        baseline=$(resolve_commit "$remote_oid") ||
          fail "Push rejected: remote commit $remote_oid is unavailable locally; synchronize local Git objects and retry."
      fi

      check_version_governance "$baseline" "$commit"

      if git -C "$repo_root" diff --quiet --no-ext-diff "$baseline" "$commit" -- docs/PROJECT_STATE.md; then
        expected=verified-current
      else
        expected=updated
      fi

      record_branch_expectation "$commit" "$expected" "$remote_ref"
      ;;
    refs/tags/*)
      commit=$(resolve_commit "$local_oid") ||
        fail "Push rejected: tag $local_ref must peel to a commit."
      printf '%s\t%s\n' "$commit" "$remote_ref" >> "$tag_file"
      ;;
    *)
      fail "Push rejected: unsupported ref namespace $remote_ref."
      ;;
  esac
done < "$input_file"

check_branch_conflicts

tab=$(printf '\t')
while IFS="$tab" read -r commit expected remote_ref; do
  actual=$(read_trailer "$commit")
  [ "$actual" = "$expected" ] ||
    fail "Push rejected: commit $commit has Project-State-Review: $actual; expected $expected for $remote_ref."
done < "$expected_file"

while IFS="$tab" read -r commit remote_ref; do
  read_trailer "$commit" >/dev/null
done < "$tag_file"
