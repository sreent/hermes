#!/usr/bin/env bash
# Admit the release tag $TAG for scripts/bundles/desktop.py (FORK.md, "Hosted by this fork").
#
# A stable desktop build needs its claim: an annotated tag rc.<N>-vX.Y.Z on the same commit, whose
# tagger time becomes the release epoch (the Windows package's version). Upstream's release workflow
# pushes one per attempt; .github/workflows/tuos-desktop.yml makes it on each runner instead and never
# pushes it. Every runner dates it from the release commit, so all platforms agree on the epoch.
set -euo pipefail

tag="${TAG:?set TAG to the release tag (vX.Y.Z)}"
commit="$(git rev-parse --verify "refs/tags/$tag^{commit}")"
claim="rc.1-$tag"
GIT_COMMITTER_DATE="$(git log -1 --format=%cI "$commit")" \
  git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  tag --annotate --force --message "Release claim for $tag" "$claim" "$commit"
object="$(git rev-parse "refs/tags/$claim")"
echo "claimed $tag ($commit) as $claim ($object)"
if [ -n "${GITHUB_ENV:-}" ]; then
  { echo "RELEASE_CLAIM_TAG=$claim"; echo "RELEASE_CLAIM_OBJECT=$object"; } >> "$GITHUB_ENV"
fi
