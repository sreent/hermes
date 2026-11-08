---
title: Official Sources & Phishing Safety
description: How to verify you are using genuine tuos resources, and how to spot impersonation scams.
---

# Official Sources & Phishing Safety

Popular open-source projects attract impersonation campaigns: lookalike websites, GitHub accounts that mass-mention contributors with shortlinks, and cold emails offering "credits" on lookalike products. This page lists where tuos is published, so you can check anything that claims to be tuos.

## Official sources

tuos is published from one GitHub repository, [sreent/hermes](https://github.com/sreent/hermes), and the GitHub services that serve it:

| Address | What it is |
|---|---|
| [github.com/sreent/hermes](https://github.com/sreent/hermes) | Source code, [issues](https://github.com/sreent/hermes/issues), and [releases](https://github.com/sreent/hermes/releases) with the desktop apps |
| `raw.githubusercontent.com/sreent/hermes/main/scripts/` | The `install.sh` / `install.ps1` installers, served from that repository's `main` branch |
| [sreent.github.io/hermes](https://sreent.github.io/hermes) | This documentation site (GitHub Pages) |
| [`ghcr.io/sreent/tuos`](https://github.com/sreent/hermes/pkgs/container/tuos) | The container image, on the GitHub Container Registry (see [Docker](../user-guide/docker.md)) |

Report problems and suspicious accounts in the repository's [issues](https://github.com/sreent/hermes/issues).

## Nous Research's sources

tuos is built on Hermes Agent, Nous Research's open-source agent. Nous Research operates `nousresearch.com` and its subdomains, the [NousResearch organization](https://github.com/NousResearch) on GitHub with its [hermes-agent repository](https://github.com/NousResearch/hermes-agent), [@NousResearch](https://x.com/NousResearch) on X and the [Nous Research Discord](https://discord.gg/NousResearch). Those are official sources for Hermes Agent and for the Nous services tuos uses:

| Address | What tuos uses it for |
|---|---|
| [portal.nousresearch.com](https://portal.nousresearch.com/) | Nous Portal: account sign-in, subscriptions and billing, when you use the Nous provider |
| `inference-api.nousresearch.com` | The Nous inference API, when you use the Nous provider (no web page) |
| `hermes-agent.nousresearch.com` | The Skills Hub index and the plugin catalog tuos reads |
| `hermes-assets.nousresearch.com` | Nous's release artifacts, including the Termux APT repository |

## Installing from an official source

The script installers come from this repository:

```bash
# Linux / macOS / WSL2
curl -fsSL https://raw.githubusercontent.com/sreent/hermes/main/scripts/install.sh | bash
```

```powershell
# Windows (native)
iex (irm https://raw.githubusercontent.com/sreent/hermes/main/scripts/install.ps1)
```

The desktop apps download from the repository's [releases](https://github.com/sreent/hermes/releases), and Docker pulls `ghcr.io/sreent/tuos`. Termux packages come from Nous Research's signed APT repository on `hermes-assets.nousresearch.com` (see the [Termux guide](./termux.md)) and install Hermes Agent.

If an installer, download, image, or "portal" is hosted anywhere other than the sources listed on this page, treat it as untrusted.

## Not official

- **Any other GitHub account or repository, or any other website**, even when its name contains "tuos" or "hermes", it copies the branding, or it says it "points to official docs". Read the whole host name: `sreent.github.io.example.net` is not GitHub Pages, and `portal.nousresearch.com.example.net` is not a Nous Research subdomain.
- **Cryptocurrency tokens.** There is **no tuos token**, and none for Hermes Agent or Nous Research either. Any account or site promoting one is a scam.
- **GitHub accounts that mass-mention users** in discussions or issues with "community notice" posts and URL-shortener links (`goo.su`, `bit.ly`, etc.). Genuine project announcements never arrive as mass @-mentions with shortlinks.
- **Unsolicited emails** offering credits, hosted "multiplayer tuos" products, or partnership deals that name-drop the project to build trust.

## If you receive a suspicious message

1. **Don't click** shortened or off-domain links; don't enter credentials or connect wallets.
2. **Report the account** to GitHub (`Report abuse` on the profile) or the relevant platform.
3. **Check the address** against the sources above: if it is not one of them, it isn't tuos.
4. Optionally flag it in an [issue](https://github.com/sreent/hermes/issues) so others see it, but note that impersonation campaigns are external abuse: they're handled by platform reports, not code changes.

tuos is MIT-licensed and free to self-host. Nobody legitimate will ever ask you to pay for the open-source agent itself, claim "your account has credits waiting", or DM you an alternate download link.
