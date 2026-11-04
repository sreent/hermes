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
git merge upstream/main          # resolve conflicts (see below), run the tests, open a PR
```

Merge pull requests into `main` with a **merge commit, not a squash**. Squashing replaces upstream's commits
with new ones, so the next `git merge upstream/main` would re-apply everything since the import and
conflict throughout.

The more files we change, the more each sync conflicts. Where we can, add new modules next to upstream's
rather than editing upstream files heavily, and list each change below.

### Keeping removed files out

A merge brings back any file upstream **adds** under a folder we deleted, with no conflict to warn us, and
stops with a modify/delete conflict on any deleted file upstream **changed**. After each merge, before
committing:

```bash
# Upstream's GitHub automation stays out of this fork (the blob-size allowlist is a lint input we keep).
git ls-files .github | grep -v '^.github/blob-size-allowlist.txt$' | xargs -r git rm -q
git rm -q --ignore-unmatch .coderabbit.yaml
git status --short | grep -E '^(DU|UD) '   # other deleted files upstream changed: `git rm` each one
```

Then run `python scripts/check` and `scripts/run_tests.sh tests/ci tests/scripts`. A new upstream test
that reads a workflow file fails with `FileNotFoundError` on a `.github/...` path; delete that test the
same way as below.

## Removed from upstream

Nous Research's project automation, which does nothing useful in this repository:

- **`.github/`**, except `blob-size-allowlist.txt` (read by the blob-size guard in `scripts/check`):
  - 58 GitHub Actions workflows. 52 of them ran on Blacksmith runners, a paid service Nous uses that this
    repository doesn't have. Among them are workflows that publish releases, deploy Nous's docs site,
    push Docker images and push autofix commits.
  - The composite actions and helper scripts those workflows called.
  - Nous's issue and pull request templates, `CODEOWNERS` (Nous maintainers), `dependabot.yml` and the
    actionlint config.
- **`.coderabbit.yaml`**: configuration for the CodeRabbit review bot Nous uses.
- **Tests of those workflow files**, which read them from disk and so can't pass without them:
  - 18 files in `tests/ci/` whose tests mostly or entirely check workflow definitions, plus the three
    helper modules only they used (`workflow_steps.py`, `_gha_expr.py`, `desktop_release_roles.py`).
  - The individual workflow-reading tests in `tests/ci/test_classify_changes.py`,
    `test_desktop_release_tag_admission.py`, `test_e2e_tmux_required.py`, `test_live_comment.py`,
    `test_windows_update_crash_oracles.py`, and `tests/scripts/test_desktop_build_cache.py`,
    `test_dispatch_log.py`, `test_release_artifacts.py`, `test_termux_build_driver.py`. The rest of each
    file still runs.
  - `tests-js/setup-pm-cache.test.mjs` and `setup-pm-post.test.mjs`, which loaded the deleted actions.

Deliberately kept, although they serve Nous's release process, because code we keep imports them:

- `scripts/releases/` is imported by `hermes_cli/release_channels.py` (the update-channel logic) and by
  the bundle builders in `scripts/bundles/`.
- `scripts/ci/` holds the guards `scripts/check` runs, next to helpers only the removed workflows used.
- `contributors/` feeds the release-notes tooling in `scripts/releases/authors.py`.

We have no CI of our own yet: run `python scripts/check` and `scripts/run_tests.sh` locally before merging.

## Upstream process documents

`AGENTS.md`, `CONTRIBUTING.md` and `SECURITY.md` describe Nous Research's process, including where to
report security issues (to Nous, for upstream code). They apply to upstream; update them here as our own
process takes shape. Coding agents read `AGENTS.md` files automatically, so its code rules (size ratchets,
profile-scope rules, `scripts/run_tests.sh`) still shape changes made here.

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
