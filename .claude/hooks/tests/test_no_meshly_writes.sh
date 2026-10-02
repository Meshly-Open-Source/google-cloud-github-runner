#!/bin/bash
# Tests for no-meshly-writes.sh — both directions.
#
# The approve half is load-bearing: an agent here legitimately needs to READ
# meshly-infra to know what the consumer expects of this fork. If reads were
# blocked the guard would be routed around on the first lookup, and a guard
# that is routed around once is routed around always.

HOOK="$(dirname "$0")/../no-meshly-writes.sh"
PASS=0; FAIL=0

run() { printf '{"tool_input":{"command":%s}}' "$(jq -Rn --arg c "$1" '$c')" | bash "$HOOK" 2>/dev/null; }
expect() {
  local want="$1" cmd="$2" desc="$3" got
  got=$(run "$cmd" | jq -r '.decision' 2>/dev/null)
  if [[ "$got" == "$want" ]]; then PASS=$((PASS+1)); else
    FAIL=$((FAIL+1)); echo "  FAIL: $desc"; echo "        cmd: $cmd"; echo "        wanted $want got ${got:-<unparseable>}"
  fi
}

echo "--- must BLOCK: git writes into a meshly repo"
expect block "cd /home/jw/dev/meshly && git commit -m x"            "commit in meshly root"
expect block "git -C /home/jw/dev/meshly/meshly-infra commit -m x"  "commit via -C"
expect block "cd ~/dev/meshly/.wt-mgr-compose && git add -A"        "add in a meshly worktree"
expect block "git -C meshly-infra push"                             "push to a submodule"
expect block "cd /home/jw/dev/meshly && git checkout main"          "checkout in meshly"
expect block "cd .wt-2431-fix && git stash"                         "stash in a .wt- worktree"
expect block "git -C /home/jw/dev/meshly submodule update"          "submodule update"

echo "--- must BLOCK: filesystem writes into a meshly repo"
expect block "rm -rf /home/jw/dev/meshly/var/tmp"                   "rm"
expect block "cp a.txt /home/jw/dev/meshly/etc/"                    "cp into meshly"
expect block "mv x ~/dev/meshly/scripts/"                           "mv into meshly"
expect block "mkdir /home/jw/dev/meshly/newdir"                     "mkdir"
expect block "sed -i s/a/b/ /home/jw/dev/meshly/CLAUDE.md"          "in-place sed"
expect block "chmod +x /home/jw/dev/meshly/scripts/x.sh"            "chmod"
expect block "tee /home/jw/dev/meshly/out.txt"                      "tee"
expect block "echo hi > /home/jw/dev/meshly/out.txt"                "redirect into meshly"

echo "--- must APPROVE: READS of meshly repos (the guard must not block these)"
expect approve "git -C /home/jw/dev/meshly/meshly-infra status --short"  "git status"
expect approve "git -C /home/jw/dev/meshly log --oneline -5"             "git log"
expect approve "git -C /home/jw/dev/meshly diff --name-only"             "git diff"
expect approve "git -C /home/jw/dev/meshly show HEAD:CLAUDE.md"          "git show"
expect approve "git -C /home/jw/dev/meshly ls-tree HEAD"                 "git ls-tree"
expect approve "cat /home/jw/dev/meshly/CLAUDE.md"                       "cat"
expect approve "grep -rn runner /home/jw/dev/meshly/meshly-infra/"       "grep"
expect approve "ls /home/jw/dev/meshly/.wt-mgr-compose"                  "ls"
expect approve "find /home/jw/dev/meshly -name '*.tf'"                   "find"
expect approve "head -20 ~/dev/meshly/meshly-infra/justfile"             "head"
expect approve "wc -l /home/jw/dev/meshly/AGENTS.md"                     "wc"

echo "--- must APPROVE: writes inside THIS repo"
expect approve "git commit -m 'work in the fork'"                   "commit here"
expect approve "git add -A"                                          "add here"
expect approve "git push origin meshly/ipfilter"                     "push here"
expect approve "rm -f /tmp/scratch.txt"                              "rm in tmp"
expect approve "mkdir -p ipfilter/tests"                             "mkdir here"
expect approve "sed -i s/a/b/ README.md"                             "sed here"
expect approve "echo x > /tmp/out.txt"                               "redirect to tmp"
expect approve "python -m pytest -c ipfilter/pytest.ini ipfilter/tests" "run the tests"

echo "--- must APPROVE: a meshly path merely MENTIONED, not written"
expect approve "grep -rn 'rm -rf /home/jw/dev/meshly' docs/"         "the string inside a grep"
expect approve "echo 'do not git commit in /home/jw/dev/meshly'"     "a warning in an echo"
expect approve "git commit -m 'note: meshly-infra consumes this'"    "meshly named in a message"

echo "--- escape hatch"
expect approve "MESHLY_WRITE_INTENDED=1 git -C /home/jw/dev/meshly commit -m x" "inline override"
if [[ "$(MESHLY_WRITE_INTENDED=1 run 'git -C /home/jw/dev/meshly commit -m x' | jq -r .decision)" == "approve" ]]; then
  PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "  FAIL: exported override"; fi

echo "--- envelope and message quality"
for c in "git -C /home/jw/dev/meshly commit -m x" "ls" ""; do
  run "$c" | jq -e '.decision | test("^(approve|block)$")' >/dev/null 2>&1 \
    && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "  FAIL: envelope for: $c"; }
done
msg=$(run "git -C /home/jw/dev/meshly commit -m x" | jq -r .reason)
for needle in "just export-handoff" "MESHLY_WRITE_INTENDED" "Reads are fine"; do
  [[ "$msg" == *"$needle"* ]] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "  FAIL: message omits '$needle'"; }
done

echo
echo "PASS=$PASS FAIL=$FAIL"
[[ "$FAIL" -eq 0 ]]
