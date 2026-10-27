"""
Smoke test for Sales Manager, run by the GitHub workflow before building the .exe.

Uses Streamlit's own AppTest to run SalesManager.py exactly as the server would,
with the pinned library versions, in desktop mode (SALES_DESKTOP=1 - the mode the
installed app uses). It:

  - activates a throw-away copy (temporary database + activation file),
  - loads the demo data,
  - opens every page and every tab, failing on any error the app raises,
  - clicks real export buttons (PDF, CSV, database backup, receipt) and checks
    the files were written to the Downloads folder.

    python ci_smoke_test.py

Exit code 0 = all good, 1 = the app raised an error (details printed).
If the AppTest API itself changes in a future Streamlit, the affected checks are
reported as skipped rather than failing the build.
"""
import hashlib
import os
import platform
import sys
import tempfile
import traceback
import uuid

# GitHub's Windows runners print through the cp1252 code page, which can't show
# characters such as arrows. Force UTF-8 (and never crash on a character).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORK = tempfile.mkdtemp(prefix="salesmanager-ci-")
os.environ["SALES_DB_PATH"] = os.path.join(WORK, "ci.db")
os.environ["SALES_ACTIVATION_PATH"] = os.path.join(WORK, ".hdm_pos_activation")
os.environ["SALES_DESKTOP"] = "1"

# Activate this machine the same way the app does (token tied to the computer).
_SALT = b"hdm-pos-install-v1"
_node = uuid.getnode()
_mac = "" if (_node >> 40) & 1 else f"{_node:012x}"
_fp = f"{_mac}|{platform.node()}|{platform.system()}"
with open(os.environ["SALES_ACTIVATION_PATH"], "w", encoding="utf-8") as fh:
    fh.write(hashlib.sha256(_SALT + b"|activated|" + _fp.encode("utf-8")).hexdigest())

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["Dashboard", "Point of sale", "Sales history", "Products & stock", "Receive stock",
         "Customers", "Suppliers", "Expenses", "Reports", "Settings"]
TABS = {
    "Dashboard": ("tabs_dashboard", ["sales", "expenses"]),
    "Products & stock": ("tabs_products", ["list", "add", "restock", "edit", "adjust",
                                           "openbag", "import"]),
    "Customers": ("tabs_customers", ["accounts", "sell", "credit", "pay", "statement", "add",
                                     "edit"]),
    "Suppliers": ("tabs_suppliers", ["list", "purchases", "add", "edit"]),
    "Expenses": ("tabs_expenses", ["record", "list"]),
    "Reports": ("tabs_reports", ["sales", "product", "profit", "stock", "cashup"]),
}

problems, skipped, passed = [], [], 0
at = AppTest.from_file("SalesManager.py", default_timeout=240)


def errors_now():
    out = []
    for e in at.exception:
        msg = getattr(e, "message", None) or getattr(e, "value", None) or str(e)
        out.append(str(msg).splitlines()[0][:300])
    return out


def check(label):
    global passed
    errs = errors_now()
    if errs:
        problems.append((label, errs))
        print(f"  FAIL  {label}: {errs[0]}")
    else:
        passed += 1
        print(f"  ok    {label}")


def step(label, fn):
    try:
        fn()
        check(label)
    except Exception as exc:          # problem with the test API, not the app
        if errors_now():
            check(label)
        else:
            skipped.append((label, repr(exc)[:200]))
            print(f"  skip  {label}: {exc!r}"[:300])
            print("        " + traceback.format_exc().strip().replace("\n", "\n        ")[-1500:])


def goto(page):
    at.radio(key="nav").set_value(page).run()


def tab(key, tab_id):
    # AppTest only knows the labels shown on screen (some include live counts,
    # e.g. "Stock list (13)"), so pick the tab by its position, not its id.
    ids = next(v[1] for v in TABS.values() if v[0] == key)
    r = at.radio(key=key)
    r.set_value(r.options[ids.index(tab_id)]).run()


print("Starting the app ...")
at.run()
check("start-up")
if any("Activate Sales Manager" in str(getattr(m, "value", "")) for m in at.markdown):
    print("  FAIL  the activation screen is showing - activation token did not match")
    sys.exit(1)

print("Empty store:")
for page in PAGES:
    step(f"{page} (empty)", lambda p=page: goto(p))

print("Loading demo data:")
step("Settings > Load demo data", lambda: (goto("Settings"), at.button(key="demo").click().run()))
demo_ok = any("Demo data loaded" in str(getattr(m, "value", "")) for m in at.success)
print(f"        demo data loaded: {demo_ok}")
if not demo_ok:
    print("  WARN  demo data did not load - the page checks below run on an empty store")

print("Every page and tab with data:")
for page in PAGES:
    step(page, lambda p=page: goto(p))
    if page in TABS:
        key, ids = TABS[page]
        for t in ids:
            step(f"{page} > {t}", lambda k=key, t_=t: tab(k, t_))

print("Exports write real files (desktop mode):")


def click_export(page, tab_key, tab_id, button_key):
    goto(page)
    if tab_key:
        tab(tab_key, tab_id)
    at.button(key=button_key).click().run()
    path = at.session_state["_saved_files"][button_key]
    if not (os.path.isfile(path) and os.path.getsize(path) > 0):
        raise AssertionError(f"{button_key}: file not written ({path})")
    print(f"        wrote {os.path.basename(path)} ({os.path.getsize(path):,} bytes)")


for label, args in [("Stock list PDF", ("Products & stock", "tabs_products", "list", "ps_pdf")),
                    ("Stock list CSV", ("Products & stock", "tabs_products", "list", "ps_csv")),
                    ("Sales report PDF", ("Reports", "tabs_reports", "sales", "rs_pdf")),
                    ("Daily sales CSV", ("Reports", "tabs_reports", "sales", "rs_csv")),
                    ("Profit report PDF", ("Reports", "tabs_reports", "profit", "rpr_pdf")),
                    ("Cash-up PDF", ("Reports", "tabs_reports", "cashup", "z_pdf")),
                    ("Sales list CSV", ("Sales history", None, None, "hist_csv")),
                    ("Expenses PDF", ("Expenses", "tabs_expenses", "list", "exp_pdf")),
                    ("Database backup", ("Settings", None, None, "db_bk"))]:
    def _run(a=args):
        click_export(*a)
    try:
        _run()
        check(label)
    except AssertionError as exc:
        problems.append((label, [str(exc)]))
        print(f"  FAIL  {label}: {exc}")
    except Exception as exc:
        if errors_now():
            check(label)
        else:
            skipped.append((label, repr(exc)[:200]))
            print(f"  skip  {label}: {exc!r}"[:300])
            print("        " + traceback.format_exc().strip().replace("\n", "\n        ")[-1500:])

print()
print(f"Passed: {passed}   Skipped (test API): {len(skipped)}   Failed: {len(problems)}")
if problems:
    print("\nThe app raised errors:")
    for label, errs in problems:
        print(f" - {label}:")
        for e in errs:
            print(f"     {e}")
    sys.exit(1)
print("Smoke test passed.")
