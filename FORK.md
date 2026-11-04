# About this fork

This repository started as a full copy of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent),
with its complete git history, so upstream fixes can still be merged in while we build our own features.

| | |
|---|---|
| Upstream | `https://github.com/NousResearch/hermes-agent` |
| Imported from | `main` at `cad0aaaf0d77ffa4899ebf0d3db8bae7a6b5147f` (2026-11-04) |
| Licence | MIT. Keep `LICENSE` and its Nous Research copyright notice in every copy. |

Notes about the fork live in this file rather than in `README.md`, so upstream changes to the README merge
without conflicts.

## Pulling upstream changes

```bash
git remote add upstream https://github.com/NousResearch/hermes-agent.git   # once per clone
git fetch upstream main
git checkout -b sync/upstream-$(date +%Y%m%d)
git merge upstream/main          # resolve conflicts, run the tests, open a PR
```

Merge pull requests into `main` with a **merge commit, not a squash**. Squashing replaces upstream's commits
with new ones, so the next `git merge upstream/main` would re-apply everything since the import and
conflict throughout.

The more files we change, the more each sync conflicts. Where we can, add new modules next to upstream's
rather than editing upstream files heavily, and list each change below.

## GitHub Actions inherited from upstream

`.github/workflows/` holds upstream's 58 workflows, unchanged. Before the first pull request into `main`,
decide which of them to keep:

- **52 of them use Blacksmith runners** (`runs-on: blacksmith-*`), a paid runner service Nous uses.
  Our repo has no such runners, so those jobs stay queued until GitHub cancels them after 24 hours.
  They cost nothing, but they show up as stuck checks on pull requests.
- Pushes to feature branches start none of them: push-triggered workflows only run on `main`, and the
  one exception (`live-providers.yml`) skips its job outside `NousResearch/hermes-agent`.
- Every pull request starts `ci.yaml` and `nix.yml`. `pm-bundle.yml`, `termux-verify.yml`,
  `plugin-catalog-ci.yml` and `windows-bundle-sdk.yml` start only when their paths change, and
  `label-rerun.yml` only when a label is added.
- Once merged into `main`, `canary-release.yml` is scheduled daily and `js-autofix.yml` runs when a push to
  `main` changes JavaScript or TypeScript. Both use Blacksmith runners, so they would sit queued too.

Options: turn Actions off under Settings → Actions → General until we have our own CI, or delete the
workflows we don't want (each upstream change to a deleted workflow then needs a `git rm` during the sync).

## Upstream process documents

`AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md` and the `.github` issue and PR templates describe Nous
Research's process, including where to report security issues (to Nous, for upstream code). They apply to
upstream; update them here as our own process takes shape. Coding agents read `AGENTS.md` files
automatically, so its code rules (size ratchets, profile-scope rules, `scripts/run_tests.sh`) still
shape changes made here.

## Our changes

None yet. Record each feature that departs from upstream here, with the upstream files it touches.

Planned: configurable memory sharing per agent (`shared`, `per_user`, `hybrid`). The upstream code that
currently ties memory to a profile rather than to a user:

- `tools/memory_tool.py` `get_memory_dir()`: MEMORY.md and USER.md always live under the profile home.
- `agent/agent_init.py` `_init_memory()`: builds and loads the store; the agent already has `user_id`,
  `chat_type` and `thread_id` here.
- `tools/memory_tool.py` `load_on_disk_store()`: the gateway approval and `/memory` paths load the store
  without an agent.
- `tools/session_search_tool.py` `session_search()`: searches every session with no user filter, although
  the `sessions` table stores `user_id`.
- Skills under the profile home are shared by everyone who talks to the profile.
- Background review and flush agents write memory after a turn, and must run as the same user.
- In a shared group or thread session the agent is built once, with the first sender's `user_id`.
