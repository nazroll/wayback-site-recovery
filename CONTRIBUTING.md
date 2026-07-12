# Contributing

Thanks for your interest in improving wayback-site-recovery! This is a small, single-maintainer project, so the process below is deliberately lightweight.

## Ways to contribute

- **Report a recovery failure.** The most valuable contribution. Real-world sites break the playbook in ways tests can't predict. Open an issue with the domain (if shareable), date range, exact command, and error output.
- **Improve the playbook (SKILL.md).** Better phase instructions, new failure modes you hit, smarter post-processing steps. This is the core of the project.
- **Fix or extend the audit script.** `scripts/coverage_report.py`: bug fixes, or new asset-reference patterns it should detect.
- **Share an idea.** Not sure it fits? Open an issue with the `idea` template and describe the problem before proposing a solution.
- **Improve docs.** README clarity, install steps for agents not yet covered, typos. All welcome as direct PRs.

## Ground rules

- **SKILL.md is the product.** Keep instructions accurate and verified: every CLI flag or API parameter mentioned must be checked against the current tool version, not guessed. Say in your PR how you verified it and against which version.
- **`scripts/coverage_report.py` stays stdlib-only.** No third-party dependencies; it must run anywhere Python 3.10+ runs.
- **Respect the Internet Archive.** Conservative request pacing is a project value, not a limitation. Contributions that add rate-limit evasion, proxy rotation, or aggressive parallelism will be declined.
- Recovery of publicly archived content only; nothing that bypasses access controls.

## Workflow

- **Small fixes** (typos, broken links, obvious script bugs): open a PR directly.
- **Anything larger** (new playbook phases, new scripts, behavior changes): open an issue first so we can agree on the approach before you invest time.
- Add or update tests when touching `scripts/`; run the suite before pushing:

  ```bash
  python -m unittest discover -s tests -v
  ```

  CI runs the same suite on Python 3.10 and 3.13 for every push and pull request.

## How decisions get made

This project has one maintainer ([@nazroll](https://github.com/nazroll)), who reviews all issues and PRs and has the final say on what merges. Expect a response within about a week; a friendly nudge after that is welcome. Acceptance leans toward changes that keep the skill accurate, portable across agents, and polite to archive.org, and away from scope creep into a general-purpose scraping toolkit.

## Building the `.skill` package locally

```bash
mkdir -p stage/wayback-site-recovery/references stage/wayback-site-recovery/scripts
cp SKILL.md README.md stage/wayback-site-recovery/
cp references/pywaybackup-cli.md stage/wayback-site-recovery/references/
cp scripts/coverage_report.py stage/wayback-site-recovery/scripts/
cd stage && zip -r ../dist/wayback-site-recovery.skill wayback-site-recovery
```

Releases are built automatically by CI when a `v*` tag is pushed.

## Code of conduct

Be kind. All participation is covered by our [Code of Conduct](CODE_OF_CONDUCT.md).
