#!/usr/bin/env python3
"""Audit a Wayback-recovered site folder for asset coverage.

Parses every HTML file (img/script/link/a/srcset and inline CSS url() refs)
and every standalone .css file (url() and @import refs) and reports:
  - internal assets that exist on disk
  - internal assets that are MISSING (with Wayback recovery URLs)
  - external-domain assets (Photobucket/Blogger/etc.) that need a separate pass
  - leftover web.archive.org URLs that still need rewriting

Missing assets are reported as root-relative paths resolved against the
referencing page's location, so recovery URLs are correct for pages in
subdirectories.

Usage:
    python coverage_report.py SITE_DIR --domain example.com [--json OUT.json]

The JSON report is written to SITE_DIR/coverage_report.json unless --json is given.

Stdlib only (html.parser); no dependencies.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote

ASSET_TAGS = {
    "img": "src",
    "script": "src",
    "link": "href",   # css/favicons; rel filtering below
    "source": "src",
    "embed": "src",
    "iframe": "src",
}
LINK_RELS_AS_ASSET = {"stylesheet", "icon", "shortcut icon", "apple-touch-icon"}
SRCSET_TAGS = {"img", "source"}

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
CSS_URL_RE = re.compile(
    r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^'"()\s]+))\s*\)""", re.I)
CSS_IMPORT_RE = re.compile(r"""@import\s+(?:"([^"]+)"|'([^']+)')""", re.I)


def css_urls(text):
    text = CSS_COMMENT_RE.sub("", text)
    out = []
    for groups in CSS_URL_RE.findall(text) + CSS_IMPORT_RE.findall(text):
        u = next((g for g in groups if g), "")
        if u:
            out.append(u)
    return out


class RefExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.assets = []   # (tag, url)
        self.links = []    # href of <a>
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag == "style":
            self.in_style = True
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if a.get("href") and (not rel or rel in LINK_RELS_AS_ASSET):
                self.assets.append((tag, a["href"]))
        elif tag in ASSET_TAGS and a.get(ASSET_TAGS[tag]):
            self.assets.append((tag, a[ASSET_TAGS[tag]]))

        if tag in SRCSET_TAGS and a.get("srcset"):
            for entry in a["srcset"].split(","):
                parts = entry.strip().split()
                if parts:
                    self.assets.append(("srcset", parts[0]))

        # Parse inline styles for background-image url(...) etc.
        for name, value in attrs:
            if name.lower() == "style" and value:
                for u in css_urls(value):
                    self.assets.append(("style_inline", u))

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            for u in css_urls(data):
                self.assets.append(("style_block", u))


def classify(url, domain):
    """Return (kind, normalized) where kind in
    {skip, wayback, external, internal_abs, relative}."""
    u = url.strip()
    if not u or u.startswith(("#", "data:", "mailto:", "javascript:", "tel:")):
        return "skip", u
    if u.startswith("//"):
        u = "http:" + u
    p = urlparse(u)
    host = p.netloc.lower().split(":")[0]
    if host.endswith("web.archive.org") or host == "archive.org":
        return "wayback", u
    if p.scheme in ("http", "https"):
        d = domain.lower()
        # Only the apex domain and www map onto the local tree; other
        # subdomains keep their full URL so the external-asset pass can
        # try the correct host instead of a wrong apex-domain path.
        if host == d or host == "www." + d:
            return "internal_abs", p.path or "/"
        return "external", u
    return "relative", u


def site_rel_page(rel_page, domain):
    """Strip a leading domain-named folder from a page path.

    Downloaders like pywaybackup nest output under SITE_DIR/DOMAIN/; missing
    paths and recovery URLs must be relative to the site root, not SITE_DIR.
    """
    first, _, rest = rel_page.partition("/")
    if rest and first.lower() in (domain.lower(), "www." + domain.lower()):
        return rest
    return rel_page


def root_relative(rel_page, ref):
    """Resolve a reference against its page's root-relative location.

    rel_page is the referencing file's posix path relative to the site root
    ('posts/post1.html'); ref is a relative or root-absolute reference.
    Returns a root-relative path without leading slash ('posts/images/x.png'),
    or None for empty refs. '../' segments are clamped at the site root.
    """
    ref = unquote(ref.split("#")[0].split("?")[0])
    if not ref:
        return None
    base = "http://x/" + rel_page
    return urlparse(urljoin(base, ref)).path.lstrip("/")


def local_candidates(site_dir, domain, root_rel):
    """Possible on-disk locations for a root-relative path.

    Probes site_dir/PATH plus site_dir/DOMAIN/PATH and site_dir/www.DOMAIN/PATH
    because some downloaders (pywaybackup) nest output under a domain-named folder.
    """
    roots = (site_dir, site_dir / domain, site_dir / ("www." + domain))
    if not root_rel:
        return [r / "index.html" for r in roots]
    out = []
    for r in roots:
        c = r / root_rel
        out.append(c)
        if not c.suffix:  # /about/ -> /about/index.html
            out.append(c / "index.html")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("site_dir", type=Path)
    ap.add_argument("--domain", required=True,
                    help="original site domain, e.g. example.com")
    ap.add_argument("--json", type=Path, default=None,
                    help="report output path (default: SITE_DIR/coverage_report.json)")
    ap.add_argument("--timestamp", default="2013",
                    help="Wayback timestamp prefix (e.g. 2013, 20080512) for recovery URLs")
    args = ap.parse_args()

    site_dir = args.site_dir.resolve()
    if not site_dir.is_dir():
        sys.exit(f"error: {site_dir} is not a directory")
    json_path = args.json if args.json is not None else site_dir / "coverage_report.json"

    def site_files(*suffixes):
        return sorted(
            p for p in site_dir.rglob("*")
            if p.suffix.lower() in suffixes and p.is_file()
            and not any(part.startswith(".")
                        for part in p.relative_to(site_dir).parts)
        )

    html_files = site_files(".html", ".htm", ".php", ".asp", ".aspx")
    if not html_files:
        sys.exit(f"error: no HTML files found under {site_dir}")
    css_files = site_files(".css")

    missing = defaultdict(list)      # root-relative path -> referencing pages
    present = set()
    external = defaultdict(list)     # url -> referencing pages
    wayback_refs = defaultdict(list)
    parse_errors = []

    def handle_asset(url, rel_page):
        kind, norm = classify(url, args.domain)
        if kind in ("relative", "internal_abs"):
            rr = root_relative(site_rel_page(rel_page, args.domain), norm)
            if rr is None:
                return
            if any(c.exists() for c in local_candidates(site_dir, args.domain, rr)):
                present.add(rr)
            else:
                missing[rr].append(rel_page)
        elif kind == "external":
            external[norm].append(rel_page)
        elif kind == "wayback":
            wayback_refs[norm].append(rel_page)

    for hf in html_files:
        rel_page = hf.relative_to(site_dir).as_posix()
        try:
            text = hf.read_text(errors="replace")
            ex = RefExtractor()
            ex.feed(text)
        except Exception as e:  # noqa: BLE001 - report and continue
            parse_errors.append({"file": rel_page, "error": str(e)})
            continue
        for _tag, url in ex.assets:
            handle_asset(url, rel_page)
        for url in ex.links:
            kind, norm = classify(url, args.domain)
            if kind == "wayback":
                wayback_refs[norm].append(rel_page)

    for cf in css_files:
        rel_page = cf.relative_to(site_dir).as_posix()
        try:
            text = cf.read_text(errors="replace")
        except Exception as e:  # noqa: BLE001 - report and continue
            parse_errors.append({"file": rel_page, "error": str(e)})
            continue
        for url in css_urls(text):
            handle_asset(url, rel_page)

    def recovery_url(path_or_url):
        if path_or_url.startswith("http"):
            target = path_or_url
        else:
            target = f"http://{args.domain}/{path_or_url.lstrip('/')}"
        prefix = args.timestamp.rstrip("id_")
        return f"https://web.archive.org/web/{prefix}id_/{target}"

    report = {
        "site_dir": str(site_dir),
        "domain": args.domain,
        "html_files_scanned": len(html_files),
        "css_files_scanned": len(css_files),
        "internal_assets_present": len(present),
        "internal_assets_missing": [
            {"path": "/" + p, "referenced_by": sorted(set(refs))[:5],
             "wayback_recovery_url": recovery_url(p)}
            for p, refs in sorted(missing.items())
        ],
        "external_assets": [
            {"url": u, "referenced_by": sorted(set(refs))[:5],
             "wayback_recovery_url": recovery_url(u)}
            for u, refs in sorted(external.items())
        ],
        "leftover_wayback_urls": [
            {"url": u, "referenced_by": sorted(set(refs))[:5]}
            for u, refs in sorted(wayback_refs.items())
        ],
        "parse_errors": parse_errors,
    }
    json_path.write_text(json.dumps(report, indent=2))

    print(f"Scanned {len(html_files)} HTML files, {len(css_files)} CSS files under {site_dir}")
    print(f"  internal assets present : {len(present)}")
    print(f"  internal assets MISSING : {len(missing)}")
    print(f"  external-domain assets  : {len(external)}")
    print(f"  leftover wayback URLs   : {len(wayback_refs)}")
    if parse_errors:
        print(f"  parse errors            : {len(parse_errors)}")
    print(f"Full report: {json_path}")
    if missing:
        print("\nTop missing internal assets:")
        for p in sorted(missing)[:10]:
            print(f"  /{p}")
    if external:
        print("\nExternal hosts referenced:")
        hosts = defaultdict(int)
        for u in external:
            hosts[urlparse(u).netloc] += 1
        for h, n in sorted(hosts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {h}  ({n} assets)")


if __name__ == "__main__":
    main()
