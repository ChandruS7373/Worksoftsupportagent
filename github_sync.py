"""
GitHub DB Sync – Worksoft Support Agent
=======================================
• Downloads DB from GitHub on first startup (so Streamlit Cloud survives restarts).
• Background thread watches the DB file every 5 s and pushes any change to GitHub.
• push_now() triggers an immediate async push — call after any DB write.
"""

import os
import base64
import sqlite3
import threading
import time
import requests
from datetime import datetime

_DB_PATH              = os.path.join(os.path.dirname(os.path.abspath(__file__)), "worksoft_support.db")
_PUSH_INTERVAL        = 5    # seconds between file-change checks (near-real-time)
_lock                 = threading.Lock()
_db_downloaded        = False
_sync_started         = False
_push_queue           = threading.Event()  # set this to trigger an immediate push
_last_download_attempt = 0.0               # epoch time of last download attempt
_DOWNLOAD_COOLDOWN    = 60                 # min seconds between retry attempts


# ── Config ──────────────────────────────────────────────────────────────────

def _cfg():
    try:
        import streamlit as st
        token  = st.secrets.get("GITHUB_TOKEN",   "") or os.environ.get("GITHUB_TOKEN",   "")
        repo   = st.secrets.get("GITHUB_REPO",    "") or os.environ.get("GITHUB_REPO",    "")
        branch = st.secrets.get("GITHUB_BRANCH",  "main")
        path   = st.secrets.get("GITHUB_DB_PATH", "worksoft_support.db") or "worksoft_support.db"
    except Exception:
        token  = os.environ.get("GITHUB_TOKEN",   "")
        repo   = os.environ.get("GITHUB_REPO",    "")
        branch = "main"
        path   = os.environ.get("GITHUB_DB_PATH", "worksoft_support.db")
    return token.strip(), repo.strip(), branch.strip() or "main", path.strip() or "worksoft_support.db"


def _headers(token: str) -> dict:
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}


def is_configured() -> bool:
    token, repo, _, _ = _cfg()
    return bool(token and repo)


# ── Download ─────────────────────────────────────────────────────────────────

def download_db() -> bool:
    """Download DB from GitHub into the local path. Returns True on success."""
    try:
        token, repo, branch, db_path = _cfg()
        if not token or not repo:
            return False
        url  = f"https://api.github.com/repos/{repo}/contents/{db_path}?ref={branch}"
        resp = requests.get(url, headers=_headers(token), timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # Prefer inline base64 content — direct from API, no CDN caching
            raw_b64 = (data.get("content") or "").replace("\n", "")
            if raw_b64:
                raw = base64.b64decode(raw_b64)
                with _lock:
                    with open(_DB_PATH, "wb") as f:
                        f.write(raw)
                print(f"[GH Sync] DB downloaded from GitHub ({len(raw) // 1024} KB).")
                return True
            # File > 1 MB: fall back to download_url with cache-busting
            raw_url = data.get("download_url", "")
            if raw_url:
                sep = "&" if "?" in raw_url else "?"
                raw_resp = requests.get(
                    f"{raw_url}{sep}_={int(time.time())}",
                    headers={"Authorization": f"token {token}", "Cache-Control": "no-cache"},
                    timeout=60,
                )
                if raw_resp.status_code == 200:
                    with _lock:
                        with open(_DB_PATH, "wb") as f:
                            f.write(raw_resp.content)
                    print(f"[GH Sync] DB downloaded from GitHub ({len(raw_resp.content) // 1024} KB, download_url).")
                    return True
        elif resp.status_code == 404:
            print("[GH Sync] No DB in repo yet — will create on first push.")
    except Exception as e:
        print(f"[GH Sync] Download error: {e}")
    return False


# ── Upload ───────────────────────────────────────────────────────────────────

def push_db(message: str = "") -> tuple:
    """Upload local DB to GitHub. Returns (success: bool, message: str)."""
    try:
        token, repo, branch, db_path = _cfg()
        if not token:
            return False, "GITHUB_TOKEN not set in secrets.toml."
        if not repo:
            return False, "GITHUB_REPO not set in secrets.toml."

        with _lock:
            if not os.path.exists(_DB_PATH):
                return False, f"Local DB not found: {_DB_PATH}"
            try:
                conn = sqlite3.connect(_DB_PATH, timeout=10)
                conn.execute("PRAGMA wal_checkpoint(FULL)")
                conn.close()
            except Exception:
                pass
            with open(_DB_PATH, "rb") as f:
                content = base64.b64encode(f.read()).decode()

        url = f"https://api.github.com/repos/{repo}/contents/{db_path}"

        def _get_sha() -> str:
            r = requests.get(f"{url}?ref={branch}", headers=_headers(token), timeout=30)
            return r.json().get("sha", "") if r.status_code == 200 else ""

        def _do_put(sha: str):
            commit_msg = message or f"sync: update DB [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"
            payload = {"message": commit_msg, "content": content, "branch": branch}
            if sha:
                payload["sha"] = sha
            return requests.put(url, json=payload, headers=_headers(token), timeout=60)

        sha = _get_sha()
        put = _do_put(sha)

        if put.status_code in (200, 201):
            size_kb = os.path.getsize(_DB_PATH) // 1024
            action  = "updated" if sha else "created"
            print(f"[GH Sync] DB {action} on GitHub ({size_kb} KB).")
            return True, f"DB {action} on GitHub ({size_kb} KB)."
        elif put.status_code == 409:
            # SHA conflict — background thread may have just pushed; retry with fresh SHA
            sha2 = _get_sha()
            if sha2:
                put2 = _do_put(sha2)
                if put2.status_code in (200, 201):
                    size_kb = os.path.getsize(_DB_PATH) // 1024
                    print(f"[GH Sync] DB updated on GitHub ({size_kb} KB, retry ok).")
                    return True, f"DB updated on GitHub ({size_kb} KB)."
            # Background thread already pushed the same data — treat as success
            print("[GH Sync] Push skipped (already up-to-date on GitHub).")
            return True, "DB already up-to-date on GitHub."
        else:
            err = put.json().get("message", put.text[:200])
            print(f"[GH Sync] Push failed ({put.status_code}): {err}")
            return False, f"GitHub push failed ({put.status_code}): {err}"
    except Exception as e:
        return False, f"GitHub push error: {e}"


# ── Background auto-push ─────────────────────────────────────────────────────

def _sync_loop():
    """
    Watches the DB file every _PUSH_INTERVAL seconds.
    Also wakes up immediately when push_now() is called via _push_queue.
    Pushes to GitHub whenever the file modification time changes.
    """
    last_mtime = os.path.getmtime(_DB_PATH) if os.path.exists(_DB_PATH) else 0
    while True:
        # Wake up after interval OR immediately if push_now() was called
        triggered = _push_queue.wait(timeout=_PUSH_INTERVAL)
        _push_queue.clear()
        try:
            if os.path.exists(_DB_PATH):
                mtime = os.path.getmtime(_DB_PATH)
                if mtime != last_mtime or triggered:
                    push_db()
                    last_mtime = os.path.getmtime(_DB_PATH)
        except Exception as e:
            print(f"[GH Sync] Loop error: {e}")


def push_now():
    """
    Signal the background thread to push immediately.
    Call this after any write to the DB — returns instantly (non-blocking).
    """
    _push_queue.set()


def _has_local_data() -> bool:
    """Return True if the local DB already has sf_knowledge rows."""
    if not os.path.exists(_DB_PATH):
        return False
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=5)
        count = conn.execute("SELECT COUNT(*) FROM sf_knowledge").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def ensure_db_downloaded():
    """
    Call at app startup — downloads DB from GitHub when needed:
    - First call this process: always download.
    - Subsequent reruns in same process: re-download only if local DB is empty
      (handles case where the previous download failed silently).
    - Cooldown of 60 s prevents hammering GitHub API on every rerun.
    """
    global _db_downloaded, _last_download_attempt
    now = time.time()
    if not _db_downloaded:
        _db_downloaded = True
        _last_download_attempt = now
        download_db()
    elif not _has_local_data() and (now - _last_download_attempt) > _DOWNLOAD_COOLDOWN:
        # Local DB is empty — retry GitHub download (previous attempt may have failed)
        _last_download_attempt = now
        download_db()


def start_sync_thread():
    """Start background thread that auto-pushes DB to GitHub when it changes."""
    global _sync_started
    if not _sync_started:
        _sync_started = True
        threading.Thread(target=_sync_loop, daemon=True).start()
        print("[GH Sync] Background sync thread started.")


# ── Remote info ──────────────────────────────────────────────────────────────

def remote_info() -> dict:
    """Return metadata about the remote DB file (sha, size, last updated)."""
    token, repo, branch, db_path = _cfg()
    if not token or not repo:
        return {}
    try:
        url  = f"https://api.github.com/repos/{repo}/contents/{db_path}?ref={branch}"
        r    = requests.get(url, headers=_headers(token), timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        cr   = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={"path": db_path, "per_page": 1},
            headers=_headers(token), timeout=10,
        )
        last_updated = ""
        if cr.status_code == 200 and cr.json():
            last_updated = cr.json()[0]["commit"]["committer"]["date"][:16].replace("T", " ")
        return {
            "sha":          data.get("sha", "")[:7],
            "size_kb":      data.get("size", 0) // 1024,
            "html_url":     data.get("html_url", ""),
            "last_updated": last_updated,
        }
    except Exception:
        return {}
