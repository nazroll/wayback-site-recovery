# wayback-site-recovery

[![Tests](https://github.com/nazroll/wayback-site-recovery/actions/workflows/test.yml/badge.svg)](https://github.com/nazroll/wayback-site-recovery/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**This is an AI agent skill that helped me recover dead websites from the Wayback Machine.**

I had a goal: recover my old websites. Unfortunately, I don't have backups. Fortunately, the Wayback Machine took snapshots of those websites at points of time when the domains were still active. I made this skill after a couple of days experimenting with an AI agent to recover my old websites from the Wayback Machine.

Your old blog is gone. A client's domain expired. You bought a dropped domain and want its content back. The pages still exist in the Internet Archive, but getting a *complete, working* site out of it means CDX queries, rate limits, toolbar-polluted HTML, missing images, and broken links. This skill teaches your AI agent (Claude Code, Claude.ai, and others) the full playbook, so "recover myoldblog.com from the Wayback Machine" just works.

[Donate to Internet Archive Project](https://archive.org/donate)

## Why a skill instead of just a tool?

The tools already exist, but this skill is focused on *orchestration*. This is an opinionated, end-to-end **site recovery playbook** for your agent.

## Who this is for

- **Blog owners** rescuing their own old site ("it's only on the Wayback Machine now")
- **Migrators** extracting archived posts to Markdown for Hugo / Astro / Eleventy / Jekyll
- **Domain rebuilders & SEO folks** restoring content on an expired domain they've acquired
- **Archivists & researchers** who need a clean local mirror of a defunct public site

## Install

**Requirements:** an AI agent that supports Agent Skills. For local recoveries you'll also need Python 3.10+ on the machine doing the work. The agent installs the downloader (`pywaybackup`) itself when needed.

### Not a developer? Use Claude.ai

Download the packaged `.skill` file from the [latest release](https://github.com/nazroll/wayback-site-recovery/releases/latest) and upload it via **Settings → Capabilities → Skills**. No terminal required. This path is best for inventory checks, audits, and smaller recoveries. For large, multi-hour bulk downloads, run a local agent (like Claude Code) on your own machine.

### Recommended: one command for any agent ([skills.sh](https://skills.sh))

```bash
npx skills add nazroll/wayback-site-recovery
```

The CLI detects your installed agents (Claude Code, Cursor, Codex, Copilot, Gemini CLI, OpenCode, and more) and lets you pick where to install. Add `-g` for a global install or `-a claude-code` to target a specific agent. Prefer manual setup? Use the clone commands below.

### Global Scope (System Level)

**Claude Code:**
```bash
mkdir -p ~/.claude/skills
git clone https://github.com/nazroll/wayback-site-recovery ~/.claude/skills/wayback-site-recovery
```

**Antigravity / Antigravity CLI:**
```bash
mkdir -p ~/.gemini/config/skills
git clone https://github.com/nazroll/wayback-site-recovery ~/.gemini/config/skills/wayback-site-recovery
```

**Codex:**
```bash
mkdir -p ~/.codex/skills
git clone https://github.com/nazroll/wayback-site-recovery ~/.codex/skills/wayback-site-recovery
```

**OpenCode:**
```bash
mkdir -p ~/.opencode/skills
git clone https://github.com/nazroll/wayback-site-recovery ~/.opencode/skills/wayback-site-recovery
```

*Note: Restart your agent client after cloning; the skill triggers automatically on Wayback/site-recovery requests.*

### Project Scope (Workspace Level)

To make the skill available only inside one project, clone it into that agent's project-level skills directory. For Claude Code:

```bash
mkdir -p .claude/skills
git clone https://github.com/nazroll/wayback-site-recovery .claude/skills/wayback-site-recovery
```

Other agents follow the same pattern with their own directory (e.g. `.agents/skills/` for agents that adopt the [cross-agent Agent Skills convention](https://agentskills.io)). Check your agent's docs for the exact path.

## What the agent does with this skill

1. **Inventory first:** Queries the CDX API (incorporating subdomain/`www.` variants, pagination, and deduplication) to act as a quick pre-download audit. This shows the user exactly what is archived *before* committing to a multi-hour download, and the agent quotes a download-time estimate and asks for confirmation before starting a long one.
2. **Bulk download done right:** Drives [pywaybackup](https://github.com/bitdruid/python-wayback-machine-downloader) or [wayback-restorer](https://github.com/obra/wayback-restorer) with verified CLI flags, resume-after-interruption, `id_`-mode clean originals, and polite ~1 req/sec pacing.
3. **Asset coverage audit:** Runs the bundled [scripts/coverage_report.py](scripts/coverage_report.py) to find every missing image, script, and stylesheet, including assets referenced from CSS and `srcset`, and maps each one to a ready-made recovery URL. It also flags externally hosted assets (Photobucket, Blogger, CDNs) and leftover `web.archive.org` links.
4. **Smart asset recovery:** Tries the original CDN URL first (CDN images often outlive their sites), falling back to Wayback. If you need strict archival provenance, just tell the agent to recover from Wayback captures only, since a live CDN URL can serve content that changed after the site died.
5. **Rebuild:** Rewrites internal links to relative paths for a fully offline-browsable static site, or extracts posts to Markdown with front-matter for migration.
6. **Honest reporting:** Lists what was recovered, what is only available in older captures, and what is permanently lost.

## Usage

Just ask naturally:

- "Recover my old blog buyot.org from the Wayback Machine, everything from 2004 to 2013."
- "I bought an expired domain and want to rebuild its old site as static HTML."
- "Extract all posts from the archived version of example.com to Markdown for Hugo."
- "Audit ./site-archive for missing images and try to recover them."

## What's inside

* [SKILL.md](SKILL.md): The four-phase recovery playbook.
* [references/pywaybackup-cli.md](references/pywaybackup-cli.md): Verified CLI flags + CDX API reference.
* [scripts/coverage_report.py](scripts/coverage_report.py): Stdlib-only asset coverage auditor script.

### Running the Coverage Audit Standalone

If you want to manually run the auditor script on any existing recovery directory, use the following:

```bash
python scripts/coverage_report.py ./site-archive --domain example.com
```

This scans every HTML and CSS file in the folder and reports missing internal assets, external hosting references, and unresolved Wayback URLs. The JSON report is written to `SITE_DIR/coverage_report.json` (override with `--json`); missing-asset paths are root-relative and each carries a ready-made Wayback recovery URL.

## Scope & etiquette

Recovers **publicly archived** content only, with conservative request pacing, because the Internet Archive is a donation-funded nonprofit ([donate](https://archive.org/donate)). No access-control bypasses; no claim that inferred content is original. If you republish a site you don't own, copyright responsibility is yours.

**If you republish, follow these norms:** preserve creator and site credits, bylines, and source attribution from the recovered material, and keep its publication context intact. Recovered third-party assets (images from photo hosts, CDNs, other people's servers) remain their owners' property, so withhold or replace them when the rights are unclear. And if a rights holder objects to something you have republished, honor the takedown. These norms are adapted from [wayback-restorer's legal notes](https://github.com/obra/wayback-restorer/blob/main/docs/legal-notes.md).

**A note on fidelity:** the archive captures files at different times, so a rebuilt site can mix eras. You might get a 2013 page styled by a 2007 stylesheet. The skill sets this expectation up front and narrows the date range if you want the site as it looked at a specific moment.

> [!TIP]
> **Rate Limits & Throttling (HTTP 429):** The Internet Archive aggressively rate-limits bulk downloads. Keep pacing conservative. If a download is interrupted, run the command again; `pywaybackup` saves state automatically and resumes without redownloading what you already have.

## Related projects

- [pywaybackup](https://github.com/bitdruid/python-wayback-machine-downloader): A resumable Python downloader (default engine)
- [wayback-restorer](https://github.com/obra/wayback-restorer): A provenance-first mirror rebuilder (alternative engine)
- [hartator/wayback-machine-downloader](https://github.com/hartator/wayback-machine-downloader): The classic Ruby downloader
- [wayback-machine-CDX-image-recovery-skill](https://github.com/Suganthan-Mohanadasan/wayback-machine-CDX-image-recovery-skill): A focused image-recovery skill

## Contributing

Ideas, fixes, and playbook improvements are welcome. The most valuable contribution is a real-world recovery failure report. Small fixes: open a PR directly. Bigger changes: open an issue first. See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules (verified facts only, stdlib-only script, be polite to archive.org).

## License

MIT
