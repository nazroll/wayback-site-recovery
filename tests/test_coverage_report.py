"""End-to-end tests for scripts/coverage_report.py.

Repo-only: these are not shipped in the packaged .skill. Each test builds a
throwaway site tree, runs the auditor CLI against it, and asserts on the JSON
report. Stdlib only, matching the script itself.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "coverage_report.py"
WB = "https://web.archive.org/web/2010id_/"


def write_tree(root, files):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def run_audit(site_dir, domain="example.com"):
    res = subprocess.run(
        [sys.executable, str(SCRIPT), str(site_dir),
         "--domain", domain, "--timestamp", "2010"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise AssertionError(f"auditor failed:\n{res.stdout}\n{res.stderr}")
    return json.loads((site_dir / "coverage_report.json").read_text())


class CoverageReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.site = Path(self._tmp.name) / "site"
        self.site.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def audit(self, files, domain="example.com"):
        write_tree(self.site, files)
        report = run_audit(self.site, domain)
        missing = {m["path"]: m for m in report["internal_assets_missing"]}
        external = {e["url"]: e for e in report["external_assets"]}
        return report, missing, external

    def test_relative_asset_present_in_subdir(self):
        report, missing, _ = self.audit({
            "posts/post1.html": '<html><img src="images/logo.png">',
            "posts/images/logo.png": "x",
        })
        self.assertEqual(report["internal_assets_present"], 1)
        self.assertEqual(missing, {})

    def test_missing_asset_resolved_root_relative_with_correct_recovery_url(self):
        _, missing, _ = self.audit({
            "posts/post1.html": '<html><img src="images/gone.png">',
        })
        self.assertIn("/posts/images/gone.png", missing)
        self.assertEqual(
            missing["/posts/images/gone.png"]["wayback_recovery_url"],
            WB + "http://example.com/posts/images/gone.png",
        )

    def test_srcset_extracts_every_entry(self):
        _, missing, _ = self.audit({
            "posts/p.html": '<img srcset="hero-1x.png 1x, /hero-2x.png 2x">',
        })
        self.assertIn("/posts/hero-1x.png", missing)
        self.assertIn("/hero-2x.png", missing)

    def test_standalone_css_url_import_and_comment_stripping(self):
        _, missing, _ = self.audit({
            "index.html": '<link rel="stylesheet" href="/css/main.css">',
            "css/main.css": (
                '/* url(dead.png) */\n'
                'body { background: url(../img/bg.png); }\n'
                '@import "fonts.css";'
            ),
        })
        self.assertIn("/img/bg.png", missing)      # resolved against /css/
        self.assertIn("/css/fonts.css", missing)
        self.assertFalse(any("dead.png" in p for p in missing))

    def test_css_case_insensitive_and_parens_in_quoted_url(self):
        _, missing, _ = self.audit({
            "index.html": '<link rel="stylesheet" href="s.css">',
            "s.css": 'a { background: URL("file(1).png"); }\n'
                     '@IMPORT "up.css";',
        })
        self.assertIn("/file(1).png", missing)
        self.assertIn("/up.css", missing)

    def test_nested_domain_layout_no_domain_duplication(self):
        report, missing, _ = self.audit({
            "example.com/posts/page.html": '<img src="images/gone.png">'
                                           '<img src="/pic.png">',
            "example.com/pic.png": "x",
        })
        self.assertEqual(report["internal_assets_present"], 1)
        self.assertIn("/posts/images/gone.png", missing)
        for m in missing.values():
            self.assertNotIn("example.com/example.com",
                             m["wayback_recovery_url"])

    def test_www_nested_layout(self):
        report, missing, _ = self.audit({
            "www.example.com/index.html": '<img src="/pic.png">',
            "www.example.com/pic.png": "x",
        })
        self.assertEqual(report["internal_assets_present"], 1)
        self.assertEqual(missing, {})

    def test_www_absolute_ref_maps_to_local_tree(self):
        report, missing, _ = self.audit({
            "index.html": '<img src="http://www.example.com/pic.png">',
            "pic.png": "x",
        })
        self.assertEqual(report["internal_assets_present"], 1)
        self.assertEqual(missing, {})

    def test_subdomain_kept_external_with_full_url(self):
        _, missing, external = self.audit({
            "index.html": '<img src="http://static.example.com/x.png">',
        })
        self.assertEqual(missing, {})
        self.assertIn("http://static.example.com/x.png", external)
        self.assertEqual(
            external["http://static.example.com/x.png"]["wayback_recovery_url"],
            WB + "http://static.example.com/x.png",
        )

    def test_dot_directories_skipped(self):
        report, missing, _ = self.audit({
            "index.html": "<html>ok</html>",
            ".git/skip.html": '<img src="skipme.png">',
        })
        self.assertEqual(report["html_files_scanned"], 1)
        self.assertFalse(any("skipme" in p for p in missing))

    def test_leftover_wayback_urls_reported(self):
        report, _, _ = self.audit({
            "index.html":
                '<img src="https://web.archive.org/web/2010/http://example.com/x.png">',
        })
        urls = [w["url"] for w in report["leftover_wayback_urls"]]
        self.assertEqual(
            urls, ["https://web.archive.org/web/2010/http://example.com/x.png"])

    def test_report_written_inside_site_dir_by_default(self):
        write_tree(self.site, {"index.html": "<html></html>"})
        run_audit(self.site)
        self.assertTrue((self.site / "coverage_report.json").is_file())

    def test_parent_traversal_clamped_at_site_root(self):
        _, missing, _ = self.audit({
            "a/page.html": '<img src="../../../escape.png">',
        })
        self.assertIn("/escape.png", missing)


if __name__ == "__main__":
    unittest.main()
