# Sales Manager (HDM POS) — Windows Software

Packages **Sales Manager**, the HDM POS point-of-sale and stock system for
agricultural feed stores (a product of Health Data Matrics), as ordinary Windows
software. The person using it does **not** need Python or Streamlit installed.
It opens in its **own native window** — no browser, no address bar, no tabs —
and there is no Streamlit menu or Deploy button. Closing the window quits the
program.

## Files

| File | Purpose |
|---|---|
| `SalesManager.py` | The app. |
| `FeedStoreSales.py` | Regenerates the app from a single wrapped source (asks for the passkey, then writes `SalesManager.py` + `requirements.txt`). Edit this, run it — never edit `SalesManager.py` directly. |
| `requirements.txt` | Python packages the app imports. |
| `requirements-windows.txt` | Windows-only extras (`pywebview`, `pythonnet`, `tzdata`) for the native window and local time. |
| `run_desktop.py` | Launcher: runs the server hidden, shows the native window. |
| `build_windows.spec` | PyInstaller recipe that produces the `.exe`. |
| `installer.iss` | Inno Setup script; asks for the passkey, produces the installer. |
| `make_key.py` | Prints the hashes of a new passkey for `installer.iss` and the app. |
| `ci_smoke_test.py` | Runs the app with the real Streamlit before building: every page, every tab, and real PDF/CSV/backup exports. |
| `logo.ico` | Application icon (the HDM POS mark, seven sizes). |
| `.gitignore` | Keeps build output, databases and activation markers out of Git. |
| `.github/workflows/build-windows.yml` | Builds, tests and packages on GitHub. **Must stay at this path.** |

## The installation passkey

There are **two** layers, and both use the same passkey:

1. **The installer** asks for the passkey once, checks it against a one-way
   hash, and refuses to install if it is wrong.
2. **The app itself** asks for the same passkey the first time it opens on a
   computer (its activation screen), then records activation for that computer
   in `%LOCALAPPDATA%\SalesManager\.hdm_pos_activation` so it is not asked
   again. The marker is tied to the computer — copied to another PC it does not
   work, and the app asks for the passkey there.

**The passkey is not written anywhere in this repository — only its hashes.**
It was supplied to you separately; give it to whoever installs the software.
Both the passkey with its trailing `...` and the same passkey without the dots
are accepted. To accept only one, see *Changing the passkey*.

## The application icon

`logo.ico` is the HDM POS mark, so the desktop shortcut, the taskbar, the window
and the installer all match the icon shown inside the app. Replace it with your
own 256×256 `.ico` if you prefer; `build_windows.spec` and `installer.iss` pick
it up by name.

## Build on GitHub (recommended)

1. Put every file at the repository root. The one exception is
   `build-windows.yml`, which must sit at `.github/workflows/` — GitHub only
   looks there. The zip already has it in place.
2. **Actions → Build Windows App → Run workflow** (or push a tag like `v1.0.0`).
   The workflow checks the code, runs the smoke test (every page, tab and
   export with the real libraries), builds the `.exe`, confirms the PDF/Excel
   libraries were bundled, then builds the installer.
3. Download the **SalesManager-installer** artifact → `SalesManagerSetup.exe`.
4. Run it, enter the passkey when asked, finish. On first launch the app asks
   for the passkey once more, then activates.

## Build on a Windows machine instead

Requires Python 3.11 and Inno Setup 6.

```bat
pip install -r requirements.txt
pip install -r requirements-windows.txt
pip install pyinstaller==6.11.1
python ci_smoke_test.py
pyinstaller build_windows.spec --noconfirm --clean
iscc installer.iss
```

Produces `dist\SalesManager\SalesManager.exe` and `Output\SalesManagerSetup.exe`.

## Why downloads, uploads and backups work in the window

**Downloads are written straight to disk.** A browser download inside an
embedded WebView2 goes through the host's download plumbing, and when any part
of that is unavailable the button does nothing at all. Rather than depend on it,
the launcher sets `SALES_DESKTOP=1`, and every export then writes the file
itself, shows where it landed, and offers **📂 Open file**. That covers:

- **PDF reports** — sales, by product, profit, stock valuation, end-of-day
  cash-up, stock list, deliveries, purchases, expenses, debtors, credit sales,
  customer statements;
- **CSV exports** — every table that offers one;
- **Receipts** — **🖨️ Print receipt** saves the PDF and opens it straight away in
  the PDF viewer, ready to print;
- **Settings → Backup & restore → Download backup (.db)**.

Files go to your **Downloads** folder, and an export never overwrites an earlier
one (`stock-list.pdf`, `stock-list (2).pdf`, …).

Run the same app with plain `streamlit run SalesManager.py` and it uses ordinary
browser download buttons again, because there the server may be on another
machine.

Two pywebview settings are still applied, since they matter for everything else
the window does: `ALLOW_DOWNLOADS` is switched on (pywebview 5 ships with it
off, which is why `requirements-windows.txt` pins `pywebview>=5.0`), and
`WEBVIEW2_USER_DATA_FOLDER` is redirected to `%LOCALAPPDATA%`, because the
default profile path sits beside the `.exe` and is read-only under
`Program Files`.

**Uploads.** Streamlit's XSRF protection rejects the `file_uploader` POST inside
an embedded webview, which looks like an upload that spins and fails. That
would break **Settings → Restore from a backup**, the **price-list import**
(CSV/Excel) and the **store logo** upload. It is switched off, with CORS off
alongside. Safe here: the server only ever binds `127.0.0.1`. The upload cap is
raised to 400 MB so a large backup fits.

**No config folder.** Every server and theme setting is passed as a
command-line flag by `run_desktop.py`, so there is no `.streamlit/config.toml`
to go missing or fall out of step with the launcher.

## Backup & restore (what the user does)

In the app: **Settings → 💾 Backup & restore**.

- **Download a backup** writes a single `.db` snapshot of everything — products
  and stock, sales and receipts, customers and credit, suppliers and purchases,
  expenses and settings — to the **Downloads** folder. It is taken safely even
  while the app is in use.
- **Restore from a backup** uploads a `.db` backup, checks it really is a Sales
  Manager backup and isn't damaged, saves a safety copy of the current data
  (`before-restore-….db` next to the database), then replaces the data. Older
  backups are upgraded automatically. This is also how you move data to another
  computer.

## When installed

- Own native window using the WebView2 engine built into Windows 10/11 —
  taskbar entry, HDM POS icon, no browser chrome.
- Data lives in `%LOCALAPPDATA%\SalesManager\feedstore.db`, so it survives
  reinstalls and upgrades. Back it up with the in-app backup, or by copying that
  file.
- The activation marker lives in `%LOCALAPPDATA%\SalesManager\.hdm_pos_activation`.
- Exports go to the normal Windows **Downloads** folder.
- Runs fully offline.
- **Fallbacks:** if the native window cannot start, it opens a standalone
  Edge/Chrome app window; if neither exists, the default browser. The app always
  opens.

## Changing the passkey

```bat
python make_key.py my_new_passkey
```

It prints two hashes. Paste them into:

- `MyPasskeyHash` (and `MyPasskeyHashAlt`, or set both to the same value) in
  `installer.iss`, and
- the `_ACT_HASHES` set in the app — in `FeedStoreSales.py` (then run it to
  regenerate `SalesManager.py`) — and the same set near the bottom of
  `FeedStoreSales.py` used by its own passkey prompt.

Never commit the plaintext.

## Known limitations

- **One shared passkey.** Every copy uses the same passkey, so an installer can
  be passed on along with the passkey. Activation is tied to each computer, but
  someone comfortable editing Python could remove the check. For paid,
  per-customer licensing, add per-buyer keys or an online activation server.
- **Unsigned.** SmartScreen will warn — choose **More info → Run anyway**. Code
  signing removes this.
- **Single machine.** No multi-user access and no sync between computers. For
  several tills sharing one set of data, deploy the server version instead.
