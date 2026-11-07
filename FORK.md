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

### Renamed copy

`scripts/fork/rename.py` renames the copy written into upstream's code and docs ("Rebranded as tuos"), so
a merge conflicts wherever upstream changed a line we renamed, and brings in upstream's new strings
unrenamed. Let the script handle both:

```bash
npm ci                                     # once per clone: the apps' half parses TypeScript
git merge upstream/main
python scripts/fork/rename.py --resolve    # settle the conflicts the rename caused, then rename again
```

`--resolve` takes upstream's side of each conflicted file whose only change on our side is the rename
(Python tests included), then renames everything again. It lists the conflicted files it left: they carry other changes of ours
too. Resolve those by hand, taking upstream's wording in renamed lines, and run the script again.

The script exits with status 3 when the rename would break a match: text renamed in one place that code
elsewhere compares against, searches for or lists, or that a regular expression in the desktop app or
TUI reads from a backend message. Keep that wording (`KEEP` in `rename.py` or `rename_ts.mjs`) or make the
matcher accept both (as `hermes_cli/console_engine.py` does), rerun until it exits 0, and commit with the
merge. `python scripts/fork/rename.py --check` exits 1 while anything is left to rename.

### Keeping removed files out

A merge brings back any file upstream **adds** under a folder we deleted, with no conflict to warn us, and
stops with a modify/delete conflict on any deleted file upstream **changed**. After each merge, before
committing:

```bash
# Upstream's GitHub automation stays out of this fork. Ours is .github/workflows/tuos-*.yml ("Hosted by
# this fork"); the blob-size allowlist is a lint input we keep.
git ls-files .github | grep -Ev '^\.github/(blob-size-allowlist\.txt|workflows/tuos-[^/]*\.yml)$' | xargs -r git rm -q
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

Our own workflows (`.github/workflows/tuos-*.yml`, "Hosted by this fork") build and publish; none runs the
tests or the lint checks yet, so run `python scripts/check` and `scripts/run_tests.sh` locally before merging.

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
  installers' stable-channel checks keep naming Nous's repository, so installs from source follow `main`
  (the code's existing rule for forks) even after this fork tags a release. The Termux APT package, the
  stable/canary channels and the setup installer (`apps/bootstrap-installer`) are Nous's; this fork
  builds desktop apps only ("Hosted by this fork").
- **Nous's services**, which are product features: Nous Portal sign-in, inference and billing, the Tool
  Gateway, the plugin catalog and Skills Hub, and the opt-in telemetry endpoint (off unless a user consents).
- **Upstream's release tooling.** `scripts/release.py` and `scripts/releases/` name this fork's builds
  ("Rebranded as tuos", below) but drive Nous's pipeline: R2 uploads (`scripts/releases/r2.py`
  `DEFAULT_PUBLIC_URL`), channel feeds, App Installer descriptors and the Store. This fork releases with
  `tuos-desktop.yml` instead. `tests/install/` drives Nous's published installers and expects Hermes's
  names.

### Hosted by this fork

What Nous Research hosts for Hermes, this fork hosts for itself on GitHub, from workflows of its own
(`.github/workflows/tuos-*.yml`, kept out of the merge cleanup above):

- **Docs site**: `https://sreent.github.io/hermes` (`hermes_cli.distribution.DOCS_URL`), built from
  `website/` and published by `tuos-docs.yml` with GitHub Pages whenever `main` changes the site, the
  skills or the plugin catalog. Turn Pages on once: Settings, Pages, Source "GitHub Actions". Pages keep
  upstream's paths under the new base (`website/docusaurus.config.ts` `url` and `baseUrl`; the Skills
  Hub, Plugins and blueprint pages read their data from `baseUrl` too). Search is Algolia DocSearch only
  when the repository has the variables `DOCSEARCH_APP_ID`, `DOCSEARCH_API_KEY` and
  `DOCSEARCH_INDEX_NAME` (DocSearch is free for open-source docs); Nous's index lists Nous's pages, so
  until then there is no search box. The navbar's "Home", Nous's landing page, is gone.
- **Docker image**: `ghcr.io/sreent/tuos` (`hermes_cli.distribution.DOCKER_IMAGE`), built by
  `tuos-docker.yml` for amd64 and arm64 on GitHub's runners. A push to `main` publishes `main` and
  `latest`; a tag `vX.Y.Z` publishes that version; each has a `-desktop` twin with the bots' screens.
  `latest` follows `main`, as installs do, where Nous's means the newest stable release. The Helm chart
  runs `main` by default. After the first run, check that the package is public (the package's page,
  Package settings) so clusters can pull it without credentials.
- **Desktop apps**: pushing a tag `vX.Y.Z` runs `tuos-desktop.yml`, which builds the bundled app (the
  agent inside, as upstream releases it) with upstream's driver, `scripts/bundles/desktop.py`, and attaches
  the installers to a draft GitHub release of that tag (`hermes_cli.distribution.RELEASES_URL`). Publish
  the draft by hand; installed apps update from the newest published release.
  - macOS arm64, DMG and ZIP: signed and notarized when the secrets `CSC_LINK` and `CSC_KEY_PASSWORD` (a
    Developer ID Application certificate) and `APPLE_API_KEY_P8`, `APPLE_API_KEY_ID` and
    `APPLE_API_ISSUER` (an App Store Connect API key) are set. Without them the app is only ad-hoc
    signed: macOS makes people allow it in Privacy & Security, and it cannot update itself. Without
    Nous's R2 bucket the app reads its update feed (`stable-mac.yml`) from GitHub releases
    (`electron-builder.config.cjs` `mac.publish`).
  - Linux x64 and arm64, AppImage.
  - Windows x64, MSIX: built only when the repository has Azure Trusted Signing variables
    (`AZURE_SIGN_ENDPOINT`, `AZURE_SIGN_ACCOUNT`, `AZURE_SIGN_PROFILE`, `AZURE_SIGN_PUBLISHER`,
    `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, with a federated credential for this workflow), because
    Windows will not install an unsigned package. The MSIX publisher, `OUT_OF_STORE_PUBLISHER` in
    `scripts/msix-shared.mjs` (now `CN=tuos`), must equal the certificate's subject. No App Installer
    descriptor is published, so Windows installs do not update themselves.
  - A stable build needs a claim tag `rc.<N>-vX.Y.Z` (upstream's release gate, which also dates the
    Windows package version). `scripts/fork/release-claim.sh` makes it on each runner from the release
    commit and never pushes it.
- **`scripts/fork/relink.py`** rewrites upstream's references to what Nous hosts, wherever they are
  (code, tests, docs and the agent's prompt):
  - links into Nous's docs site go to the same page on ours. What Nous's site serves for its services
    stays: `/docs/api/` (the Skills Hub index, the plugin and model catalogs), `/docs/img/`, and the
    hub page the desktop app embeds. So does the rest of `hermes-agent.nousresearch.com`;
  - Nous's desktop download page becomes this repository's releases page;
  - the image `nousresearch/hermes-agent` becomes ours, and its Docker Hub page our package page. The
    same words inside a path name the repository and stay. `rename.py` runs it, and
  its `--resolve` treats relinked lines as ours, so syncing upstream needs no extra step; `relink.py
  --check` exits 1 while anything is left.

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
existing installs keep working: Python packages, `HERMES_*` variables, `~/.hermes` and the desktop app's
state folder, service and unit names, and the `hermes` command.

- **The rule**: `brand()` in `hermes_cli/distribution.py` and its TypeScript twin in `apps/shared/src/brand.ts`
  (keep them identical; both are tested). In user-facing copy, "Hermes Agent" and "Hermes" become "tuos",
  and so does the command where copy tells someone to run it (`hermes setup`, `` `hermes` ``), except:
  - "Hermes Cloud", Nous's hosted service;
  - Nous model names such as "Hermes 3";
  - the wake word "Hey Hermes";
  - credit to upstream ("built on / based on Hermes Agent");
  - paths, packages, modules and file or app names (`~/.hermes`, `hermes-agent`, `hermes_cli`,
    `hermes.exe`, `Hermes.app`, `Application Support/Hermes`);
  - "Hermes Local Signing", the macOS signing certificate's name in the keychain;
  - the `hermes` user and group the Docker image and the Nix module run as ("the `hermes` user",
    `sudo -u hermes`, `--user hermes`, `s6-setuidgid hermes`, `hermes:hermes`, "drops to hermes"), and
    the container the compose files name hermes (`docker exec hermes tuos ...`). The first rename turned
    these into `tuos` in 12 docs pages (`docker exec -u tuos ...` and `docker exec tuos ...` fail: there
    is no such user or container); they read `hermes` again.
  - The TUI's taglines credit upstream in every language ("Built on Hermes Agent by Nous Research"), and
    the rule recognises credit only in English, so `agent/i18n.py` and `ui-tui/src/i18n/runtime.ts`
    serve those two keys as translated (`CREDIT_KEYS`). Before, the translations still carried Hermes's
    "Messenger of the Digital Gods".
- **Applied where copy is loaded, not in the strings themselves**, so upstream's strings merge untouched and
  its new ones are rebranded too:
  - Gateway messages, and the translations the TUI fetches from the backend: `agent/i18n.py` `_load_bundled`.
  - Desktop:
    - `apps/desktop/src/i18n/en.ts` and `define-locale.ts`;
    - runtime packs in `registry.ts`;
    - plugin strings in `plugin-i18n.ts`.
    - `brandCatalog` brands what a message function returns but not the values it interpolates: a
      profile called "Hermes Lab", or a backend's own message, reads as given.
  - Web dashboard: `web/src/i18n/en.ts` and `context.tsx`.
  - TUI: its English in `ui-tui/src/i18n/en.ts`, packs in `runtime.ts`.
  - CLI help: `HermesArgumentParser.format_help` in `hermes_cli/_parser.py`. Its `prog` is now `tuos`.
  - The dashboard's sign-in pages: `hermes_cli/dashboard_auth/login_page.py`.
- **Copy written into code and docs**: `scripts/fork/rename.py` applies the rule to the files themselves.
  Rerun it after every upstream merge ("Renamed copy", above); `--report` lists the strings it left.
  - Python (`hermes_cli`, `gateway`, `tui_gateway`, `cron`, `tools`, `agent`, `plugins`, `acp_adapter`,
    `cli.py`): what `print`, `input` and the CLI's output helpers show, doctor checks, writes to
    `sys.stdout`/`sys.stderr`, messages of anything raised, slash-command descriptions (`CommandDef`),
    keyword arguments named for copy (`help=`, `description=`, `detail=`, `install_hint=`, ...),
    dictionary values under such keys (tool schemas the agent reads, platform cards, config field help;
    not HTTP header values such as OpenRouter's `X-Title`), and constants named for copy
    (`UPDATE_MESSAGE`, `_AUTH_HINT`). Not logs, docstrings, prompts, comparisons or other data.
  - The desktop app and its setup installer, web dashboard, TUI and the docs site's own pages
    (`scripts/fork/rename_ts.mjs`): JSX text, error messages, and attributes, properties, variables and
    function results whose names say they hold copy (title, label, message, description, hint, ...). Not
    logs, keys, headers, commands the code runs or scripts it sends to a shell.
  - Docs pages (`website/docs` and the zh-Hans translation): prose, front-matter titles and descriptions,
    and shell blocks. Other code blocks, and lines that credit Nous Research, stay. A renamed heading keeps
    its old anchor (`{#...}`), so links into the page still land.
  - The READMEs and contributing guides in every language, the plugin catalog's rules and the skills
    (`skills/`, `optional-skills/`) (`DOC_FILES`), the same way but without the anchors, which GitHub
    and the agent would read as text. The docs site mirrors the
    catalog rules word for word (`tests/website/test_catalog_rules_mirror.py`).
  - Tests follow: an expectation that quotes copy the code now shows renamed is renamed with it.
    - Python: text a test searches output for (`"..." in out`, `not in`, `any(...)`, `.count(...)`),
      passes to a mock's `assert_*` as a message naming the product, or matches in
      `pytest.raises(match=...)`.
    - The apps: `expect(...)` matchers, Testing Library text queries and `node:test` asserts. An exact
      match follows only when it is prose naming the product.
    - Not when the test passes the same copy in itself (it checks its own input comes through), nor when
      the code still keeps that wording somewhere (a log, a JSON field: the test may be reading that).
      Messages pieced together from several strings, expected values held in variables or parameter
      lists, and wording the code keeps in one place but shows renamed in another are fixed by hand.
  - `KEEP` in each script holds wording that stays: code matches on it, or it names something else
    (Nous's models, a service, the `hermes` executable, upstream's community showcase).
  - Hand edits where code reads renamed wording: `hermes_cli/console_engine.py` (the status footer),
    `apps/desktop/src/lib/provider-setup-errors.ts` ("No tuos provider is configured") and
    `apps/desktop/electron/local-runtime-version.ts` (reads `tuos v...` from `--version`, and upstream's
    `Hermes Agent v...` from older installs and remote hosts).
  - Default names people see: the Slack app manifest (`hermes_cli/slack_cli.py`) and the Photon project
    (`plugins/platforms/photon/auth.py`) are called tuos.
- **The agent's identity**: "You are tuos, built on Nous Research's open-source Hermes Agent."
  - Set by `brand_identity()` in a block at the end of `agent/prompt_builder.py`. The same block brands the
    help guidance and the TUI and desktop surface hints.
  - Also in `hermes_cli/default_soul.py`, `SOUL.md` and `docker/SOUL.md`.
  - Hermes's default persona is now listed as an auto-seeded legacy text. A SOUL.md nobody edited moves to
    tuos; one a user wrote stays.
- **CLI and TUI look**:
  - The built-in skins that carried Hermes's branding say tuos, with ◆ in place of ☤
    (`hermes_cli/skin_engine.py`).
  - Banner art: `hermes_cli/brand_art.py` (new) holds the wordmark and the mark that `banner.py` falls
    back to, and `ui-tui/src/banner.ts` draws the same: the icons' letterforms in quadrant blocks, a
    glyph 13 columns by 6 lines, with the corner cuts drawn as stairs.
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
  - pip and Nix installs get it as a console script (`pyproject.toml`): `hermes_cli/tuos_command.py`
    starts the `hermes` installed beside it, with the arguments as given.
- **Desktop and web literals**:
  - Desktop window titles, tray, notification fallbacks and browser tab titles.
  - The intro wordmark, now lowercase: `.wordmark` lost its `text-transform`.
  - The boot-failure page, and a few onboarding and quick-entry messages.
  - The dashboard's `<title>`, and the default Telegram bot name (`web/`, `telegram_managed_bot.py`,
    `web_routers/messaging.py`).
- **Docs and README**: the docs site's title and navbar (`website/docusaurus.config.ts`, without Hermes's
  logo), and the README's title and opening.
- **The desktop app's packaging identity** (`apps/desktop/product-identity.cjs`). The apps are tuos,
  tuos Light and tuos Agent (the bundled build):
  - Files: `tuos.app`, `tuos.exe` and the Linux executable `tuos`.
  - App ids: `io.github.sreent.tuos[-light|-bundled]` (`APP_ID_PREFIX`).
  - MSIX packages: `Sreent.Tuos…` (`MSIX_ORG`), with publisher display name tuos.
  - Artifacts: `TuosBundled-<version>-…`.
  - These follow too: the macOS menu, the About panel (copyright "Nous Research and the tuos
    contributors"), the DMG title, the exe's version info (`scripts/set-exe-identity.mjs`), the Linux
    package metadata and the build scripts' fallbacks.
  - The CLI's copy is `DESKTOP_APP_NAME` and `DESKTOP_APP_ID` in `hermes_cli/distribution.py` (a test
    keeps it in step). `tuos desktop`, doctor and its permission hints, update and uninstall find the
    app with it.
  - These find the app by its new name: `scripts/install.ps1`, `scripts/desktop-update/posix.sh`, the
    setup installer (`bootstrap.rs`, `update.rs`) and `apps/desktop/scripts/test-desktop.mjs`.
    `install.ps1`'s shortcuts are now `tuos.lnk`, and it removes an old `Hermes.lnk` that started this
    checkout's app.
  - The setup installer (`apps/bootstrap-installer`):
    - product and window name tuos, bundle id `io.github.sreent.tuos.setup`, binary `tuos-setup`;
    - its Windows manifest, macOS permission prompts and UI text (`rename_ts.mjs` now covers its
      `src/`), and the installers' "Download tuos" step;
    - it still copies itself to `~/.hermes/hermes-setup`, which the desktop's updater runs.
  - Linux: the launcher entry is `io.github.sreent.tuos.desktop`, labelled tuos. Hermes's
    `com.nousresearch.hermes.desktop` becomes a hidden alias of it, like the older `hermes.desktop`, so
    taskbar pins keep working. Notifications name the new entry.
  - Unchanged:
    - The state folder: `Application Support/Hermes`, `%APPDATA%\Hermes`, `~/.config/Hermes`, named by
      `apps/desktop/package.json`'s `productName`. Saved connections, sign-ins and window layout carry
      over. Hermes's own desktop app shares it, so only one of the two runs at a time.
    - The `hermes://` link scheme, which plugins, the catalog and connectors open.
    - The `hermes` command inside packages.
    - The managed Python's signing identifier and the "Hermes Local Signing" certificate.
  - One-time costs of the new identity:
    - macOS asks again for permissions (screen recording, microphone, Full Disk Access), since they
      belong to the bundle id.
    - Secrets kept in the keychain (an opt-in setting) must be entered again.
    - On Windows the MSIX is a new package, installed beside a Hermes one.
    - Update and uninstall leave apps installed under the old names alone (`Hermes.app`, Nous's
      packages); remove those by hand.
  - The Store variant refuses to package until `STORE_MSIX` holds this fork's Partner Center identity.
- **Icons, logos and banners**: the tuos mark, four blocky glyphs stacked two by two (t u over o s):
  strokes 4 units wide on a 13-unit square, square ends, a 45-degree cut where a stroke would curve,
  and counters as narrow as 1.5 units.
  - The glyph outlines are `MARK_GLYPHS` in `scripts/generate_icons.py`, which draws everything from them:
    every app icon (desktop, Windows tiles, the macOS 26 layers, the setup installer), the favicons
    and logos of the dashboard and docs site, the README and social-card banner, and the DMG's
    background and volume icon. Change the outlines (or `MARK_FRACTION`, the mark's share of the plate),
    run `node scripts/generate-icons.mjs` and commit.
  - Colours: a white mark on a navy (`#13294b`, `NAVY_HEX`) tile in light and dark mode alike. The
    mark's ink follows the tile (`mark_ink`), so canary and commit builds keep their yellow and red
    tiles with a black mark where the tile is light. The transparent logos are navy (for light
    surfaces) and white; the README banner is navy.
  - Nous's artwork is gone (`assets/nous-girl-*.svg`, the drive picture and the DMG background), and
    the generator lost the code that placed it. In an upstream merge, keep the mark in
    `generate_icons.py` and regenerate.
  - Renamed files: `public/tuos-mark*.png` (the apps' `BrandMark`), `website/static/img/tuos-logo*.png`,
    `tuos-banner.png` (the docs site's social card) and `packaging/dmg-background.tiff`. The README
    shows the banner again.
  - Linux names the launcher's icon after the app id (`io.github.sreent.tuos`), so it never replaces
    Hermes's `hermes` icon; uninstall removes both.
- **Release scripts** name the builds as the packager does: artifacts `TuosBundled-`/`TuosLight-`
  (`scripts/releases/darwin.py`, `scripts/render-builds-table.py`, whose tables and pages say tuos and
  whose default repository is this one), preview channels `tuos <name>` with app id
  `io.github.sreent.tuos.channel.h<token>` and MSIX name `Sreent.TuosChannel<token>` (`channels.py`),
  and releases and canaries titled `tuos v<version>` and `tuos canary <tag>` (`entrypoint.py` and
  `scripts/release.py`, whose release notes carry the same heading and link commits to this
  repository).

Not rebranded yet:
- Strings outside the contexts above: Python's returned values and data whose names don't say they hold
  copy, and the apps' strings likewise. A message built from both can mix the names ("run `tuos gateway
  install` ... fold this profile with `hermes gateway migrate --multiplex`"); both commands work.
  `--report` lists what is left; some of it feeds the agent or matchers in other processes (`[hermes note:
  ...]` markers, the internal notification footer), so extend the scripts' rules with care.
- Identities sent to other services: OpenRouter's `X-Title` and `HTTP-Referer` attribution, and the
  names Hermes registers under elsewhere.
- The desktop pet's pixel knight and the feature illustrations, and upstream's community stories on the
  docs site (quotes from people about Hermes).

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
