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

`AGENTS.md`, `CONTRIBUTING.md` and `SECURITY.md` are upstream's. Each now opens with a short note for this
fork (report vulnerabilities privately here, and to Nous too when upstream has the flaw; contribute through
pull requests here), and otherwise describes Nous Research's process. Coding agents read `AGENTS.md` files
automatically, so its code rules (size ratchets, profile-scope rules, `scripts/run_tests.sh`) still shape
changes made here.

## Our changes

Record each feature that departs from upstream here, with the upstream files it touches.

### Installs, updates and links point at this repository

So that installing or updating this fork never fetches Nous Research's version instead:

- `hermes_cli/distribution.py` (new) names this repository, its installer URLs and its issue tracker, for
  the Python code below.
- **Installers**: `scripts/install.sh`, `install.ps1` and `install.cmd` clone this repository by default
  (`HERMES_REPO_URL` still overrides) and fetch each other from it.
- **`hermes update`**: `hermes_cli/update_cmd_git.py` treats checkouts of this repository as the
  distribution's own, so their users are no longer asked to add Nous's repository as `upstream` (syncing
  upstream is the maintainers' job, above). Its repair hints, and the reinstall hints in `update_cmd.py`,
  `update_cmd_maint.py`, `update_cmd_zip.py`, `uninstall.py` and `hermes_constants.py`, name this
  repository's installers. A ZIP update with no recorded source downloads this repository.
- **Desktop app**: the first-run bootstrap (`apps/desktop/electron/bootstrap-runner.ts`, and the Tauri
  installer's `install_script.rs`) downloads the install script from this repository at the app's own
  commit. `electron-builder.config.cjs` publishes to, and so updates from, this repository's releases.
  Release-notes, commit, installer and issue links, `package.json` and the desktop README point here.
- **Docker and Nix**: `docker-compose.windows.yml` builds from the checkout like `docker-compose.yml`, instead
  of pulling Nous's published image; the Nix packages' `homepage` points here.
- **Docs**: the docs site's repository, "edit this page", GitHub, issue and download links
  (`website/docusaurus.config.ts`); the install and clone commands in the README and its translations, the
  docs pages that show them (English and zh-Hans), and the bundled `hermes-agent` skill. The README files
  open with a note saying this is a fork.

Deliberately still upstream's:

- **Nous Research's release infrastructure.** `hermes_cli/source_releases.OFFICIAL_REPOSITORY` and the
  installers' stable-channel checks keep naming Nous's repository. This fork publishes no releases, so its
  checkouts follow `main` (the code's existing rule for forks). Packaged desktop builds, the Termux APT
  package and the stable/canary channels are Nous's; this fork doesn't build them yet.
- **Nous's services**, which are product features: Nous Portal sign-in, inference and billing, the Tool
  Gateway, the plugin catalog and Skills Hub, and the opt-in telemetry endpoint (off unless a user consents).
- **Documentation links** to `hermes-agent.nousresearch.com/docs` throughout the CLI, app and docs. Those pages
  still describe this code; repoint them once this fork hosts its own docs (the site's `url` and `baseUrl`
  are unchanged for that reason).
- **Packaging identity**: the desktop app's signing publisher, MSIX identity and Linux package maintainer
  ("Nous Research"). Builds of this fork need their own certificates and maintainer before publishing.

### Diagnostics stay on the machine running Hermes

Upstream uploads debug reports: `hermes debug share` to paste.rs (dpaste.com as fallback), `--nous` and
the desktop's "Send diagnostics" to Nous's support portal, chat `/debug` to a paste link. This fork uploads
nothing. Every surface saves the same redacted report + full logs as an owner-only zip under the
profile's `logs/debug-reports/` and reports its path:

- `hermes_cli/debug_archive.py` (new) writes the archive. `hermes_cli/debug.py` lost the paste and Nous
  upload code (`upload_to_pastebin`, `build_debug_share`, `build_nous_bundle` and the rest);
  `hermes_cli/diagnostics_upload.py` is deleted. Removing them, rather than only their callers, makes an
  upstream merge that adds a new upload call fail loudly instead of uploading.
- `hermes debug share` saves the archive (`--local` still prints the report); `--nous`, `--expire` and
  `--yes` are gone (`hermes_cli/subcommands/debug.py`). `hermes debug delete` and the hourly sweep stay:
  they only delete pastes that an earlier version uploaded.
- CLI `/debug` (`cli_commands_mixin.py`), chat `/debug` (`gateway/slash_commands.py`), the dashboard's
  `POST /api/ops/debug-share` (`hermes_cli/web_routers/status.py`) and the desktop RPC, renamed
  `diagnostics.save` (`tui_gateway/methods_config.py`, contracts regenerated), save locally.
- UI: the desktop's "Save diagnostics" dialog, update-error report and maintenance action, and the web
  dashboard's System page show the saved path. The rewritten desktop strings fall back to English in the
  other languages (`apps/desktop/src/i18n/overlay-gaps.json`); the chat strings are translated in all 17
  gateway languages (`locales/*.yaml`).
- Docs: the CLI and slash-command references (English and zh-Hans), the desktop guide and the
  command-parity table.

### Memory storage: local, GCS or S3/MinIO

`memory.storage` (config.yaml) chooses where built-in `MEMORY.md` / `USER.md` live: `local` (upstream's
behaviour, the default), `gcs`, or `s3` (MinIO, AWS S3, R2). With a bucket, the bucket holds the truth
and `memories/` is a cache; every write is conditional (GCS generation / S3 `If-Match`) and a lost race
is re-applied to the newer copy, so two pods sharing a bucket never silently drop each other's
entries. Documented in `website/docs/user-guide/configuration.md#memory-storage`.

- `tools/memory_storage.py` (new): settings, the mirror, `reset_memory_files`; `tools/memory_storage_gcs.py`
  (JSON API; metadata-server or key-file credentials) and `tools/memory_storage_s3.py` (SigV4), both
  standard library + `cryptography`, so no new dependencies.
- `tools/memory_tool_store.py`: `MemoryStore` takes the mirror; `load_from_disk` pulls first;
  `_mutate` is now a retry loop around `_mutate_locked` (the old body) with a conditional push before
  the local write. `tools/memory_tool.py` and `agent/agent_init.py` build the mirror from config; a bad
  setting turns memory off (logged) instead of writing local files the bucket would undo.
- `hermes memory reset` (`hermes_cli/main_agent_cmds.py`) and `POST /api/memory/reset`
  (`hermes_cli/web_routers/ops.py`) delete the bucket copy too.
- Credentials are read through `agent.secret_scope` (profile `.env`, then the environment), never
  config.yaml. The keys are not in `DEFAULT_CONFIG` (a data module at its size cap); `storage_settings`
  supplies the defaults.

### Kubernetes: Helm chart

`deploy/helm/tuos/` (new) runs the Docker image as a one-pod StatefulSet. Guide:
`website/docs/user-guide/kubernetes.md` (new; listed in `website/sidebars.ts`). No upstream code changes.

- The gateway is the container's main program (s6 supervises it); `/opt/data` is a volume claim that
  outlives `helm uninstall`.
- The pod's environment comes from a Secret: the user's own, or one the chart makes from `secrets.env`.
- Helm's `config` value is mounted as the managed `config.yaml` through `HERMES_MANAGED_DIR`, at
  `/etc/hermes-managed` because the image keeps build facts in `/etc/hermes`. That is how
  `memory.storage` (GCS through Workload Identity, or MinIO) is set declaratively.
- The dashboard runs as the image's s6 service, on loopback (reached with `kubectl port-forward`) unless
  `dashboard.expose` puts it behind a Service, where it requires a login.
- The pod starts as root, as the image requires, and does not mount a service-account token: the agent's
  shell commands run in this pod.

### Rebranded as tuos

What people see calls the product **tuos** (lowercase). Internal names stay Hermes's, so upstream merges and
existing installs keep working: Python packages, `HERMES_*` variables, `~/.hermes`, service and unit names,
the desktop app's packaging identity, and the `hermes` command.

- **The rule**: `brand()` in `hermes_cli/distribution.py` and its TypeScript twin in `apps/shared/src/brand.ts`
  (keep them identical; both are tested). In user-facing copy, "Hermes Agent" and "Hermes" become "tuos",
  except:
  - "Hermes Cloud", Nous's hosted service;
  - Nous model names such as "Hermes 3";
  - the wake word "Hey Hermes";
  - credit to upstream ("built on / based on Hermes Agent").
- **Applied where copy is loaded, not in the strings themselves**, so upstream's strings merge untouched and
  its new ones are rebranded too:
  - Gateway messages, and the translations the TUI fetches from the backend: `agent/i18n.py` `_load_bundled`.
  - Desktop:
    - `apps/desktop/src/i18n/en.ts` and `define-locale.ts`;
    - runtime packs in `registry.ts`;
    - plugin strings in `plugin-i18n.ts`.
  - Web dashboard: `web/src/i18n/en.ts` and `context.tsx`.
  - TUI: its English in `ui-tui/src/i18n/en.ts`, packs in `runtime.ts`.
  - CLI help: `HermesArgumentParser.format_help` in `hermes_cli/_parser.py`. Its `prog` is now `tuos`.
  - The dashboard's sign-in pages: `hermes_cli/dashboard_auth/login_page.py`.
- **The agent's identity**: "You are tuos, built on Nous Research's open-source Hermes Agent."
  - Set by `brand_identity()` in a block at the end of `agent/prompt_builder.py`. The same block brands the
    help guidance and the TUI and desktop surface hints.
  - Also in `hermes_cli/default_soul.py`, `SOUL.md` and `docker/SOUL.md`.
  - Hermes's default persona is now listed as an auto-seeded legacy text. A SOUL.md nobody edited moves to
    tuos; one a user wrote stays.
- **CLI and TUI look**:
  - The built-in skins that carried Hermes's branding say tuos, with ◆ in place of ☤
    (`hermes_cli/skin_engine.py`).
  - Banner art: `hermes_cli/brand_art.py` (new) holds the wordmark and emblem that `banner.py` falls back to,
    and `ui-tui/src/banner.ts` draws the same.
  - Version labels: `banner.py`, `_startup_fast.py`.
  - The TUI's default brand, taglines and attribution: `theme.ts`, `components/branding.tsx`,
    `i18n/en/chatBits.ts`.
- **The `tuos` command** hands off to `hermes` rather than being a second entry point: gateway, update and
  restart checks recognise processes by the `hermes` executable (`gateway/status.py`).
  - `hermes_cli/_launchers.py` publishes it with the other commands. On POSIX, `~/.local/bin/tuos` execs the
    install's hermes launcher, the same mechanism as the `hermes-agent` forwarder (now the `_FORWARDERS`
    table). On Windows, `tuos.cmd` sits beside `hermes.exe` in `%HERMES_HOME%\bin`.
  - The Docker image has `/opt/hermes/bin/tuos` (`docker/tuos.sh`, `Dockerfile`).
  - Shell completion covers it (`completion.py`), and uninstall removes it (`uninstall.py`).
  - pip and Nix installs have only `hermes`.
- **Desktop and web literals**:
  - Desktop window titles, tray, notification fallbacks and browser tab titles.
  - The intro wordmark, now lowercase: `.wordmark` lost its `text-transform`.
  - The boot-failure page, and a few onboarding and quick-entry messages.
  - The dashboard's `<title>`, and the default Telegram bot name (`web/`, `telegram_managed_bot.py`,
    `web_routers/messaging.py`).
- **Docs and README**: the docs site's title and navbar (`website/docusaurus.config.ts`, without Hermes's
  logo), and the README's title and opening.

Not rebranded yet:
- English hard-coded outside the catalogs: about 1,500 Python strings (setup wizard, doctor, status output,
  errors), and roughly 300 literals in the desktop renderer and Electron main process.
- The desktop app's packaging identity (`product-identity.cjs`): app and executable name, appId, MSIX
  identity, the macOS menu's app name and the About panel. That belongs with this fork's own builds and
  signing.
- Docs pages, translated READMEs, favicons and images, and the TUI's translated taglines.

### Memory sharing per agent: shared, per_user, hybrid

`memory.sharing` in a profile's config.yaml decides whose `MEMORY.md` / `USER.md` a conversation uses:

- `shared` is upstream's behaviour and the default.
- `per_user` gives each messaging user their own pair of files.
- `hybrid` shares the agent's `MEMORY.md` and gives each user their own `USER.md`.

The operator (CLI, TUI, desktop, their own cron jobs) keeps the profile's `memories/` files. A user's files live
in `memories/users/<platform>/<id>/`. A group or thread session shared by its members is owned by the chat:
`memories/chats/<platform>/<chat>[/<thread>]/`, since no single member's memory may load into it. Documented
in `website/docs/user-guide/configuration.md#memory-sharing`.

- `tools/memory_sharing.py` (new) holds the logic:
  - the setting, and the owner, derived from the identity the gateway already gives the agent (DM, or the
    session key ending in the participant id);
  - folders and store construction;
  - `owner_for_agent`: a cron job's owner, then the store's (review forks share it), then identity, then the
    delegating parent's;
  - the viewer filter for pending writes;
  - `OwnerScopedSessions`, the session view `session_search` gets.
- Upstream hooks, each small:
  - `tools/memory_tool_store.py`: the store has an owner, and `_path_for` uses its folder.
  - `tools/memory_tool.py`: `load_on_disk_store(owner)`; staged writes carry their owner, and approval applies
    them there.
  - `tools/memory_storage.py`: bucket keys use the path under `memories/`, so users never share an object.
  - `agent/agent_init.py`: the store comes from `store_for_agent`.
  - `agent/inline_tool_executors.py`: `session_search` gets the viewer.
  - `tools/session_search_tool.py`: a scoped view, and no cross-profile reads.
  - `tools/write_approval.py`: pending memory writes are filtered to the viewer.
  - `gateway/slash_commands.py`: `/memory` runs as the sender.
  - `tools/cronjob_job_args.py`: a job made in a chat records `origin.memory_owner`.
  - `cron/scheduler.py`: the job's agent takes that owner; the line count is unchanged.
  - `hermes memory reset --user platform:id` (`hermes_cli/subcommands/memory.py`, `main_agent_cmds.py`).
- Not per user: skills, and external memory providers, which scope users themselves.
