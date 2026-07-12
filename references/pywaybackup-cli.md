# pywaybackup CLI reference (verified against v4.1.6)

Package: `pywaybackup` (PyPI). GitHub: bitdruid/python-wayback-machine-downloader.
Command: `waybackup`. Verify the installed version's flags with `waybackup --help` if anything below fails; the project evolves and flags have changed between major versions.

## Flags that are commonly guessed wrong

- There is **no `--list` or dry-run flag**. Inventory workaround: run with `--limit 1 --keep -m <metadir>` and read the CSV/CDX metadata it writes before downloading.
- **`-a`, `-l`, `-f`, `-s` are mutually exclusive** (argparse group; exactly one required). `-a --last` is an error.
- `--last` gives ONE folder with the final version of each file in the range, which is the right mode for site reconstruction.

## Full option list (v4.1.6)

```
required (one exclusive):
  -u, --url            url (with subdir/subdomain) to download
  -a, --all            download snapshots of all timestamps
  -l, --last           download the last version of each file snapshot
  -f, --first          download the first version of each file snapshot
  -s, --save           save a page to the wayback machine

optional query parameters:
  -e, --explicit       search only for the explicit given url (no subdirs;
                       recommended for query-string URLs like ?p=123)
  -r, --range          range in years to search
  --start              start timestamp, format YYYYMMDDHHMMSS
  --end                end timestamp, format YYYYMMDDHHMMSS
  --limit [int]        limit number of snapshots to download
  --filetype           filetypes to download, comma separated (js,css,...)
  --statuscode         statuscodes to download, comma separated (200,301,...)
                       (404 and 301 are always skipped by the tool)

behavior:
  -o, --output         output dir (default: current directory / waybackup_snapshots)
  -m, --metadata       dir for db/cdx/csv/log files (keep LOCAL, not a network
                       share; sqlite locking issues)
  -v, --verbose        low | default | high
  --log                save a log file into the output folder
  --progress           show a progress bar
  --no-redirect        do not follow archive.org redirects
  --retry              retry failed downloads (int, or infinite if no value)
  --workers            simultaneous downloads (keep at 1-2; archive.org throttles)
  --delay              seconds between downloads (use 1 for polite pacing)
  --wait               seconds before reconnecting after HTTP errors (default 15)

special:
  --reset              reset the job, ignore existing cdx/db/csv files
  --keep               keep all metadata files after the job finishes
```

## Resume semantics

Interrupted jobs resume automatically on re-run. Resumption breaks if you change
the URL, mode, query parameters, or output path. Progress state lives in a sqlite
db in the metadata dir while running.

## Python API

```python
from pywaybackup import PyWayBackup

backup = PyWayBackup(url="https://example.com", all=True,
                     start="20040101", end="20131231",
                     log=True, keep=True)
backup.run()                    # or backup.run(daemon=True) + backup.status()
print(backup.paths(rel=True))   # snapshots dir, cdx, db, csv, log paths
```

## CDX API quick reference (for inventory without pywaybackup)

```
https://web.archive.org/cdx/search/cdx?url=DOMAIN*&output=json
    &filter=statuscode:200&collapse=urlkey&from=2004&to=2013
```

- `url=DOMAIN*` → all pages under domain; `url=*.DOMAIN&matchType=domain` → include subdomains.
- Fields: urlkey, timestamp, original, mimetype, statuscode, digest, length.
- Large sites: `&showNumPages=true`, then iterate `&page=N`.
- Clean-original fetch of any capture: `https://web.archive.org/web/{timestamp}id_/{original}`; the `id_` modifier strips the Wayback toolbar and URL rewriting.
