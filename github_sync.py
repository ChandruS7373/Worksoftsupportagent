"""
GitHub DB Sync
==============
Push/pull worksoft_support.db to/from a GitHub repository so the knowledge
base is persisted in the cloud and shared across deployments.

Config (set in .streamlit/secrets.toml or as environment variables):
  GITHUB_TOKEN    - personal access token with repo read/write scope
  GITHUB_REPO     - "owner/repo-name"  e.g. "aravind/worksoft-agent"
  GITHUB_DB_PATH  - path inside the repo  (default: "worksoft_support.db")
"""

import os
import base64
import sqlite3
import requests
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────

def _cfg():
    """Return (token, repo, db_path_in_repo) from secrets or env."""
    try:
        import streamlit as st
        tok  = st.secrets.get("GITHUB_TOKEN",   "") or os.environ.get("GITHUB_TOKEN",   "")
        repo = st.secrets.get("GITHUB_REPO",    "") or os.environ.get("GITHUB_REPO",    "")
        path = st.secrets.get("GITHUB_DB_PATH", "") or os.environ.get("GITHUB_DB_PATH", "worksoft_support.db")
    except Exception:
        tok  = os.environ.get("GITHUB_TOKEN",   "")
        repo = os.environ.get("GITHUB_REPO",    "")
        path = os.environ.get("GITHUB_DB_PATH", "worksoft_support.db")
    return tok.strip(), repo.strip(), path.strip() or "worksoft_support.db"


def _local_db_path():
    """Return the local DB path (same logic as support_db)."""
    return os.environ.get(
        "SUPPORT_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "worksoft_support.db"),
    )


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

def _checkpoint_wal(db_path: str):
    """Flush WAL into the main .db file before upload."""
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.close()
    except Exception:
        pass


def _get_remote_sha(token: str, repo: str, remote_path: str) -> str | None:
    """Return the current SHA of the file on GitHub, or None if it doesn't exist."""
    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    r   = requests.get(url, headers=_headers(token), timeout=15)
    if r.status_code == 200:
        return r.json().get("sha")
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def push_db(message: str = "") -> tuple[bool, str]:
    """
    Upload the local DB to GitHub.
    Creates the file if it doesn't exist; updates it (with SHA) if it does.
    Returns (success, message).
    """
    token, repo, remote_path = _cfg()
    if not token:
        return False, "GITHUB_TOKEN not set in secrets.toml."
    if not repo:
        return False, "GITHUB_REPO not set in secrets.toml  (e.g. 'username/repo-name')."

    db_path = _local_db_path()
    if not os.path.exists(db_path):
        return False, f"Local DB not found: {db_path}"

    _checkpoint_wal(db_path)

    with open(db_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    sha = _get_remote_sha(token, repo, remote_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = message or f"sync: update DB  [{now}]"

    payload = {"message": commit_msg, "content": content_b64}
    if sha:
        payload["sha"] = sha

    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    r   = requests.put(url, json=payload, headers=_headers(token), timeout=30)

    if r.status_code in (200, 201):
        size_kb = os.path.getsize(db_path) // 1024
        action  = "updated" if sha else "created"
        return True, f"DB {action} on GitHub  ({size_kb} KB)."
    else:
        err = r.json().get("message", r.text[:200])
        return False, f"GitHub push failed ({r.status_code}): {err}"


def pull_db() -> tuple[bool, str]:
    """
    Download the DB from GitHub and replace the local copy.
    A .bak backup of the current local file is kept.
    Returns (success, message).
    """
    token, repo, remote_path = _cfg()
    if not token:
        return False, "GITHUB_TOKEN not set in secrets.toml."
    if not repo:
        return False, "GITHUB_REPO not set in secrets.toml."

    db_path = _local_db_path()

    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    r   = requests.get(
        url,
        headers={**_headers(token), "Accept": "application/vnd.github.v3.raw"},
        timeout=30,
    )

    if r.status_code == 404:
        return False, "DB file not found in the GitHub repo — push it first."
    if r.status_code != 200:
        return False, f"GitHub pull failed ({r.status_code}): {r.text[:200]}"

    # Backup current local DB before overwriting
    if os.path.exists(db_path):
        bak = db_path + ".bak"
        with open(db_path, "rb") as fin, open(bak, "wb") as fout:
            fout.write(fin.read())

    with open(db_path, "wb") as f:
        f.write(r.content)

    size_kb = len(r.content) // 1024
    return True, f"DB pulled from GitHub  ({size_kb} KB).  Previous copy saved as .bak"


def remote_info() -> dict:
    """
    Return metadata about the remote DB file:
      sha, size_kb, html_url, last_commit_date
    Returns empty dict if not configured or file doesn't exist.
    """
    token, repo, remote_path = _cfg()
    if not token or not repo:
        return {}
    try:
        url  = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
        r    = requests.get(url, headers=_headers(token), timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()

        # Get last commit date via commits API
        commits_url = f"https://api.github.com/repos/{repo}/commits"
        cr = requests.get(
            commits_url,
            params={"path": remote_path, "per_page": 1},
            headers=_headers(token),
            timeout=10,
        )
        last_updated = ""
        if cr.status_code == 200 and cr.json():
            raw_date = cr.json()[0]["commit"]["committer"]["date"]  # ISO 8601
            last_updated = raw_date[:16].replace("T", " ")

        return {
            "sha":          data.get("sha", "")[:7],
            "size_kb":      data.get("size", 0) // 1024,
            "html_url":     data.get("html_url", ""),
            "last_updated": last_updated,
        }
    except Exception:
        return {}


def is_configured() -> bool:
    """Return True if GitHub token + repo are set."""
    token, repo, _ = _cfg()
    return bool(token and repo)
