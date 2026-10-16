#!/usr/bin/env bash
# 全作例を最新の mokume で組む。CI の build ジョブの中身で、手元でも同じに走る。
#
# 作例は Package.resolved を持たず `from:` で追随するので、組むたびに最新のリリースを解決する。
# macOS の runner の枠を mokume 本体の CI と分け合っているため、作例ごとにジョブを分けず
# 1 本で逐次に組み、scratch path を共有して mokume のビルドを 1 回で済ませる。
set -uo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$root/.build/shared"

examples=()
for manifest in "$root"/*/Package.swift; do
  [[ -e "$manifest" ]] || continue
  examples+=("$(basename "$(dirname "$manifest")")")
done

if [[ ${#examples[@]} -eq 0 ]]; then
  echo "作例なし"
  exit 0
fi

failed=()
for name in "${examples[@]}"; do
  echo "::group::$name"
  if ! swift build --package-path "$root/$name" --scratch-path "$scratch"; then
    failed+=("$name")
  fi
  echo "::endgroup::"
done

# 解決した版。scratch path を共有しているので、全作例で同じ版になる
version="$(python3 -c '
import json, sys
deps = json.load(open(sys.argv[1]))["object"]["dependencies"]
print(next(d["state"]["checkoutState"]["version"] for d in deps if d["packageRef"]["identity"] == "mokume"))
' "$scratch/workspace-state.json" 2>/dev/null)"
echo "mokume: ${version:-不明}"

if [[ ${#failed[@]} -gt 0 ]]; then
  echo "組めなかった作例 (${#failed[@]}/${#examples[@]}):" >&2
  printf '  %s\n' "${failed[@]}" >&2
  exit 1
fi
echo "全 ${#examples[@]} 本が組めた"
