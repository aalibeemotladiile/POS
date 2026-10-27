"""
Sales Manager (HDM POS) — Windows desktop launcher.

Runs the Streamlit server hidden and shows the app in its own native window
(WebView2), so it behaves like ordinary desktop software: taskbar entry, app
icon, no browser chrome. Closing the window shuts the server down.

How it starts
-------------
The packaged .exe re-spawns *itself* with SALES_SERVER=1 to become the server
process. That is deliberate: inside a PyInstaller bundle `sys.executable` is
SalesManager.exe, not python.exe, so the usual `sys.executable -m streamlit`
trick would launch a second copy of the window instead of a server. The child
then hands control to Streamlit's own CLI.

Downloads, uploads and backups
------------------------------
Both downloads and uploads are dead inside a native window unless these are
set, and all are needed:

  1. pywebview 5 ships with downloads switched off. Without ALLOW_DOWNLOADS a
     "Download ..." button can look like it does nothing at all. Belt and
     braces: the app itself runs in desktop mode (SALES_DESKTOP=1) and writes
     every export — PDF reports, CSV exports, receipts and the database backup
     — straight to the Downloads folder instead of trusting the webview, then
     offers an "Open file" button (receipts open at once, ready to print).
  2. WebView2 keeps its profile in a folder that defaults to a path beside the
     .exe. Under Program Files that is read-only, so the download manager — and
     sometimes the whole window — fails silently. We point it at LOCALAPPDATA.
  3. Streamlit's XSRF protection rejects the file_uploader POST when the page
     is hosted in an embedded webview, which shows up as an upload that spins
     and then fails — that is what powers "Restore from a backup", the price
     list import and the store logo upload. Safe to disable here: the server
     only ever listens on 127.0.0.1. The upload cap is raised so a large
     backup fits.
"""

import os
import socket
import subprocess
import sys
import time

APP_NAME = "SalesManager"              # folder / process name (no spaces)
WINDOW_TITLE = "Sales Manager — HDM POS"
APP_FILE = "SalesManager.py"
SERVER_FLAG = "SALES_SERVER"
PORT_VAR = "SALES_PORT"
STARTUP_TIMEOUT = 90          # seconds to wait for the server to answer


# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
def base_dir():
    """Where the bundled files live (PyInstaller onedir, or the source tree)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """Per-user writable folder — where the database and activation live."""
    try:
        if os.name == "nt":
            base = (os.environ.get("LOCALAPPDATA")
                    or os.environ.get("APPDATA")
                    or os.path.expanduser("~"))
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library",
                                "Application Support")
        else:
            base = (os.environ.get("XDG_DATA_HOME")
                    or os.path.join(os.path.expanduser("~"), ".local", "share"))
        target = os.path.join(base, APP_NAME)
        os.makedirs(target, exist_ok=True)
        return target
    except Exception:
        return os.getcwd()


def free_port():
    """Ask the OS for a port nothing else is using."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_is_up(port):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ──────────────────────────────────────────────
# Server side (this process when SALES_SERVER=1)
# ──────────────────────────────────────────────
def skip_first_run_prompt():
    """Write credentials.toml so Streamlit does not stop for the email prompt.

    A windowed app has no console to type into, so that prompt is an invisible
    hang. Writing the file first makes Streamlit skip it entirely.
    """
    try:
        folder = os.path.join(os.path.expanduser("~"), ".streamlit")
        os.makedirs(folder, exist_ok=True)
        creds = os.path.join(folder, "credentials.toml")
        if not os.path.exists(creds):
            with open(creds, "w", encoding="utf-8") as f:
                f.write('[general]\nemail = ""\n')
    except Exception:
        pass


def run_server(port):
    """Become the Streamlit server. Never returns."""
    skip_first_run_prompt()
    app_path = os.path.join(base_dir(), APP_FILE)

    # Streamlit reads these before the CLI parses anything — belt and braces
    # in case a flag name changes between versions.
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", "false")
    os.environ.setdefault("STREAMLIT_SERVER_ENABLE_CORS", "false")
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")

    sys.argv = [
        "streamlit", "run", app_path,
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        # No file watching in a frozen bundle: watchdog would walk the whole
        # _internal folder and slow startup badly.
        "--server.fileWatcherType=none",
        # Uploads (Restore from a backup, price-list import, logo): see the
        # module docstring. Localhost only, so this is safe.
        "--server.enableXsrfProtection=false",
        "--server.enableCORS=false",
        # Big enough for a restored backup after years of sales.
        "--server.maxUploadSize=400",
        "--server.runOnSave=false",
        "--browser.gatherUsageStats=false",
        "--browser.serverAddress=127.0.0.1",
        f"--browser.serverPort={port}",
        "--client.toolbarMode=minimal",
        "--client.showErrorDetails=false",
        "--global.developmentMode=false",
        # Theme passed here rather than in a .streamlit/config.toml, so the
        # whole program is a flat set of files with no config folder to lose.
        "--theme.base=light",
        "--theme.primaryColor=#2E6B30",
        "--theme.backgroundColor=#FFFFFF",
        "--theme.secondaryBackgroundColor=#F3F8EE",
        "--theme.textColor=#1F3320",
    ]

    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


# ──────────────────────────────────────────────
# Window side (the process the user launches)
# ──────────────────────────────────────────────
def start_server_process(port):
    """Re-spawn this same executable as a hidden server child."""
    env = os.environ.copy()
    env[SERVER_FLAG] = "1"
    env[PORT_VAR] = str(port)
    # Tells the app it is running inside the native window, so exports — PDF
    # reports, CSV exports, receipts and the database backup — are written
    # straight to the Downloads folder instead of relying on the webview.
    env["SALES_DESKTOP"] = "1"

    if getattr(sys, "frozen", False):
        cmd = [sys.executable]              # SalesManager.exe re-running itself
    else:
        cmd = [sys.executable, os.path.abspath(__file__)]

    kwargs = {"env": env, "cwd": base_dir()}
    if os.name == "nt":
        # No console window flashing up behind the app.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        kwargs["stdin"] = subprocess.DEVNULL
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    return subprocess.Popen(cmd, **kwargs)


def wait_for_server(port, proc):
    """Block until the server answers, or give up."""
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if server_is_up(port):
            return True
        if proc.poll() is not None:        # the child died on us
            return False
        time.sleep(0.3)
    return False


def configure_webview(webview):
    """Everything WebView2 needs before a window exists.

    Returns the profile path so webview.start() can be told about it.
    """
    profile = os.path.join(data_dir(), "WebView2")
    try:
        os.makedirs(profile, exist_ok=True)
    except Exception:
        pass
    # A read-only Program Files profile is the usual reason a window never
    # appears, or appears but cannot download.
    os.environ.setdefault("WEBVIEW2_USER_DATA_FOLDER", profile)

    # pywebview 5 exposes a module-level settings dict and ships with
    # downloads off; pywebview 4 has no such dict and allows them anyway.
    try:
        settings = getattr(webview, "settings", None)
        if isinstance(settings, dict):
            settings["ALLOW_DOWNLOADS"] = True
            settings.setdefault("ALLOW_FILE_URLS", True)
            settings.setdefault("OPEN_EXTERNAL_LINKS_IN_BROWSER", True)
    except Exception:
        pass

    return profile


def open_native_window(url):
    """The real desktop window. Returns True if it ran."""
    try:
        import webview
    except Exception:
        return False

    profile = configure_webview(webview)

    try:
        webview.create_window(
            WINDOW_TITLE, url,
            width=1320, height=860,
            min_size=(960, 640),
            resizable=True,
            text_select=True,
            confirm_close=False,
            background_color="#FFFFFF",
        )
    except TypeError:
        # Older pywebview: fewer keyword arguments.
        webview.create_window(WINDOW_TITLE, url, width=1320, height=860,
                              resizable=True)

    for attempt in ({"private_mode": False, "storage_path": profile},
                    {"private_mode": False},
                    {}):
        try:
            webview.start(**attempt)
            return True
        except TypeError:
            continue                      # this version lacks those kwargs
        except Exception:
            return False
    return False


def open_app_window_fallback(url):
    """No pywebview: borrow Edge or Chrome in app mode — still no browser UI."""
    if os.name != "nt":
        return False
    profile = os.path.join(data_dir(), "BrowserProfile")
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for exe in candidates:
        if exe and os.path.exists(exe):
            try:
                subprocess.run([exe, f"--app={url}", "--window-size=1320,860",
                                f"--user-data-dir={profile}"], check=False)
                return True
            except Exception:
                continue
    return False


def open_browser_fallback(url):
    """Last resort — the app always opens, even if it looks like a tab."""
    try:
        import webbrowser
        webbrowser.open(url)
        # Nothing to wait on, so hold the process until the user closes it.
        input()
        return True
    except Exception:
        return False


def show_error(message):
    """Tell the user something, even with no console attached."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, WINDOW_TITLE, 0x10)
    except Exception:
        sys.stderr.write(message + "\n")


def main():
    # Child process? Then be the server and nothing else.
    if os.environ.get(SERVER_FLAG) == "1":
        run_server(int(os.environ.get(PORT_VAR) or free_port()))
        return

    # Database and activation marker live in %LOCALAPPDATA%\SalesManager — a
    # writable folder that survives reinstalls — not beside the .exe.
    folder = data_dir()
    os.environ.setdefault("SALES_DB_PATH", os.path.join(folder, "feedstore.db"))
    os.environ.setdefault("SALES_ACTIVATION_PATH",
                          os.path.join(folder, ".hdm_pos_activation"))

    port = free_port()
    url = f"http://127.0.0.1:{port}"

    proc = start_server_process(port)
    try:
        if not wait_for_server(port, proc):
            show_error("Sales Manager could not start its internal server.\n\n"
                       "Try launching it again. If it keeps happening, restart "
                       "the computer and try once more.")
            return

        if open_native_window(url):
            return
        if open_app_window_fallback(url):
            return
        open_browser_fallback(url)
    finally:
        # Closing the window must close the program — no stray background
        # process left holding the database open.
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
