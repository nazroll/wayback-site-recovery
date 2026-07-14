---
name: wayback-site-recovery
description: End-to-end recovery of dead or expired websites from the Internet Archive's Wayback Machine - inventory what's archived via the CDX API, bulk-download with resume and polite rate-limiting (pywaybackup or wayback-restorer), audit missing images/assets, fix links, and rebuild a browsable static site or extract posts to Markdown for migration to Hugo/Astro/Eleventy. Use whenever the user wants to download, restore, mirror, rebuild, or rescue an old website, blog, or expired domain from the Wayback Machine / archive.org / web.archive.org; recover lost images or content from an archived site; check what the archive holds for a domain; or migrate an archived blog to a modern static site generator. Trigger even if the user just says a site "is only on the Wayback Machine", "my old blog is gone", or "I bought an expired domain and want the old content back".
---

# Wayback Site Recovery

Recover a website from the Internet Archive's Wayback Machine and rebuild it as a clean, browsable local static site.

The workflow has four phases: **Inventory → Download → Post-process → Verify.** Never skip the inventory: it prevents multi-hour downloads that turn out to be missing half the site.

## Phase 0: Establish scope with the user

Before running anything, confirm:

1. **Domain** and likely URL variants. Sites from the 2000s are often split across `http://example.com`, `http://www.example.com`, and subdomains. Plan to check all variants.
2. **Date range** (Wayback timestamps are `YYYYMMDDHHMMSS`).
3. **Goal**: a *faithful mirror* (site as it looked) or a *content rescue* (posts extracted to Markdown for migration into Hugo/Eleventy/etc.). The download is identical; the post-processing differs. Ask early, because extracting Markdown during processing is far easier than retrofitting.
4. **Every snapshot vs. latest version**: "all data" is ambiguous. `--all` mode downloads every capture of every file (a homepage captured 80 times = 80 copies); `--last` downloads one final version of each file. Default to `--last` for site reconstruction; use `--all` only if the user wants the historical record.
5. **Set the era-mixing expectation.** `--last` takes the *final* capture of each file individually, so a site archived over many years can come back as a mix of eras: 2013 HTML styled by a 2007 CSS sheet, with 2005 images. Tell the user this up front. If they want "the site as it looked on/around DATE", narrow `--start`/`--end` to a window around that date instead of the site's whole lifetime.

## Phase 1: Inventory (CDX API)

Query the CDX index to see what actually exists before downloading:

```
https://web.archive.org/cdx/search/cdx?url=DOMAIN*&output=json&filter=statuscode:200&collapse=urlkey&from=YYYY&to=YYYY
```

- `url=DOMAIN*` (trailing wildcard) matches every page under the domain; the bare domain matches only the homepage.
- Use `url=*.DOMAIN&matchType=domain` to include all subdomains.
- For very large sites, use pagination: `&showNumPages=true` then `&page=N`.
- `collapse=urlkey` gives one row per URL; `collapse=digest` instead deduplicates identical captures while keeping distinct versions, which is useful when deciding between `--last` and `--all`.

If the environment cannot reach web.archive.org, give the user the URL to paste into a browser, or use pywaybackup's own inventory workaround (below).

**Interpret the inventory before proceeding:**
- Count `text/html` rows vs. what the user remembers (e.g. ~300 posts but only 40 HTML URLs ⇒ shallow crawl; monthly-archive and pagination pages may still contain the missing text).
- Check for `image/jpeg`, `image/png`, `text/css` rows. If it's nearly all HTML, the site's assets were not archived under this domain. Expect broken images and plan the external-asset pass (Phase 3).
- Thin results ⇒ re-run the query for `www.` and other variants; captures are frequently split.

**pywaybackup inventory workaround**: the tool has **no dry-run/list flag**. It writes its CDX/CSV metadata before downloading, so a `--limit 1` run yields the full inventory at the cost of one file:

```bash
waybackup -u https://DOMAIN -l --start 20040101000000 --end 20131231235959 \
  --limit 1 --keep -o /tmp/inventory-test -m ./meta
```

Then read the CSV in `./meta` (one row per archived URL: timestamp, original URL, mimetype, statuscode).

## Phase 2: Download (pywaybackup)

**Estimate duration and confirm before starting.** At the mandatory polite pacing (~1 req/sec plus overhead), budget roughly 1.5 seconds per URL: 500 URLs ≈ 12 minutes, 3,000 URLs ≈ 75 minutes. Compute the estimate from the Phase 1 inventory count, tell the user, and get their go-ahead before starting any download expected to exceed ~15 minutes. While it runs, remind them that long stalls are normal (archive.org throttling) and that an interrupted job resumes when re-run; otherwise users assume the agent hung and kill it.

**Decision gate before running pywaybackup:** pywaybackup always re-queries CDX on startup; it cannot accept a pre-built URL list. If the CDX inventory from Phase 1 is already complete AND the site is small (≤ a few hundred URLs), skip pywaybackup and download the files directly using the `id_` URL modifier (`https://web.archive.org/web/{timestamp}id_/{original_url}`), one request per second. Only reach for pywaybackup when the site is large enough that its resume/retry logic is worth the overhead, or when you do not yet have a complete inventory.

Install: `pip install pywaybackup` (use `--break-system-packages` on Debian/Ubuntu system Python). CLI details and full verified flag list: read `references/pywaybackup-cli.md` before constructing commands, since several flags are commonly guessed wrong.

Standard site-reconstruction command:

```bash
waybackup -u https://DOMAIN -l --start YYYYMMDDHHMMSS --end YYYYMMDDHHMMSS \
  -o ./site-archive -m ./meta --progress --retry 3 --delay 1 --log --keep
```

Omit `--progress` when running non-interactively (agent shells, CI, `nohup`) because its carriage-return progress bar floods captured logs; rely on `--log` instead.

Critical facts (all verified against v4.1.6; do not guess these):

- **Modes `-a | -l | -f | -s` are mutually exclusive**; exactly one is required. `-a --last` is invalid. `-l` = last version of each file, `-a` = all snapshots, `-f` = first version.
- **Resume**: interrupted jobs resume automatically when re-run, but only if URL, mode, query parameters, and output are unchanged. `--reset` starts over.
- **Rate limits**: archive.org throttles aggressively. Keep `--delay 1` and `--workers` at 1–2; use `--retry` and `--wait` rather than more workers. Long stalls mid-run are normal; re-run and it resumes.
- **Windows path-length limit** silently skips files with long URLs; prefer Linux/macOS/WSL for big jobs.
- Run each URL variant (`www.` etc.) into separate output folders, then merge, preferring the more complete copy of each file.

**Alternative engine: wayback-restorer** (github.com/obra/wayback-restorer, Python, no third-party deps): handles CDX pagination, canonical capture selection, host-alias dedupe (`--canonical-host` / repeatable `--equivalent-host`, which solves the www/non-www split natively), id_-mode downloads with conservative single-threaded pacing, a referenced-asset recovery pass, link rewriting, and coverage/gap/provenance reports. Prefer it when the user cares about provenance (knowing exactly which capture each file came from) or has messy host aliases; prefer pywaybackup for simple resumable date-range pulls. Check its README for current CLI before use.

**Etiquette and scope**: keep pacing conservative (~1 req/sec, single-threaded) because the Internet Archive is a donation-funded nonprofit, not a CDN. Recover only publicly archived content; never attempt login/admin/private paths. If the user plans to republish a site they don't own, note that recovered content may carry third-party copyright and the decision is theirs.

## Phase 3: Post-process

Work on a copy; keep the raw download pristine.

1. **Strip Wayback artifacts.** Check downloaded HTML for injected toolbar markup, `<script src=".../static/js/wombat.js">`-style includes, and rewritten `https://web.archive.org/web/TIMESTAMP/...` URLs. pywaybackup downloads originals via the `id_` URL modifier so files are usually clean, but verify; mixed captures happen.
2. **Rewrite internal links** to relative local paths so the site browses offline. Map `http(s)://(www.)?DOMAIN/path` → relative `path`, handling query-string URLs (`?p=123`) by mapping them to the on-disk names the downloader produced. This step is **mandatory for query-string sites** (old WordPress/forum permalinks): a static file server cannot resolve `?p=123` to a file, so every unrewritten query-string link 404s offline even though the page was downloaded. If any remain, tell the user which links won't work and why.
3. **Asset coverage audit.** Run the bundled script:

   ```bash
   python scripts/coverage_report.py ./site-archive --domain DOMAIN [--timestamp TIMESTAMP]
   ```

   It parses every HTML file (`img/script/link/a`, `srcset`, inline-CSS `url()`) **and every standalone `.css` file** (`url()` and `@import`), reporting: internal assets present, internal assets missing (as root-relative paths resolved against the referencing page, with Wayback recovery URLs generated using the optional `--timestamp`), and external-domain assets (Photobucket, ImageShack, Blogger, Flickr, all extremely common for 2004–2013 blogs). It probes both `SITE_DIR/path` and `SITE_DIR/DOMAIN/path` layouts. The JSON report is written to `SITE_DIR/coverage_report.json` (override with `--json`). Review it with the user.
4. **Recover missing assets: try the original URL first, then Wayback.** CDN-hosted images (Cloudinary, Contentful, Imgur, Blogger's googleusercontent, Flickr staticflickr) often outlive the sites that embedded them; a plain GET on the original URL frequently still works even when the site is long dead. For each missing or external asset: (a) try the original URL live; (b) on failure, fetch `https://web.archive.org/web/TIMESTAMPid_/ASSET_URL` (the `id_` modifier returns the clean original; pick a timestamp near the referencing page's capture). Respect ~1 req/sec pacing on archive.org. Update the HTML references for anything recovered; note permanent losses in the final report. (Truly dead hosts like Photobucket/ImageShack usually only survive via Wayback, if at all.)
5. **Optional Markdown extraction** (content-rescue goal): parse each post's HTML, extract title/date/body (era-typical platforms: WordPress, Blogger, Movable Type; look for `<div class="post">`, `<div class="entry">`, `h2/h3.post-title` patterns), and emit one `.md` file per post with front-matter.

## Phase 4: Verify and report

- Open a sample of pages (serve locally: `python -m http.server`) or parse them to confirm: no `web.archive.org` URLs remain, images resolve, internal navigation works. Test query-string links (`?p=123`) specifically, since they are the ones that break under a static server if Phase 3 link rewriting missed them.
- Re-run `coverage_report.py` to confirm the missing-asset count dropped.
- Deliver a short report: pages recovered, date coverage, assets recovered vs. permanently lost, and anything only available in older captures.

## Failure modes to anticipate

- **Empty/thin CDX results**: wrong URL variant, or the site is under a subdomain (`blog.DOMAIN`). Query `matchType=domain`.
- **HTTP 429 storms**: back off; increase `--wait`; never parallelize harder.
- **Duplicate content under multiple URLs** (`/post/`, `/post/index.html`, `/?p=123`): deduplicate by content hash during post-processing, keeping the canonical path.
- **Session-era cruft** (calendar pages, `?replytocom=` URLs): thousands of near-duplicate crawler-trap URLs can dominate an inventory; filter them out before downloading with `--filetype`/URL filtering or by trimming the CDX list.
