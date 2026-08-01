#!/bin/sh
set -eu

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  printf '%s\n' 'Project State Push Gate installation must run inside a Git work tree.' >&2
  exit 1
}

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

local_hooks_path=$(git config --local --get core.hooksPath 2>/dev/null || true)
effective_hooks_path=$(git config --show-origin --get core.hooksPath 2>/dev/null || true)

if [ -n "$effective_hooks_path" ]; then
  printf 'Detected effective core.hooksPath: %s\n' "$effective_hooks_path"
else
  printf '%s\n' 'Detected effective core.hooksPath: unset.'
fi

if [ "$local_hooks_path" = ".githooks" ]; then
  [ -x "$repo_root/.githooks/pre-push" ] || {
    printf '%s\n' 'Project State Push Gate pre-push hook is not executable.' >&2
    exit 1
  }
  [ -x "$repo_root/scripts/check-project-state-push.sh" ] || {
    printf '%s\n' 'Project State Push Gate check script is not executable.' >&2
    exit 1
  }
  printf '%s\n' 'Project State Push Gate is already installed through local core.hooksPath=.githooks.'
  exit 0
fi

if [ -n "$effective_hooks_path" ]; then
  printf 'Project State Push Gate installation stopped: effective core.hooksPath is already configured (%s). Integrate manually; nothing was changed.\n' "$effective_hooks_path" >&2
  exit 1
fi

hooks_dir=$(git rev-parse --git-path hooks)
if [ -d "$hooks_dir" ]; then
  for hook in "$hooks_dir"/*; do
    [ -e "$hook" ] || continue
    case "$(basename "$hook")" in
      *.sample) ;;
      *)
        printf 'Project State Push Gate installation stopped: existing custom hook %s found. Integrate manually; nothing was changed.\n' "$hook" >&2
        exit 1
        ;;
    esac
  done
fi

[ -x "$repo_root/.githooks/pre-push" ] || {
  printf '%s\n' 'Project State Push Gate pre-push hook is not executable.' >&2
  exit 1
}
[ -x "$repo_root/scripts/check-project-state-push.sh" ] || {
  printf '%s\n' 'Project State Push Gate check script is not executable.' >&2
  exit 1
}

git config --local core.hooksPath .githooks
printf '%s\n' 'Project State Push Gate installed with local core.hooksPath=.githooks.'
