import os
import re
import base64
import requests as _req
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from html.parser import HTMLParser
import streamlit as st

import support_db
import github_sync


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities from Salesforce rich-text fields."""
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, d):
            self.parts.append(d)
    p = _S()
    p.feed(html or "")
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════
def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default) or default
    except Exception:
        return os.environ.get(key, default)

ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = _secret("OPENAI_API_KEY")
SF_USERNAME       = _secret("SF_USERNAME")
SF_PASSWORD       = _secret("SF_PASSWORD")
SF_SECURITY_TOKEN = _secret("SF_SECURITY_TOKEN")
SF_CLIENT_ID      = _secret("SF_CLIENT_ID")
SF_CLIENT_SECRET  = _secret("SF_CLIENT_SECRET")
SF_DOMAIN         = _secret("SF_DOMAIN", "login")
SF_INSTANCE_URL   = _secret("SF_INSTANCE_URL", "")
IT_ADMIN_EMAIL    = _secret("IT_ADMIN_EMAIL", "it-admin@qualesce.com")
PORTAL_URL        = SF_INSTANCE_URL or f"https://{SF_DOMAIN}.salesforce.com"

st.set_page_config(
    page_title="Worksoft Support | Qualesce",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── RESET ── */
*{box-sizing:border-box;margin:0;padding:0;}
html,body,[data-testid="stAppViewContainer"]{background:#f0f4ff!important;}
header,#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stSidebar"]{display:none!important;}
[data-testid="stMain"]>div{padding-top:0!important;}
.block-container{max-width:100%!important;padding:4px 12px 0!important;}

/* ── NAVBAR ── */
.nav{
  height:52px;background:#fff;
  border-bottom:2px solid #e0e7ff;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;margin-bottom:10px;border-radius:14px;
  box-shadow:0 1px 8px rgba(99,102,241,.08);
}
.nav-left{display:flex;align-items:center;gap:10px;}
.nav-logo{
  width:34px;height:34px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;
  font-size:18px;box-shadow:0 2px 8px rgba(59,130,246,.35);
}
.nav-title{font-size:14px;font-weight:800;color:#0f172a;letter-spacing:-.2px;}
.nav-sub{font-size:10px;color:#94a3b8;margin-top:1px;}
.nav-right{display:flex;align-items:center;gap:8px;}
.nav-pill{
  font-size:11px;font-weight:700;padding:4px 12px;border-radius:99px;
  background:linear-gradient(135deg,#1e40af,#3b82f6);color:#fff;
  letter-spacing:.4px;
}
.nav-user{font-size:12px;font-weight:600;color:#1e40af;
  background:#eff6ff;border:1.5px solid #bfdbfe;
  padding:4px 12px;border-radius:99px;}

/* ── LEFT PANEL ── */
.lp{
  background:#1e293b;border-radius:16px;
  padding:20px 16px;display:flex;flex-direction:column;gap:14px;
  box-shadow:0 4px 20px rgba(15,23,42,.25);
}
.lp-logo{display:flex;align-items:center;gap:10px;
  padding-bottom:14px;border-bottom:1px solid rgba(255,255,255,.07);}
.lp-av{width:38px;height:38px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:20px;
  box-shadow:0 2px 10px rgba(59,130,246,.4);}
.lp-t{font-size:13px;font-weight:800;color:#f1f5f9;}
.lp-s{font-size:10px;color:#64748b;margin-top:1px;}
.lp-status{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);
  color:#4ade80;font-size:10px;font-weight:700;
  padding:4px 10px;border-radius:99px;text-transform:uppercase;letter-spacing:.4px;
  width:fit-content;
}
.lp-dot{width:5px;height:5px;border-radius:50%;background:#22c55e;
  animation:pulse 1.6s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.4)}}
.lp-sec-title{font-size:9px;font-weight:700;color:#475569;
  text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px;}
.lp-stat{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.07);
  border-radius:10px;padding:12px 14px;}
.lp-num{font-size:26px;font-weight:900;color:#e2e8f0;line-height:1;}
.lp-numlbl{font-size:10px;color:#64748b;margin-top:3px;}
.lp-feature{display:flex;align-items:center;gap:8px;padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,.04);font-size:11px;color:#94a3b8;}
.lp-feature:last-child{border-bottom:none;}
.lp-user{
  margin-top:auto;background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:10px 12px;
}
.lp-uname{font-size:12px;font-weight:700;color:#e2e8f0;}
.lp-uemail{font-size:10px;color:#64748b;margin-top:2px;}

/* ── CHAT WINDOW ── */
.cwin{
  background:#fff;border-radius:16px;
  border:1.5px solid #e0e7ff;
  box-shadow:0 4px 20px rgba(99,102,241,.08);
  overflow:hidden;
}
.chead{
  height:58px;display:flex;align-items:center;justify-content:space-between;
  padding:0 18px;background:#fff;
  border-bottom:1.5px solid #f1f5f9;
}
.chead-left{display:flex;align-items:center;gap:10px;}
.chead-av{
  width:36px;height:36px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:19px;
  box-shadow:0 2px 8px rgba(59,130,246,.3);
}
.chead-name{font-size:13px;font-weight:800;color:#0f172a;}
.chead-sub{font-size:10px;color:#64748b;margin-top:1px;}
.chead-status{
  display:inline-flex;align-items:center;gap:4px;
  background:#f0fdf4;border:1px solid #bbf7d0;color:#16a34a;
  font-size:9px;font-weight:700;padding:2px 8px;border-radius:99px;
  text-transform:uppercase;letter-spacing:.3px;
}
.chead-dot{width:4px;height:4px;border-radius:50%;background:#22c55e;
  animation:pulse 1.6s infinite;}
.chead-rt{text-align:right;}
.chead-rt-lbl{font-size:9px;color:#94a3b8;text-transform:uppercase;letter-spacing:.4px;}
.chead-rt-val{font-size:11px;font-weight:700;color:#16a34a;}

/* ── INPUT BAR ── */
.cinput{
  background:#f8faff;border-top:1.5px solid #f1f5f9;
  padding:10px 14px;
}

/* ── INPUT BOX ── */
.input-box{
  background:#fff;border:1.5px solid #dbeafe;border-radius:14px;
  padding:6px 8px;display:flex;align-items:flex-end;gap:6px;
  box-shadow:0 1px 6px rgba(99,102,241,.08);transition:.2s;
}
.input-box:focus-within{border-color:#3b82f6!important;
  box-shadow:0 2px 14px rgba(59,130,246,.15)!important;}

/* ── INPUT TEXT AREA ── */
.input-bar .stTextArea textarea{
  background:transparent!important;border:none!important;
  color:#0f172a!important;font-size:13px!important;
  line-height:1.5!important;resize:none!important;
  box-shadow:none!important;outline:none!important;padding:6px 4px!important;
}
.input-bar .stTextArea textarea::placeholder{color:#94a3b8!important;font-size:13px!important;}
.input-bar .stTextArea textarea:focus{box-shadow:none!important;border:none!important;}
.input-bar div[data-baseweb="textarea"]{background:transparent!important;border:none!important;}
.input-bar .stTextArea label{display:none!important;}
.input-bar [data-testid="stHorizontalBlock"]{align-items:center!important;}
.input-bar [data-testid="stHorizontalBlock"] [data-testid="column"]{
  display:flex!important;align-items:center!important;padding-bottom:0!important;}

/* ── FILE UPLOADER IN BAR ── */
div[data-testid="stFileUploader"]{min-height:0!important;}
div[data-testid="stFileUploader"]>label{display:none!important;}
section[data-testid="stFileUploaderDropzone"]{
  min-height:38px!important;max-height:38px!important;padding:0 4px!important;
  border:1.5px solid #bfdbfe!important;background:#eff6ff!important;
  border-radius:10px!important;display:flex!important;align-items:center!important;
  justify-content:center!important;overflow:hidden!important;}
section[data-testid="stFileUploaderDropzone"]>div{
  flex-direction:row!important;gap:0!important;align-items:center!important;
  width:100%!important;justify-content:center!important;}
section[data-testid="stFileUploaderDropzone"]>div>div:first-child{display:none!important;}
section[data-testid="stFileUploaderDropzone"] button{
  background:transparent!important;border:none!important;padding:0!important;
  min-height:0!important;width:auto!important;height:auto!important;
  font-size:0!important;cursor:pointer!important;box-shadow:none!important;
  display:flex!important;align-items:center!important;justify-content:center!important;}
section[data-testid="stFileUploaderDropzone"] button::before{
  content:"📎";font-size:18px;line-height:1;display:block;}
div[data-testid="stFileUploader"] small{display:none!important;}
[data-testid="stFileUploaderDeleteBtn"]{color:#dc2626!important;}
div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"]{
  font-size:10px!important;max-width:100px!important;overflow:hidden!important;
  white-space:nowrap!important;text-overflow:ellipsis!important;}

/* ── HOME FILE UPLOADER ── */
.home-upload div[data-testid="stFileUploader"]>label{
  font-size:12px!important;font-weight:600!important;color:#374151!important;
  margin-bottom:4px!important;display:block!important;}
.home-upload section[data-testid="stFileUploaderDropzone"]{
  border:2px dashed #93c5fd!important;background:#f0f7ff!important;
  border-radius:12px!important;padding:16px!important;
  min-height:auto!important;max-height:none!important;}
.home-upload section[data-testid="stFileUploaderDropzone"] button{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;border-radius:7px!important;
  font-size:12px!important;font-weight:700!important;padding:6px 14px!important;
  cursor:pointer!important;width:auto!important;height:auto!important;}

/* ── SEND BUTTON ── */
.stFormSubmitButton button{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;border-radius:10px!important;
  font-weight:700!important;box-shadow:0 2px 10px rgba(37,99,235,.3)!important;
  transition:all .18s!important;
}
.stFormSubmitButton button:hover{
  box-shadow:0 4px 16px rgba(37,99,235,.45)!important;transform:translateY(-1px)!important;}
.input-bar .stFormSubmitButton button{
  height:38px!important;width:38px!important;padding:0!important;
  font-size:18px!important;min-height:0!important;border-radius:10px!important;}

/* ── BUTTONS ── */
.stButton>button{
  border-radius:10px!important;font-weight:600!important;font-size:12px!important;
  padding:7px 16px!important;transition:all .18s!important;
  min-height:34px!important;line-height:1.2!important;
}
.stButton>button[kind="primary"],button[kind="primary"]{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;
  box-shadow:0 2px 10px rgba(37,99,235,.28)!important;}
.stButton>button[kind="primary"]:hover{
  box-shadow:0 4px 16px rgba(37,99,235,.42)!important;transform:translateY(-1px)!important;}
.stButton>button:not([kind="primary"]){
  background:#fff!important;color:#1e40af!important;
  border:1.5px solid #bfdbfe!important;}
.stButton>button:not([kind="primary"]):hover{
  background:#eff6ff!important;border-color:#3b82f6!important;transform:translateY(-1px)!important;}

/* ── FORM INPUTS ── */
.stTextArea label,.stTextInput label{
  font-size:12px!important;font-weight:600!important;color:#374151!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{
  background:#fff!important;color:#0f172a!important;
  border:1.5px solid #c7d2fe!important;border-radius:10px!important;font-size:13px!important;}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{
  border-color:#3b82f6!important;box-shadow:0 0 0 3px rgba(59,130,246,.1)!important;}
[data-testid="stAlert"]{border-radius:12px!important;}

/* ── LOGIN CARD ── */
.login-wrap{max-width:500px;margin:20px auto;}
.login-banner{
  background:linear-gradient(135deg,#1e3a8a,#1e40af,#0ea5e9);
  border-radius:18px 18px 0 0;padding:28px 28px 22px;text-align:center;}
.login-icon{font-size:44px;margin-bottom:8px;}
.login-title{font-size:20px;font-weight:900;color:#fff;letter-spacing:-.3px;}
.login-sub{font-size:12px;color:rgba(255,255,255,.7);margin-top:5px;}
.login-chips{display:flex;justify-content:center;gap:6px;flex-wrap:wrap;margin-top:12px;}
.chip{font-size:10px;font-weight:700;padding:4px 11px;border-radius:99px;
  background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);color:#fff;}
.login-body{
  background:#fff;border-radius:0 0 18px 18px;
  border:1.5px solid #e0e7ff;border-top:none;padding:22px 28px;}

/* ── TICKET ── */
.ticket-card{background:#fff;border:1.5px solid #bfdbfe;border-radius:18px;
  box-shadow:0 4px 20px rgba(30,64,175,.08);padding:20px 24px;margin:12px auto;max-width:460px;}
.ticket-id{font-size:10px;font-weight:700;color:#1e40af;letter-spacing:.5px;text-transform:uppercase;}
.ticket-num{font-size:22px;font-weight:900;color:#0f172a;margin:3px 0 12px;}
.ticket-row{display:flex;gap:8px;align-items:flex-start;margin-bottom:6px;font-size:12px;}
.ticket-lbl{color:#64748b;min-width:70px;flex-shrink:0;}
.ticket-val{color:#0f172a;font-weight:600;word-break:break-all;}
.ticket-link{
  display:inline-flex;align-items:center;gap:5px;margin-top:12px;
  background:linear-gradient(135deg,#1e40af,#3b82f6);color:#fff!important;
  text-decoration:none;font-size:12px;font-weight:700;
  padding:7px 18px;border-radius:10px;box-shadow:0 3px 12px rgba(30,64,175,.28);}
.badge-new{display:inline-block;background:#dbeafe;color:#1e40af;
  font-size:9px;font-weight:700;padding:2px 8px;border-radius:99px;
  text-transform:uppercase;letter-spacing:.4px;}

@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.anim{animation:fadeUp .3s ease both;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "page":                    "chat",
        "user":                    {"name": "Guest", "email": ""},
        "messages":                [],
        "issue_text":              "",
        "sf_ticket":               None,
        "fu_key":                  0,
        "pending_file":            None,
        "session_id":              None,
        "sf_resolution":           "",
        "sf_case_context":         "",
        "sf_steps":                [],
        "sf_step_idx":             0,
        "chat_phase":              "idle",
        "initial_issue":           "",
        "resolution_check_shown":  False,
        "show_resolution_popup":   False,
        "chat_started":            False,
        "sf_diagnosis":            "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

github_sync.ensure_db_downloaded()   # MUST be before init_db — downloads synced DB from GitHub before creating empty one
github_sync.start_sync_thread()       # auto-push DB to GitHub every 30s when it changes
support_db.init_db()                  # creates tables if they don't exist (no-op if DB already has data)
_init_state()


# ═══════════════════════════════════════════════════════════
# SALESFORCE
# ═══════════════════════════════════════════════════════════
def _sf_client():
    from simple_salesforce import Salesforce
    resp = _req.post(
        f"https://{SF_DOMAIN}.salesforce.com/services/oauth2/token",
        data={
            "grant_type": "password", "client_id": SF_CLIENT_ID,
            "client_secret": SF_CLIENT_SECRET, "username": SF_USERNAME,
            "password": SF_PASSWORD + SF_SECURITY_TOKEN,
        }, timeout=15)
    resp.raise_for_status()
    t = resp.json()
    return Salesforce(session_id=t["access_token"], instance_url=t["instance_url"])


def sf_create_case(subject, description, user_name, user_email, priority="High"):
    sf  = _sf_client()
    res = sf.Case.create({
        "Subject": subject,
        "Description": f"Reported By: {user_name}\nEmail: {user_email}\n\n{description}",
        "Status": "New", "Priority": priority, "Origin": "Web",
    })
    cid  = res["id"]
    data = sf.Case.get(cid)
    url  = sf.base_url.split("/services")[0] + f"/lightning/r/Case/{cid}/view"
    return {"id": cid, "case_number": data.get("CaseNumber", cid), "url": url}


# ═══════════════════════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════════════════════
def _smtp_creds():
    return _secret("OUTLOOK_EMAIL"), _secret("OUTLOOK_PASSWORD")


def _send_smtp(sender, password, to, subject, body, cc=""):
    msg = MIMEMultipart("alternative")
    msg["From"] = sender; msg["To"] = to; msg["Subject"] = subject
    if cc: msg["CC"] = cc
    msg.attach(MIMEText(body, "html"))
    recipients = [to] + ([cc] if cc else [])
    last_err = ""
    for host, port in [("smtp.office365.com", 587), ("smtp.gmail.com", 587)]:
        try:
            with smtplib.SMTP(host, port) as srv:
                srv.ehlo(); srv.starttls(); srv.login(sender, password)
                srv.sendmail(sender, recipients, msg.as_string())
            return True, ""
        except Exception as exc:
            last_err = str(exc)
    return False, last_err


def send_escalation_email(ticket, user_name, user_email, issue, conversation):
    sender, password = _smtp_creds()
    if not sender or not password:
        return False, "SMTP credentials not configured"

    case_num = ticket.get("case_number", ticket.get("id", "N/A"))
    case_url = ticket.get("url", "#")
    created  = datetime.now().strftime("%d %b %Y, %H:%M")
    priority = ticket.get("priority", "High")

    sf_btn = (
        f'<a href="{case_url}" style="display:inline-block;background:linear-gradient(135deg,#1d4ed8,#3b82f6);'
        f'color:#fff;text-decoration:none;font-weight:700;font-size:13px;padding:10px 24px;'
        f'border-radius:10px;margin-top:4px;">🔗 View Case in Salesforce</a>'
        if case_url != "#sf-not-configured" else
        '<p style="color:#94a3b8;font-size:12px;">Salesforce link unavailable.</p>'
    )

    html = f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     max-width:600px;margin:0 auto;padding:32px;background:#0f172a;border-radius:16px;color:#e2e8f0;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;">
    <div style="font-size:26px;font-weight:900;color:#3b82f6;">Q</div>
    <div>
      <div style="font-size:16px;font-weight:800;color:#f1f5f9;">Worksoft Support Escalation</div>
      <div style="font-size:12px;color:#64748b;">Qualesce AI Support Agent</div>
    </div>
  </div>
  <div style="background:rgba(59,130,246,.15);border-left:4px solid #3b82f6;border-radius:0 10px 10px 0;
       padding:14px 18px;margin-bottom:20px;">
    <div style="font-size:10px;font-weight:700;color:#93c5fd;text-transform:uppercase;margin-bottom:4px;">New Case</div>
    <div style="font-size:22px;font-weight:900;color:#f1f5f9;">#{case_num}</div>
    <div style="font-size:12px;color:#94a3b8;margin-top:4px;">Created: {created}</div>
  </div>
  <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;
       padding:16px 20px;margin-bottom:14px;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="padding:4px 0;color:#94a3b8;width:35%;">Reported By</td>
          <td style="padding:4px 0;font-weight:600;color:#f1f5f9;">{user_name}</td></tr>
      <tr><td style="padding:4px 0;color:#94a3b8;">Email</td>
          <td style="padding:4px 0;font-weight:600;color:#f1f5f9;">{user_email}</td></tr>
      <tr><td style="padding:4px 0;color:#94a3b8;">Priority</td>
          <td><span style="background:rgba(220,38,38,.2);color:#f87171;font-size:10px;
                font-weight:700;padding:2px 10px;border-radius:99px;">{priority.upper()}</span></td></tr>
    </table>
  </div>
  <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;
       padding:16px 20px;margin-bottom:14px;">
    <div style="font-size:12px;font-weight:700;color:#93c5fd;margin-bottom:8px;">ISSUE</div>
    <div style="font-size:13px;color:#cbd5e1;line-height:1.6;white-space:pre-wrap;">{issue}</div>
  </div>
  <div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;
       padding:16px 20px;margin-bottom:20px;">
    <div style="font-size:12px;font-weight:700;color:#93c5fd;margin-bottom:8px;">AI CHAT CONVERSATION</div>
    <div style="font-size:12px;color:#94a3b8;line-height:1.7;white-space:pre-wrap;
         background:rgba(0,0,0,.2);border-radius:6px;padding:12px;">{conversation}</div>
  </div>
  {sf_btn}
  <p style="color:#475569;font-size:11px;border-top:1px solid rgba(255,255,255,.08);
     padding-top:14px;margin:20px 0 0;">
    Automated escalation · Qualesce Worksoft Support Portal
  </p>
</div>"""

    return _send_smtp(sender, password, IT_ADMIN_EMAIL,
                      f"[Worksoft Support] New Escalation – Case {case_num}",
                      html, cc=user_email)


# ═══════════════════════════════════════════════════════════
# FILE PROCESSING
# ═══════════════════════════════════════════════════════════
def _process_upload(f):
    if f is None: return None
    name = f.name
    mime = f.type or ""
    raw  = f.read()
    if mime.startswith("image/") or name.lower().endswith((".png",".jpg",".jpeg",".gif",".webp",".bmp")):
        if not mime.startswith("image/"): mime = "image/png"
        return {"type":"image","name":name,"mime":mime,"base64":base64.b64encode(raw).decode()}
    if mime=="application/pdf" or name.lower().endswith(".pdf"):
        return {"type":"text","name":name,"content":_pdf_text(raw)}
    try:    text = raw.decode("utf-8", errors="replace")
    except: text = str(raw[:3000])
    return {"type":"text","name":name,"content":text[:4000]}


def _pdf_text(raw):
    try:
        import pdfplumber, io
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)[:4000]
    except Exception: pass
    try:
        import pypdf, io
        r = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join(p.extract_text() or "" for p in r.pages)[:4000]
    except Exception:
        return "[PDF could not be extracted — please describe the issue in text]"


# ═══════════════════════════════════════════════════════════
# SALESFORCE KNOWLEDGE SYNC
# ═══════════════════════════════════════════════════════════
def sync_sf_knowledge() -> tuple[bool, str]:
    try:
        sf = _sf_client()

        # No upfront DELETE — upsert_sf_case() uses ON CONFLICT DO UPDATE and
        # delete_removed_cases() removes stale entries at the end.
        # Deleting first would push an empty DB to GitHub before inserts complete.

        # Try progressively simpler queries until one succeeds.
        # Using a CaseComments subquery fetches all comments in one API call
        # instead of one per case, which avoids rate limits and permission gaps.
        # Extra structured fields (Type, Reason, Priority, etc.) are included so
        # cases with no Description/Comments still have searchable content.
        cases            = None
        use_cc_subquery  = False
        _EXTRA = "Type, Reason, Origin, Priority, Product__c, SLAViolation__c, EngineeringReqNumber__c, PotentialLiability__c"
        _QUERIES = [
            (True,  f"SELECT Id, CaseNumber, Subject, Description, Status, Resolution__c, Comments, {_EXTRA}, "
                    "(SELECT CommentBody, CreatedDate FROM CaseComments ORDER BY CreatedDate ASC) "
                    "FROM Case ORDER BY LastModifiedDate DESC LIMIT 1000"),
            (True,  f"SELECT Id, CaseNumber, Subject, Description, Status, {_EXTRA}, "
                    "(SELECT CommentBody, CreatedDate FROM CaseComments ORDER BY CreatedDate ASC) "
                    "FROM Case ORDER BY LastModifiedDate DESC LIMIT 1000"),
            (True,  "SELECT Id, CaseNumber, Subject, Description, Status, Type, Reason, Origin, Priority, "
                    "(SELECT CommentBody, CreatedDate FROM CaseComments ORDER BY CreatedDate ASC) "
                    "FROM Case ORDER BY LastModifiedDate DESC LIMIT 1000"),
            (False, "SELECT Id, CaseNumber, Subject, Description, Status, Type, Reason, Origin, Priority "
                    "FROM Case ORDER BY LastModifiedDate DESC LIMIT 1000"),
            (False, "SELECT Id, CaseNumber, Subject, Description, Status "
                    "FROM Case ORDER BY LastModifiedDate DESC LIMIT 1000"),
        ]
        for _has_sub, _q in _QUERIES:
            try:
                _r = sf.query_all(_q)
                cases           = _r.get("records", [])
                use_cc_subquery = _has_sub
                break
            except Exception:
                continue

        if cases is None:
            return False, "❌ Sync failed: All Salesforce queries failed. Check API credentials and field permissions."

        if not cases:
            return False, "No cases found in Salesforce."

        synced        = 0
        empty_content = 0
        errors        = []
        active_ids    = []

        for case in cases:
            cid         = case["Id"]
            case_number = case.get("CaseNumber", "")
            subject     = case.get("Subject",     "") or ""
            description = case.get("Description", "") or ""
            status      = case.get("Status",      "") or ""
            resolution  = (case.get("Resolution__c") or case.get("Comments") or "")

            # Build structured metadata from available fields as fallback content
            _meta_parts = []
            for _label, _key in [
                ("Type",            "Type"),
                ("Reason",          "Reason"),
                ("Priority",        "Priority"),
                ("Origin",          "Origin"),
                ("Product",         "Product__c"),
                ("SLA Violation",   "SLAViolation__c"),
                ("Engineering Req", "EngineeringReqNumber__c"),
                ("Liability",       "PotentialLiability__c"),
            ]:
                _v = case.get(_key)
                if _v and str(_v).strip():
                    _meta_parts.append(f"{_label}: {_v}")
            structured_meta = " | ".join(_meta_parts) if _meta_parts else ""

            # Use structured metadata as description when no text description exists
            if not description and structured_meta:
                description = structured_meta

            active_ids.append(cid)
            comments_list = []

            # ── CaseComment: subquery (bulk, one API call) or per-case fallback ──
            if use_cc_subquery:
                cc = case.get("CaseComments")
                if cc and isinstance(cc, dict):
                    for c in cc.get("records", []):
                        body = (c.get("CommentBody") or "").strip()
                        if body:
                            comments_list.append(body)
            else:
                try:
                    res = sf.query_all(
                        f"SELECT CommentBody, CreatedDate "
                        f"FROM CaseComment WHERE ParentId='{cid}' ORDER BY CreatedDate ASC"
                    )
                    for c in res.get("records", []):
                        body = (c.get("CommentBody") or "").strip()
                        if body:
                            comments_list.append(body)
                except Exception as e:
                    errors.append(f"CaseComment [{case_number}]: {e}")

            # ── Chatter FeedItem + FeedComments ──────────────
            # Comments entered via the Salesforce case feed are stored as
            # FeedComment records on the case's FeedItem (usually a
            # CreateRecordEvent), not as standalone TextPost FeedItems.
            try:
                res = sf.query_all(
                    f"SELECT Body, "
                    f"(SELECT CommentBody, CreatedDate FROM FeedComments ORDER BY CreatedDate ASC) "
                    f"FROM FeedItem WHERE ParentId='{cid}' ORDER BY CreatedDate ASC LIMIT 30"
                )
                for fi in res.get("records", []):
                    # Direct FeedItem body (TextPost type)
                    body = _strip_html(fi.get("Body") or "").strip()
                    if body:
                        comments_list.append(body)
                    # FeedComments (replies on the feed item — the main comment path)
                    fc_result = fi.get("FeedComments")
                    if fc_result and isinstance(fc_result, dict):
                        for fc in fc_result.get("records", []):
                            fc_body = _strip_html(fc.get("CommentBody") or "").strip()
                            if fc_body:
                                comments_list.append(fc_body)
            except Exception as e:
                errors.append(f"FeedItem [{case_number}]: {e}")

            # ── EmailMessage ─────────────────────────────────
            try:
                res = sf.query_all(
                    f"SELECT TextBody FROM EmailMessage "
                    f"WHERE ParentId='{cid}' ORDER BY MessageDate ASC LIMIT 20"
                )
                for em in res.get("records", []):
                    body = (em.get("TextBody") or "").strip()
                    if body:
                        comments_list.append(body)
            except Exception as e:
                errors.append(f"EmailMessage [{case_number}]: {e}")

            comments_text = "\n\n".join(comments_list)

            support_db.upsert_sf_case(
                sf_case_id=cid, case_number=case_number, subject=subject,
                description=description, status=status,
                resolution=str(resolution), comments=comments_text,
            )
            if not (comments_text or description or resolution):
                empty_content += 1
            synced += 1

        deleted = support_db.delete_removed_cases(active_ids)
        support_db.update_sync_log(synced)

        msg = f"✅ Synced {synced} cases from Salesforce."
        if empty_content:
            msg += f"\n⚠️ {empty_content} case(s) have no description or comments in Salesforce — the resolution steps need to be added directly to those Salesforce cases."
        if deleted:
            msg += f"\n🗑 Removed {deleted} deleted case(s)."
        if errors:
            unique_types = list(dict.fromkeys(e.split(" [")[0] for e in errors))
            msg += f"\n❌ Could not fetch {', '.join(unique_types[:3])} data. Ask your SF admin to grant API Read access to these objects."
        return True, msg

    except Exception as exc:
        return False, f"❌ Sync failed: {exc}"


# ═══════════════════════════════════════════════════════════
# AI HELPERS
# ═══════════════════════════════════════════════════════════
# OpenAI models — fallback when Claude is unavailable
_OPENAI_MODEL      = "gpt-4o"
_OPENAI_FAST_MODEL = "gpt-4o-mini"   # cheap, fast — used for greetings / clarifying Qs

# Claude models — primary AI engine (OpenAI is fallback)
_CLAUDE_MODEL      = "claude-sonnet-4-6"
_CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"


@st.cache_data(ttl=45, show_spinner=False)
def _cached_case_subjects():
    """Case subjects list — cached 45 s so repeated chat turns skip the DB query."""
    return support_db.get_all_case_subjects()


@st.cache_data(ttl=45, show_spinner=False)
def _cached_case_pool():
    """Case pool with snippets — cached 45 s."""
    return support_db.get_case_pool(limit=150)


@st.cache_data(ttl=90, show_spinner=False)
def _cached_gh_info():
    """GitHub remote DB info — cached 90 s to avoid 2 HTTP calls on every render."""
    try:
        import github_sync as _gs
        return _gs.remote_info() if _gs.is_configured() else {}
    except Exception:
        return {}

_EXPERT_PERSONA = (
    "You are a sharp, friendly Worksoft support expert at Qualesce — think of yourself as a senior colleague "
    "sitting right next to the user, helping them fix a problem fast. "
    "Match the tone of ChatGPT or Gemini: warm, direct, and genuinely helpful. "
    "Use contractions naturally (I've, you'll, let's, that's). Acknowledge what the user said before diving in. "
    "Vary your openers — don't always start with 'Got it!' or 'Sure!'. "
    "Be concise: no filler, no padding, no 'Great question!'. "
    "When you give steps, make them feel like you're walking them through it, not reading from a manual. "
    "If a step might be confusing, add a quick 'why' so they understand what it's doing. "
    "Never sound robotic, stiff, or scripted. "
    "You have deep expertise in Worksoft CTM, Certify, Portal, Capture, agent machines, IIS, and appsettings. "
    "When case data is available use it precisely. When it's not, troubleshoot confidently from your own knowledge."
)

_WORKSOFT_DOMAIN = """
=== WORKSOFT PRODUCT KNOWLEDGE ===

WORKSOFT CTM (Continuous Testing Manager)
- Orchestrates test execution across agent machines via a web-based dashboard
- Test suites, jobs, and schedules are dispatched to Windows agent VMs
- Key config: appsettings.config (CTM URL, timeouts, DB connection string)
- Key paths: C:\\inetpub\\wwwroot\\CTM\\, IIS Application Pool "CTMAppPool"
- Common issues & fixes:
    • Agent offline / disconnected → restart "Worksoft CTM Agent" Windows service on the agent machine; verify CTM_URL in agent config matches the CTM server URL
    • Suite stuck in "Abort Pending" → use CTM Force Abort; if unresponsive, restart agent service + iisreset on CTM server
    • Execution timeout → increase ExecutionTimeout in appsettings.config
    • CTM UI not loading → iisreset; check IIS app pool is Started; check event viewer for 500 errors
    • Jobs not dispatching → verify agent machine heartbeat in CTM > Agents tab; check firewall rules on port 8080/443

WORKSOFT CERTIFY
- Windows desktop automation tool; records and plays back UI interactions
- Common issues & fixes:
    • Object not found / recognition failure → update object snapshot (right-click > Update); add a Sync or Wait step before the action
    • Playback too fast → add Delay or Sync steps; lower playback speed in settings
    • License checkout failure → check license server connectivity; release checked-out licenses from admin console
    • Variable / data table errors → verify variable binding in test, check CSV/Excel data file path
    • .NET errors on launch → run as Administrator; repair Certify install; clear %APPDATA%\\Worksoft

WORKSOFT PORTAL
- Web portal for test assets, user management, and reporting (IIS-hosted)
- Common issues & fixes:
    • Login / SSO failure → check AD group membership; verify SSO config in Portal web.config; clear browser cookies
    • 403 / 401 errors → check IIS authentication settings; verify user has correct Portal role
    • Slow load / timeout → recycle IIS app pool; check SQL Server connection; review IIS logs at C:\\inetpub\\logs
    • Page not loading after update → iisreset; clear browser cache; check Portal app pool identity

WORKSOFT CAPTURE
- Browser extension + server for recording business process documentation
- Common issues: plugin not loading → reinstall browser extension; check Capture server URL in plugin settings

AGENT MACHINES (Windows VMs running Certify playback)
- Service name: "Worksoft CTM Agent" (in services.msc)
- Config file: CTMAgent.exe.config (CTM server URL, heartbeat interval)
- Fix pattern: Stop service → verify config → Start service → confirm green heartbeat in CTM dashboard
- Firewall: agent must reach CTM server on configured port (default 443 or 8080)

UNIVERSAL WORKSOFT FIX TOOLKIT
1. iisreset (run as admin) — recycles all IIS app pools; fixes most web/portal issues
2. Restart Worksoft Windows services — open services.msc, restart anything prefixed "Worksoft"
3. Check appsettings.config — wrong URLs, connection strings, or timeouts cause ~40% of issues
4. Windows Event Viewer → Application/System logs — reveals the real error behind a vague UI message
5. IIS logs at C:\\inetpub\\logs\\LogFiles\\ — shows exact HTTP errors for web components
6. SQL Server connectivity — test with SSMS if DB-related errors; check connection string in config
7. Run as Administrator — many Worksoft components require elevated privileges
=== END WORKSOFT KNOWLEDGE ===
"""

_GREET_WORDS = {"hi","hello","hey","hii","helo","heya","howdy","greetings",
                "morning","afternoon","evening","sup","yo","namaste","hai","hola"}
_GREETINGS   = _GREET_WORDS | {
    "good morning","good afternoon","good evening","good day",
    "what's up","whats up","hi there","hey there","hello there",
    "hi all","hello all",
}


@st.cache_resource(show_spinner=False)
def _anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _ask_claude(system_prompt: str, user_prompt: str, max_tokens: int = 800,
                history: list = None, fast: bool = False, stream: bool = False) -> str:
    """
    Primary AI engine using Claude.
    stream=True  → streams response word-by-word to the slot in st.session_state['_stream_slot'].
                   Also auto-hides the typing indicator (st.session_state['_typing_slot']) on
                   first chunk so the transition feels seamless.
    fast=True    → uses Haiku (greeting, clarifying Q, wrap-up).
    fast=False   → uses Sonnet (answer generation, retrieval ranking).
    """
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        import anthropic
        client = _anthropic_client()
        messages = []
        if history:
            for msg in history[-8:]:
                role    = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:600]})
        messages.append({"role": "user", "content": user_prompt})
        model = _CLAUDE_FAST_MODEL if fast else _CLAUDE_MODEL

        stream_slot = st.session_state.get("_stream_slot") if (stream and not fast) else None

        if stream_slot is not None:
            full = ""
            try:
                with client.messages.stream(
                    model=model,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=max_tokens,
                ) as s:
                    for text in s.text_stream:
                        if not full:
                            # First chunk: hide typing indicator for smooth handoff
                            typing = st.session_state.pop("_typing_slot", None)
                            if typing:
                                typing.empty()
                        full += text
                        stream_slot.markdown(full + " ▌")
                if full:
                    stream_slot.markdown(full)   # remove blinking cursor
            except Exception:
                if not full:
                    return ""
            return full

        r = client.messages.create(
            model=model,
            system=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.45,
        )
        return (r.content[0].text or "") if r.content else ""
    except Exception:
        return ""


def _ask_ai(system_prompt: str, user_prompt: str, max_tokens: int = 800,
            history: list = None, fast: bool = False, stream: bool = False) -> str:
    """Claude primary → OpenAI (ChatGPT) fallback."""
    result = _ask_claude(system_prompt, user_prompt, max_tokens, history, fast, stream)
    if result:
        return result
    # OpenAI fallback — no streaming (already fell through from Claude)
    return _ask_openai(system_prompt, user_prompt, max_tokens, history, fast)


@st.cache_resource(show_spinner=False)
def _openai_client():
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


def _ask_openai(system_prompt: str, user_prompt: str, max_tokens: int = 800,
                history: list = None, fast: bool = False) -> str:
    """
    OpenAI fallback — used only when Claude is unavailable.
    fast=True  → gpt-4o-mini  (cheap, fast — greetings / clarifying Qs)
    fast=False → gpt-4o       (full-quality answers)
    """
    if not OPENAI_API_KEY:
        return ""
    try:
        client  = _openai_client()
        model   = _OPENAI_FAST_MODEL if fast else _OPENAI_MODEL
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history[-8:]:
                role    = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:600]})
        messages.append({"role": "user", "content": user_prompt})
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.45,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _describe_image_claude(file_data: dict, user_text: str) -> str:
    """Describe an uploaded screenshot using Claude Vision."""
    if not ANTHROPIC_API_KEY:
        return user_text
    try:
        import anthropic
        client = _anthropic_client()
        r = client.messages.create(
            model=_CLAUDE_FAST_MODEL,
            messages=[{"role": "user", "content": [
                {
                    "type": "image",
                    "source": {
                        "type":       "base64",
                        "media_type": file_data["mime"],
                        "data":       file_data["base64"],
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Describe the error or issue visible in this screenshot in 2 short sentences. "
                        "Be specific about error messages, codes, and UI state. "
                        "Only describe what you can see."
                    ),
                },
            ]}],
            max_tokens=150,
        )
        desc = (r.content[0].text or "").strip() if r.content else ""
        return f"{user_text} {desc}".strip() if desc else user_text
    except Exception:
        return user_text


def _describe_image(file_data: dict, user_text: str) -> str:
    """Try Claude Vision first; fall back to OpenAI Vision (gpt-4o-mini)."""
    result = _describe_image_claude(file_data, user_text)
    if result != user_text:
        return result
    # OpenAI Vision fallback
    if not OPENAI_API_KEY:
        return user_text
    try:
        client = _openai_client()
        r = client.chat.completions.create(
            model=_OPENAI_FAST_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text",
                 "text": "Describe the error or issue in this screenshot in 2 short sentences. Only describe what you see."},
                {"type": "image_url",
                 "image_url": {"url": f"data:{file_data['mime']};base64,{file_data['base64']}"}},
            ]}],
            max_tokens=120,
        )
        desc = (r.choices[0].message.content or "").strip()
        return f"{user_text} {desc}".strip() if desc else user_text
    except Exception:
        return user_text


def _build_sf_context(matches: list) -> dict:
    context_lines = []
    resolution_blocks = []
    for i, case in enumerate(matches, 1):
        subject    = (case.get("subject")     or "").strip()
        status     = (case.get("status")      or "").strip()
        case_num   = (case.get("case_number") or "").strip()
        comments   = (case.get("comments")    or "").strip()
        desc       = (case.get("description") or "").strip()
        resolution = (case.get("resolution")  or "").strip()
        header = f"--- Case {i}"
        if case_num: header += f" (#{case_num})"
        if subject:  header += f": {subject}"
        if status:   header += f" [{status}]"
        context_lines.append(header)
        content = comments or desc or resolution
        if content:
            resolution_blocks.append(f"=== Case {i} – {subject} ===\n{content[:2500]}")
    return {
        "context_block": "\n".join(context_lines),
        "resolution":    "\n\n".join(resolution_blocks),
    }


def _is_greeting(text: str) -> bool:
    clean = re.sub(r"[^a-z\s']", "", text.lower()).strip()
    first_word = clean.split()[0] if clean.split() else ""
    return (
        clean in _GREETINGS
        or all(w in _GREET_WORDS for w in clean.split() if w)
        or (first_word in _GREET_WORDS and len(clean.split()) <= 4
            and not any(c.isdigit() for c in clean))
    )


def _reset_chat_state():
    st.session_state.sf_resolution          = ""
    st.session_state.sf_case_context        = ""
    st.session_state.sf_steps               = []
    st.session_state.sf_step_idx            = 0
    st.session_state.sf_diagnosis           = ""
    st.session_state.chat_phase             = "idle"
    st.session_state.initial_issue          = ""
    st.session_state.resolution_check_shown = False
    st.session_state.show_resolution_popup  = False


def _parse_steps(text: str) -> tuple:
    """
    Extract (diagnosis_line, [step1_text, step2_text, ...]) from an AI response.
    Expects numbered steps like '1. **Action** — reason'.
    """
    step_re = re.compile(r"(?m)^\s*(\d+)\.\s+(.+)$")
    steps   = [m.group(2).strip() for m in step_re.finditer(text)]

    # Diagnosis = first non-blank line that doesn't start with a digit
    diagnosis = ""
    for line in text.split("\n"):
        line = line.strip()
        if line and not re.match(r"^\d+\.", line):
            diagnosis = line
            break

    return diagnosis, steps


def _format_case_content(content: str) -> str:
    """Format raw Salesforce case text as readable markdown — exact content, no AI."""
    content = content.strip()
    if not content:
        return content

    # Already numbered steps (1. / 1) ) — preserve numbering, clean whitespace
    if re.search(r'(?m)^\s*\d+[\.\)]\s', content):
        parts = re.split(r'(?m)(?=^\s*\d+[\.\)]\s)', content)
        return "\n\n".join(p.strip() for p in parts if p.strip())

    # Multiple paragraphs — bullet each paragraph
    paras = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    if len(paras) > 1:
        return "\n\n".join(f"- {p}" for p in paras)

    # Multiple lines — bullet each line
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if len(lines) > 1:
        return "\n".join(f"- {l}" for l in lines)

    return content


# ── Jinja chat renderer ────────────────────────────────────────
from jinja2 import Template as _JTmpl

_CHAT_CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0;}
html,body{background:#f8faff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
.msgs{
  height:420px;overflow-y:auto;overflow-x:hidden;
  padding:16px 14px 8px;
  scrollbar-width:thin;scrollbar-color:#c7d2fe #f8faff;
  background:#f8faff;
}
.msgs::-webkit-scrollbar{width:3px;}
.msgs::-webkit-scrollbar-thumb{background:#c7d2fe;border-radius:3px;}
.msgs::-webkit-scrollbar-track{background:transparent;}
.row{display:flex;align-items:flex-end;gap:8px;margin-bottom:12px;}
.row.u{flex-direction:row-reverse;}
.av{width:30px;height:30px;border-radius:50%;flex-shrink:0;
    display:flex;align-items:center;justify-content:center;font-size:14px;}
.av.a{background:linear-gradient(135deg,#1e40af,#3b82f6);}
.av.u{background:linear-gradient(135deg,#7c3aed,#a855f7);}
@keyframes avIn{from{opacity:0;transform:scale(.5)}to{opacity:1;transform:scale(1)}}
.row.new .av{animation:avIn .25s cubic-bezier(.34,1.56,.64,1) both;}
.bub{max-width:80%;padding:10px 14px;font-size:13px;line-height:1.7;word-break:break-word;}
.bub.a{background:#fff;border:1.5px solid #e0e7ff;color:#1e293b;
       border-radius:4px 16px 16px 16px;box-shadow:0 1px 6px rgba(99,102,241,.08);}
.bub.u{background:linear-gradient(135deg,#1e40af,#2563eb);color:#fff;
       border-radius:16px 4px 16px 16px;box-shadow:0 2px 12px rgba(37,99,235,.28);}
@keyframes botIn{from{opacity:0;transform:translateX(-16px) translateY(6px)}to{opacity:1;transform:none}}
@keyframes usrIn{from{opacity:0;transform:translateX(16px) translateY(6px)}to{opacity:1;transform:none}}
.row.new.a .bub{animation:botIn .35s cubic-bezier(.22,.68,0,1.12) both;}
.row.new.u .bub{animation:usrIn .3s cubic-bezier(.22,.68,0,1.12) both;}
.bub p{margin:0 0 6px;}.bub p:last-child{margin-bottom:0;}
.bub ol,.bub ul{margin:6px 0 6px 18px;}.bub li{margin-bottom:5px;line-height:1.6;}
.bub strong{color:#1d4ed8;}.bub.u strong{color:#bfdbfe;}
.bub code{background:#eff6ff;color:#2563eb;padding:1px 6px;border-radius:4px;font-size:12px;font-family:monospace;}
.bub.u code{background:rgba(255,255,255,.2);color:#e0f2fe;}
.bub hr{border:none;border-top:1px solid #e0e7ff;margin:8px 0;}
.vstep{background:#f1f5ff;border:1px solid #dbeafe;border-radius:10px;padding:9px 12px;margin:5px 0;font-size:12px;}
.vstep-num{display:inline-flex;align-items:center;justify-content:center;
  width:20px;height:20px;border-radius:50%;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  color:#fff;font-size:10px;font-weight:700;margin-right:7px;flex-shrink:0;}
.vstep-row{display:flex;align-items:flex-start;}
.vstep-body{flex:1;}
.vstep-action{font-weight:700;color:#0f172a;margin-bottom:2px;}
.vstep-why{font-size:11px;color:#64748b;margin-bottom:4px;}
.vpath{display:flex;align-items:center;flex-wrap:wrap;gap:3px;
  background:#1e293b;border-radius:6px;padding:6px 10px;margin-top:3px;}
.vpath-seg{color:#94a3b8;font-family:monospace;font-size:11px;}
.vpath-sep{color:#475569;margin:0 1px;}
.vpath-seg.file{color:#7dd3fc;font-weight:600;}
.vcode{background:#1e293b;border-radius:6px;padding:7px 10px;margin-top:4px;
  font-family:monospace;font-size:11px;color:#e2e8f0;white-space:pre-wrap;border-left:3px solid #3b82f6;}
.vcode .ck{color:#7dd3fc;}.vcode .cv{color:#86efac;}
@keyframes db{0%,60%,100%{transform:translateY(0);opacity:.3}30%{transform:translateY(-5px);opacity:1}}
@keyframes tIn{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}
.qtyping-row{display:flex;align-items:flex-end;gap:8px;margin-bottom:10px;animation:tIn .25s ease both;}
.qtyping-av{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}
.qtyping-bubble{background:#fff;border:1.5px solid #e0e7ff;border-radius:4px 16px 16px 16px;
  box-shadow:0 1px 6px rgba(99,102,241,.08);padding:10px 14px;display:flex;gap:4px;align-items:center;}
.qtyping-bubble span{width:6px;height:6px;border-radius:50%;background:#94a3b8;
  display:inline-block;animation:db 1.1s infinite ease-in-out;}
.qtyping-bubble span:nth-child(2){animation-delay:.15s;}
.qtyping-bubble span:nth-child(3){animation-delay:.3s;}
</style>
"""

_CHAT_TMPL = _JTmpl("""
{{ css | safe }}
<div class="msgs" id="msgs">
  <div id="chat">
  {%- for msg in messages %}
  <div class="row {{ 'a' if msg.role == 'assistant' else 'u' }}{% if loop.last %} new{% endif %}">
    <div class="av {{ 'a' if msg.role == 'assistant' else 'u' }}">{{ '🤖' if msg.role == 'assistant' else '👤' }}</div>
    <div class="bub {{ 'a' if msg.role == 'assistant' else 'u' }}">{{ msg.html | safe }}</div>
  </div>
  {%- endfor %}
  </div>
</div>
<script>var m=document.getElementById('msgs');if(m)m.scrollTop=m.scrollHeight;</script>
""")

_TYPING_HTML = """
<style>
@keyframes typingFade{from{opacity:0;transform:translateX(-14px) translateY(6px);}to{opacity:1;transform:none;}}
@keyframes dotBounce{0%,60%,100%{transform:translateY(0);opacity:.35;}30%{transform:translateY(-7px);opacity:1;}}
.qtyping-row{display:flex;align-items:flex-start;gap:10px;padding:4px 0 8px;animation:typingFade .3s ease both;}
.qtyping-av{width:36px;height:36px;border-radius:50%;flex-shrink:0;
            background:linear-gradient(135deg,#2563eb,#0ea5e9);
            display:flex;align-items:center;justify-content:center;font-size:17px;}
.qtyping-bubble{background:#fff;border:1px solid #e2e8f0;
                border-radius:4px 18px 18px 18px;
                box-shadow:0 2px 12px rgba(0,0,0,.07);
                padding:16px 20px;display:flex;gap:6px;align-items:center;}
.qtyping-bubble span{width:8px;height:8px;border-radius:50%;background:#94a3b8;
                     display:inline-block;animation:dotBounce 1.1s infinite ease-in-out;}
.qtyping-bubble span:nth-child(2){animation-delay:.18s;}
.qtyping-bubble span:nth-child(3){animation-delay:.36s;}
</style>
<div class="qtyping-row">
  <div class="qtyping-av">🤖</div>
  <div class="qtyping-bubble"><span></span><span></span><span></span></div>
</div>
"""


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML — no extra dependencies."""
    import html as _h
    text = _h.escape(text)
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Inline code
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)
    # Horizontal rule
    text = re.sub(r'(?m)^---+\s*$', '\x00HR\x00', text)

    lines  = text.split('\n')
    out    = []
    in_ol  = False
    in_ul  = False

    def close_lists():
        nonlocal in_ol, in_ul
        if in_ol:  out.append('</ol>'); in_ol = False
        if in_ul:  out.append('</ul>'); in_ul = False

    for line in lines:
        stripped = line.strip()
        if stripped == '\x00HR\x00':
            close_lists(); out.append('<hr>'); continue
        if not stripped:
            close_lists(); continue
        ol_m = re.match(r'^(\d+)[\.\)]\s+(.*)', stripped)
        ul_m = re.match(r'^[-•]\s+(.*)', stripped)
        if ol_m:
            if in_ul: out.append('</ul>'); in_ul = False
            if not in_ol: out.append('<ol>'); in_ol = True
            out.append(f'<li>{ol_m.group(2)}</li>')
        elif ul_m:
            if in_ol: out.append('</ol>'); in_ol = False
            if not in_ul: out.append('<ul>'); in_ul = True
            out.append(f'<li>{ul_m.group(1)}</li>')
        else:
            close_lists()
            out.append(f'<p>{stripped}</p>')

    close_lists()
    return '\n'.join(out)


def _path_to_html(path: str) -> str:
    """Render a file path as a dark terminal-style breadcrumb visual."""
    import html as _h
    parts = re.split(r'[\\/]+', path.strip().strip('\\/'))
    segs  = []
    for i, p in enumerate(parts):
        if not p:
            continue
        cls = "file" if (i == len(parts) - 1 and '.' in p) else ""
        segs.append(f'<span class="vpath-seg {cls}">{_h.escape(p)}</span>')
        if i < len(parts) - 1:
            segs.append('<span class="vpath-sep">›</span>')
    return f'<div class="vpath">📁 {"".join(segs)}</div>'


def _config_to_html(lines: list[str]) -> str:
    """Render key=value or XML config lines as a highlighted code block."""
    import html as _h
    out = []
    for line in lines:
        # XML attribute style: key="value" or key='value'
        m = re.match(r'\s*<add\s+key=["\']([^"\']+)["\']\s+value=["\']([^"\']*)["\']', line)
        if m:
            out.append(
                f'  &lt;add key=<span class="ck">"{_h.escape(m.group(1))}"</span> '
                f'value=<span class="cv">"{_h.escape(m.group(2))}"</span> /&gt;'
            )
            continue
        # plain key=value or key: value
        m2 = re.match(r'\s*([^=:]+)[=:]\s*(.+)', line)
        if m2:
            out.append(
                f'<span class="ck">{_h.escape(m2.group(1).strip())}</span>'
                f' = <span class="cv">{_h.escape(m2.group(2).strip())}</span>'
            )
            continue
        out.append(_h.escape(line))
    return f'<div class="vcode">{"<br>".join(out)}</div>'


def _enrich_step_html(step_text: str) -> str:
    """
    Given one step's text (already HTML-escaped by _md_to_html),
    detect file paths and config snippets and render them as visual cards.
    """
    import html as _h

    # Find Windows file paths  e.g.  C:\Program Files (x86)\Worksoft\...
    path_pattern = re.compile(
        r'([A-Za-z]:\\(?:[^\s<>"\']+\\)*[^\s<>"\'.]*(?:\.[a-zA-Z0-9]+)?)',
    )
    # Find config lines (XML add-key or key=value blocks in backtick or plain)
    config_pattern = re.compile(
        r'`([^`]{5,})`|(&lt;add\s+key=["\'][^&]+)',
    )

    extras = []

    # Extract all paths and replace inline with just filename highlighted
    paths_found = []
    def _replace_path(m):
        raw = m.group(1)
        paths_found.append(raw)
        fname = raw.split('\\')[-1]
        return f'<code>{_h.escape(fname)}</code>'

    enriched = path_pattern.sub(_replace_path, step_text)

    for p in paths_found:
        extras.append(_path_to_html(p))

    # Extract config key-value pairs from backtick code spans already in HTML
    cfg_lines = []
    for m in config_pattern.finditer(step_text):
        raw = _h.unescape(m.group(0)).strip('`')
        cfg_lines.append(raw)
    if cfg_lines:
        extras.append(_config_to_html(cfg_lines))
        # Remove the backtick spans from enriched text (already captured above)
        enriched = re.sub(r'<code>[^<]{3,}</code>', '', enriched)

    return enriched + ''.join(extras)


def _assistant_to_html(text: str) -> str:
    """
    Full pipeline for assistant messages:
    1. Parse numbered steps
    2. Render each step as a visual card with path/config visuals
    3. Render non-step text normally via _md_to_html
    """
    import html as _h

    lines      = text.split('\n')
    out        = []
    in_steps   = False
    step_buf   = []

    def _flush_steps():
        nonlocal in_steps
        if not step_buf:
            return
        for num, body in step_buf:
            # Split action from reason (after em-dash or '—')
            parts  = re.split(r'\s*[—–-]{1,2}\s*', body, maxsplit=1)
            action = _md_to_html(parts[0].strip())
            why    = _md_to_html(parts[1].strip()) if len(parts) > 1 else ""
            enriched_action = _enrich_step_html(action)
            enriched_why    = _enrich_step_html(why) if why else ""
            out.append(
                f'<div class="vstep">'
                f'<div class="vstep-row">'
                f'<span class="vstep-num">{num}</span>'
                f'<div class="vstep-body">'
                f'<div class="vstep-action">{enriched_action}</div>'
                + (f'<div class="vstep-why">{enriched_why}</div>' if enriched_why else '')
                + '</div></div></div>'
            )
        step_buf.clear()
        in_steps = False

    for line in lines:
        ol_m = re.match(r'^(\d+)[\.\)]\s+(.*)', line.strip())
        if ol_m:
            in_steps = True
            step_buf.append((ol_m.group(1), ol_m.group(2)))
        else:
            if in_steps:
                _flush_steps()
            if line.strip():
                out.append(_md_to_html(line))

    _flush_steps()
    return '\n'.join(out)


def _render_messages_html(messages: list) -> str:
    import html as _h
    prepared = []
    for msg in messages:
        content = msg.get("content", "")
        if msg["role"] == "assistant":
            html_body = _assistant_to_html(content)
        else:
            html_body = f'<p>{_h.escape(content)}</p>'
        prepared.append({"role": msg["role"], "html": html_body})
    return _CHAT_TMPL.render(css=_CHAT_CSS, messages=prepared)


def _split_case_content(content: str) -> list:
    """Split raw case content into individual steps by numbered list, paragraph, or line."""
    parts = re.split(r'(?m)(?=^\s*\d+[\.\)]\s)', content)
    steps = [p.strip() for p in parts if p.strip()]
    if len(steps) > 1:
        return steps
    parts = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
    if len(parts) > 1:
        return parts
    parts = [p.strip() for p in content.splitlines() if p.strip()]
    if len(parts) > 1:
        return parts
    return [content.strip()]


def _retrieve_best_cases(query: str, top_n: int = 1) -> list:
    """
    Two-stage retrieval:
    Stage 1 — ALL case subjects sent to AI → up to 12 candidates (semantic) + keyword hits merged.
    Stage 2 — Full content of candidates sent to AI → best 1-2 chosen by actual content.
    """
    all_subs = _cached_case_subjects()
    if not all_subs:
        return []

    # Include a short content snippet so the AI can match on content, not just subject
    sub_lines = []
    for i, c in enumerate(all_subs[:300]):
        subj    = (c.get("subject",  "") or "").strip()
        snippet = (c.get("snippet",  "") or "").strip()[:150]
        cnum    = (c.get("case_number", "") or "").strip()
        if not subj:
            continue
        line = f"{i+1}. [{cnum}] {subj}"
        if snippet:
            line += f" | {snippet}"
        sub_lines.append(line)

    s1_resp = _ask_ai(
        system_prompt=(
            "You are a Worksoft support case matcher. A user has a problem. "
            "Each entry below shows: index. [CaseNum] Subject | content snippet.\n"
            "Your job: pick every case whose subject OR content MIGHT be related to the user's question. "
            "Be INCLUSIVE — it is far better to include too many than to miss the right one. "
            "Think broadly and semantically:\n"
            "  'CTM session timeout' → 'MouseMove', 'session keep-alive', 'CTM timeout', 'appsettings'\n"
            "  'suite stuck abort pending' → 'Abort Pending', 'Force Abort', 'execution stuck'\n"
            "  'login fails' → 'authentication', 'credentials', 'SSO', 'access denied'\n"
            "Return ONLY position numbers of up to 20 candidates, e.g. '3, 7, 12, 45'. "
            "If absolutely nothing is even loosely related, return: NONE"
        ),
        user_prompt=f"User question: {query}\n\nCases:\n" + "\n".join(sub_lines),
        max_tokens=80,
        stream=False,
    )

    candidate_ids: list = []
    if s1_resp and re.sub(r"[^a-zA-Z]", "", s1_resp).upper() != "NONE":
        for token in re.findall(r"\d+", s1_resp):
            idx = int(token) - 1
            if 0 <= idx < len(all_subs):
                cid = all_subs[idx]["sf_case_id"]
                if cid not in candidate_ids:
                    candidate_ids.append(cid)

    # Merge keyword-search hits (returns up to 5, improved SQL LIKE matching)
    kw_hits = support_db.search_knowledge(query, top_n=8)
    for m in kw_hits:
        cid = m["sf_case_id"]
        if cid not in candidate_ids:
            candidate_ids.append(cid)

    if not candidate_ids:
        return []

    candidates = support_db.get_cases_by_ids(candidate_ids[:20])
    if not candidates:
        return []
    if len(candidates) == 1:
        return candidates

    content_blocks = []
    for i, c in enumerate(candidates):
        case_num = (c.get("case_number", "") or "").strip()
        subject  = (c.get("subject",     "") or "").strip()
        comments = (c.get("comments",    "") or "").strip()[:2500]
        desc     = (c.get("description", "") or "").strip()[:800]
        body     = comments or desc or "(no content)"
        content_blocks.append(f"[{i+1}] Case #{case_num} — {subject}\n{body}")

    s2_resp = _ask_ai(
        system_prompt=(
            "You are a Worksoft support specialist. "
            "Read each case's ACTUAL CONTENT carefully — not just the subject. "
            "Pick the 1-3 cases whose content genuinely answers the user's question. "
            "Prefer cases that have detailed resolution steps or comments. "
            "Return ONLY position numbers, e.g. '2' or '1, 3'. "
            "If no case content actually addresses the user's issue, return: NONE"
        ),
        user_prompt=(
            f"User question: {query}\n\n"
            "Cases (judge by content, not subject alone):\n\n"
            + "\n\n---\n\n".join(content_blocks)
        ),
        max_tokens=30,
        stream=False,
    )

    if s2_resp and re.sub(r"[^a-zA-Z]", "", s2_resp).upper() != "NONE":
        final_ids: list = []
        for token in re.findall(r"\d+", s2_resp):
            idx = int(token) - 1
            if 0 <= idx < len(candidates):
                cid = candidates[idx]["sf_case_id"]
                if cid not in final_ids:
                    final_ids.append(cid)
        if final_ids:
            return [c for c in candidates if c["sf_case_id"] in final_ids][:top_n]

    with_content = [
        c for c in candidates
        if (c.get("comments") or c.get("description") or "").strip()
    ]
    return (with_content or candidates)[:top_n]


# ═══════════════════════════════════════════════════════════
# CHAT ENGINE  (conversational, step-by-step)
# ═══════════════════════════════════════════════════════════
def process_chat(text: str, history: list, file_data: dict = None) -> str:
    if file_data and file_data["type"] == "image":
        query = _describe_image(file_data, text)
    elif file_data and file_data["type"] == "text":
        query = f"{text} {file_data['content'][:500]}"
    else:
        query = text

    phase = st.session_state.get("chat_phase", "idle")

    # ── GREETING ──────────────────────────────────────────────
    if _is_greeting(text) and not file_data and phase == "idle":
        return _ask_ai(
            system_prompt=(
                f"{_EXPERT_PERSONA} The user just greeted you. "
                "Say hi warmly, mention you're their Worksoft support assistant powered by Salesforce knowledge, "
                "and ask what they're running into. One or two sentences max."
            ),
            user_prompt=f"User said: '{text}'",
            history=history,
            max_tokens=100,
            fast=True,
        ) or "Hey! I'm your Worksoft support assistant. What's going on today?"

    # ── RESOLVING PHASE — fully AI-driven ────────────────────
    if phase == "resolving":
        sf_steps = st.session_state.get("sf_steps", [])
        step_idx = st.session_state.get("sf_step_idx", 0)
        total    = len(sf_steps)
        sf_res   = st.session_state.get("sf_resolution", "")
        case_ctx = st.session_state.get("sf_case_context", "")

        # Build step state for the AI to reason about
        if sf_steps:
            given_lines   = "\n".join(
                f"  ✓ Step {i+1}: {sf_steps[i]}" for i in range(step_idx + 1)
            )
            pending_lines = "\n".join(
                f"  • Step {i+1}: {sf_steps[i]}" for i in range(step_idx + 1, total)
            ) or "  (none — all steps have been given)"
            step_state = (
                f"STEP PROGRESS ({step_idx + 1} of {total} given):\n"
                f"Steps already given to user:\n{given_lines}\n\n"
                f"Steps NOT yet given (do NOT reveal all at once):\n{pending_lines}\n\n"
                f"Last step given: Step {step_idx + 1} — {sf_steps[step_idx] if step_idx < total else 'all done'}\n"
            )
        else:
            step_state = "No structured step list — answer freely using your knowledge.\n"

        system_prompt = (
            f"{_EXPERT_PERSONA}\n\n"
            f"{_WORKSOFT_DOMAIN}\n\n"
            + (f"Salesforce knowledge base:\n{sf_res[:1800]}\n\n" if sf_res else "")
            + (f"Issue context: {case_ctx}\n\n" if case_ctx else "")
            + step_state
            + """
You are having a live chat support session. The user just replied to you.
Read their message carefully — understand what they actually mean — then decide:

DECISION RULES (think, don't keyword-match):
• Did the user say a step worked, say "done", ask to move on, or confirm they're ready?
  → They want the NEXT step.
• Did the user say something failed, describe an error, ask "why", or need help?
  → They need help with the CURRENT step — answer and stay on it.
• Did the user say the whole issue is fixed, say "thanks / all good / sorted"?
  → The problem is resolved — confirm and close.

RESPONSE FORMAT — your reply MUST start with exactly one of these tokens on its own line:
[NEXT] — you're advancing to the next step
[DONE] — the issue is fully resolved
[HELP] — you're assisting with the current step (question, failure, clarification)

Then a blank line. Then your actual reply to the user.

RULES FOR EACH TOKEN:
[NEXT] → Give ONLY the next pending step. Say "Step X of Y:" before it.
          End with "Let me know when that's done! 👇"
          If this IS the final step, end with "Let me know if that sorted it!"
[DONE] → 1 warm sentence. Tell them to click ✅ Resolved at L1 below.
[HELP] → 2-3 sentences MAX. Answer their specific question or diagnose the failure.
          End with a short question ("What do you see?", "Does that help?").

NEVER give more than one step at a time.
NEVER use keyword lists — actually understand what the user is saying.
Sound like a knowledgeable colleague, not a support script.
"""
        )

        raw = _ask_ai(
            system_prompt=system_prompt,
            user_prompt=text,
            history=history,
            max_tokens=350,
        )

        if not raw:
            return "What exactly are you seeing? Tell me more and I'll help you figure it out."

        # Parse the AI's decision token
        lines   = raw.strip().split("\n")
        token   = lines[0].strip()
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw.strip()

        if token == "[NEXT]":
            new_idx = step_idx + 1
            if new_idx < total:
                st.session_state.sf_step_idx = new_idx
        elif token == "[DONE]":
            st.session_state.show_resolution_popup = True
            _reset_chat_state()
        # [HELP] — no state change, stay on current step

        return content or raw

    # ── INTAKE PHASE — user answered the clarifying question ──
    if phase == "intake":
        original   = st.session_state.get("initial_issue", "")
        full_query = f"{original}. {text}".strip(". ") if original else text
        _reset_chat_state()
        return _resolve(full_query, history)

    # ── IDLE — first message on this issue ────────────────────
    if file_data:
        _reset_chat_state()
        return _resolve(query, history)

    # Store issue, ask ONE clarifying question, then wait for answer
    st.session_state.initial_issue = text
    st.session_state.chat_phase    = "intake"

    return _ask_ai(
        system_prompt=(
            f"{_EXPERT_PERSONA}\n\n"
            "The user just described a Worksoft issue. Ask ONE short, targeted question to narrow it down.\n\n"
            "Choose the most useful question from:\n"
            "- Which module — CTM, Certify, Portal, or Capture?\n"
            "- What's the exact error message or code?\n"
            "- Is this on all machines or just one?\n"
            "- Did anything change recently (update, restart, config change)?\n"
            "- Is this new, or was it working before?\n\n"
            "Rules:\n"
            "- One sentence only. Conversational, not formal.\n"
            "- Vary your opener — don't always say 'Got it!'\n"
            "- Show you understood the issue before asking."
        ),
        user_prompt=f"User's issue: {text}",
        history=history,
        max_tokens=120,
        fast=True,
    ) or "Hmm, a few things could cause this — which Worksoft module are you in: CTM, Certify, or Portal?"


def _build_case_knowledge(matches: list, query: str = "") -> tuple:
    """
    Build a rich knowledge context from ALL matched cases.
    Returns (knowledge_text, has_any_content, summary_for_context).
    """
    blocks = []
    all_subjects = []
    for i, case in enumerate(matches, 1):
        subject    = (case.get("subject")     or "").strip()
        desc       = (case.get("description") or "").strip()
        resolution = (case.get("resolution")  or "").strip()
        comments   = (case.get("comments")    or "").strip()

        if subject:
            all_subjects.append(subject)

        parts = []
        if subject:
            parts.append(f"Issue type: {subject}")
        if desc:
            parts.append(f"Problem description:\n{desc[:800]}")
        if resolution:
            parts.append(f"Resolution summary:\n{resolution[:600]}")
        if comments:
            parts.append(f"Detailed steps/comments:\n{comments[:1800]}")

        if len(parts) > 1:   # must have more than just the subject
            blocks.append(f"── Knowledge Entry {i} ──\n" + "\n\n".join(parts))

    knowledge_text  = "\n\n".join(blocks) if blocks else ""
    has_content     = bool(blocks)
    context_summary = "; ".join(all_subjects[:3]) if all_subjects else query
    return knowledge_text, has_content, context_summary


def _resolve(query: str, history: list) -> str:
    """
    Retrieve Salesforce cases, generate ALL fix steps via AI (non-streaming),
    then serve only Step 1 — the rest are served one-at-a-time as the user
    confirms each step is done.
    """
    matches = _retrieve_best_cases(query, top_n=5)
    knowledge_text, has_content, ctx_summary = (
        _build_case_knowledge(matches, query) if matches else ("", False, query)
    )

    base_system = f"{_EXPERT_PERSONA}\n\n{_WORKSOFT_DOMAIN}\n\n"

    step_format = (
        "OUTPUT FORMAT — follow exactly:\n"
        "Line 1: One plain-English diagnosis sentence (no bold, no bullet).\n"
        "Blank line.\n"
        "Then numbered steps, one per line:\n"
        "1. **[exact action]** — [brief why it fixes the issue]\n"
        "2. **[exact action]** — [brief why]\n"
        "3. **[exact action]** — [brief why]\n"
        "...and so on.\n\n"
        "RULES:\n"
        "- Each step = ONE action only. Never combine two actions.\n"
        "- Include exact service names, file paths, config keys (e.g. services.msc, "
        "C:\\\\Program Files (x86)\\\\Worksoft\\\\CTM Agent Manager\\\\appsettings.config).\n"
        "- No closing sentence. Steps only.\n"
    )

    if has_content:
        system_prompt = (
            base_system
            + "The following Salesforce resolved cases contain the fix for this issue. "
            "Read them all, identify the pattern, and produce structured steps.\n\n"
            + step_format
            + "Source all steps from the knowledge base below. "
            "Fill gaps only with directly relevant Worksoft expertise.\n\n"
            f"=== SALESFORCE KNOWLEDGE BASE ===\n\n{knowledge_text}"
        )
        st.session_state.sf_resolution   = knowledge_text[:3000]
        st.session_state.sf_case_context = ctx_summary
    else:
        system_prompt = (
            base_system
            + "No Salesforce case matched this query exactly. "
            "Use your Worksoft domain expertise to produce structured fix steps.\n\n"
            + step_format
        )
        st.session_state.sf_resolution   = ""
        st.session_state.sf_case_context = query

    st.session_state.chat_phase = "resolving"

    # Generate ALL steps (non-streaming — we'll drip them one at a time)
    full_answer = _ask_ai(
        system_prompt=system_prompt,
        user_prompt=f"User's issue: {query}",
        history=history,
        max_tokens=1200,
    )

    if not full_answer and has_content:
        best = matches[0]
        raw  = (best.get("comments") or best.get("description") or "").strip()
        full_answer = _format_case_content(raw)

    if not full_answer:
        return (
            "I couldn't find a match or generate an answer right now. "
            "Use **🔺 Forward to L2** below to raise a ticket with the team."
        )

    # ── Parse into diagnosis + step list ─────────────────────
    diagnosis, steps = _parse_steps(full_answer)

    if not steps:
        # AI didn't follow the numbered format — return as-is
        st.session_state.sf_steps    = []
        st.session_state.sf_step_idx = 0
        return full_answer

    # Store all steps; we'll serve them one by one
    st.session_state.sf_steps    = steps
    st.session_state.sf_step_idx = 0
    st.session_state.sf_diagnosis = diagnosis
    total = len(steps)

    # ── Serve Step 1 only ─────────────────────────────────────
    intro = f"{diagnosis}\n\n" if diagnosis else ""
    if total == 1:
        return (
            f"{intro}"
            f"Here's what to try:\n\n"
            f"1. {steps[0]}\n\n"
            f"Give that a go and let me know how it goes! 👇"
        )
    else:
        return (
            f"{intro}"
            f"I've got **{total} steps** for this — let's go one at a time so we don't miss anything.\n\n"
            f"**Step 1 of {total}:**\n\n"
            f"1. {steps[0]}\n\n"
            f"Try that and reply when you're done — I'll give you Step 2! 👇"
        )


# ═══════════════════════════════════════════════════════════
# NAVBAR
# ═══════════════════════════════════════════════════════════
def render_navbar():
    st.html("""
<div class="nav">
  <div class="nav-left">
    <div class="nav-logo">🤖</div>
    <div>
      <div class="nav-title">Worksoft AI Support</div>
      <div class="nav-sub">Qualesce · Salesforce Knowledge</div>
    </div>
  </div>
  <div class="nav-right">
    <span class="nav-pill">● Online</span>
  </div>
</div>""")


# ═══════════════════════════════════════════════════════════
# PAGE: CHAT
# ═══════════════════════════════════════════════════════════
def render_sidebar():
    pass   # no Streamlit sidebar — controls are in the left column


def _render_left_panel(col):
    info = support_db.get_sync_info()
    cnt  = info.get("case_count", 0)
    last = info.get("last_sync", "")[:16].replace("T", " ") if info.get("last_sync") else "Never"
    feats = "".join([
        f'<div class="lp-feature"><span style="font-size:14px;">{i}</span>{l}</div>'
        for i, l in [("🔍","Smart AI search"),("📎","File & screenshot"),
                     ("🎫","Auto ticket"),("📧","Admin notify")]
    ])

    with col:
        st.markdown(f"""
<div class="lp">
  <div class="lp-logo">
    <div class="lp-av">🤖</div>
    <div><div class="lp-t">Worksoft AI</div><div class="lp-s">Support · Qualesce</div></div>
  </div>
  <span class="lp-status"><span class="lp-dot"></span>Online &amp; Ready</span>
  <div>
    <div class="lp-sec-title">Knowledge Base</div>
    <div class="lp-stat">
      <div class="lp-num">{cnt}</div>
      <div class="lp-numlbl">Cases · Last sync: {last}</div>
    </div>
  </div>
  <div>
    <div class="lp-sec-title">Capabilities</div>
    {feats}
  </div>
</div>""", unsafe_allow_html=True)

        if st.button("🔄 Sync Salesforce", use_container_width=True, type="primary"):
            with st.spinner("Syncing Salesforce…"):
                ok, msg = sync_sf_knowledge()
            if ok:
                _cached_case_subjects.clear()
                _cached_gh_info.clear()
                if github_sync.is_configured():
                    with st.spinner("Pushing to GitHub…"):
                        gh_ok, gh_msg = github_sync.push_db()
                    msg += f"\n{'☁️ ' + gh_msg if gh_ok else '⚠️ GitHub: ' + gh_msg}"
            st.success(msg) if ok else st.error(msg)
            st.rerun()


def render_chat():
    render_navbar()

    # ── Two-column layout ───────────────────────────────────
    left_col, right_col = st.columns([1, 2.6], gap="large")
    _render_left_panel(left_col)

    with right_col:
        _live_chat()


@st.dialog("Support Level Check 🔔")
def _show_resolution_dialog():
    """Popup shown when AI detects the issue is resolved — asks L1 or L2."""
    st.markdown("""
<div style="text-align:center;padding:6px 0 18px;">
  <div style="font-size:52px;margin-bottom:12px;">🔍</div>
  <div style="font-size:18px;font-weight:800;color:#0f172a;margin-bottom:8px;">
    Can we close this at L1?
  </div>
  <div style="font-size:13px;color:#64748b;line-height:1.7;">
    It looks like your issue may be resolved.<br>
    Confirm below — or keep chatting if you need more help.
  </div>
</div>
""", unsafe_allow_html=True)

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("✅  Resolved at L1", use_container_width=True, type="primary"):
            st.session_state.resolution_check_shown = True
            st.session_state.show_resolution_popup  = False
            st.session_state.page = "resolved"
            st.rerun(scope="app")
    with btn_col2:
        if st.button("🔺  Forward to L2", use_container_width=True):
            st.session_state.resolution_check_shown = True
            st.session_state.show_resolution_popup  = False
            st.session_state.page = "escalated"
            st.rerun(scope="app")

    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    if st.button("💬  Not yet — keep chatting", use_container_width=True):
        # Dismiss popup, let user continue without re-popping unless AI detects resolution again
        st.session_state.resolution_check_shown = False
        st.session_state.show_resolution_popup  = False
        st.rerun()


@st.fragment
def _live_chat():
    """
    Fragment: only the chat panel reruns on each message — sidebar/navbar stay frozen.
    """
    # ── Auto-welcome on very first load ──────────────────────
    if not st.session_state.get("chat_started"):
        st.session_state.chat_started = True
        welcome = (
            "Hi there! I'm your **Worksoft AI Support Assistant** — "
            "my answers are sourced directly from Salesforce resolved cases and our knowledge base.\n\n"
            "I'll walk you through fixes **one step at a time** so nothing gets missed. "
            "Just tell me what's going on — or attach a screenshot, log file, or PDF using the 📎 icon.\n\n"
            "Which Worksoft product are you having trouble with? *(CTM, Certify, Portal, or Capture)*"
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})

    # ── Chat window header ───────────────────────────────────
    st.html(f"""
<div class="cwin">
  <div class="chead">
    <div class="chead-left">
      <div class="chead-av">🤖</div>
      <div>
        <div class="chead-name">Qualesce AI Support</div>
        <div class="chead-sub">CTM · Certify · Portal · Capture</div>
        <span class="chead-status"><span class="chead-dot"></span>Online</span>
      </div>
    </div>
    <div class="chead-rt">
      <div class="chead-rt-lbl">Response</div>
      <div class="chead-rt-val">~2-5 sec</div>
    </div>
  </div>
</div>""")

    # ── Messages (scrollable) ────────────────────────────────
    if st.session_state.messages:
        st.html(_render_messages_html(st.session_state.messages))

    # Inline images from file uploads
    for msg in st.session_state.messages:
        fdata = msg.get("file")
        if fdata and fdata["type"] == "image":
            st.image(
                f"data:{fdata['mime']};base64,{fdata['base64']}",
                caption=fdata["name"], width=260,
            )

    # ── Input bar ────────────────────────────────────────────
    st.markdown('<div class="input-bar">', unsafe_allow_html=True)
    st.markdown('<div class="input-box">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        att_col, txt_col, snd_col = st.columns([1, 9, 1])
        with att_col:
            uploaded = st.file_uploader(
                "attach",
                type=["png","jpg","jpeg","gif","webp","pdf","txt","log","csv","xml"],
                label_visibility="collapsed",
            )
        with txt_col:
            user_input = st.text_area(
                "msg",
                placeholder="Describe your Worksoft issue…",
                height=52,
                label_visibility="collapsed",
            )
        with snd_col:
            send = st.form_submit_button("➤", use_container_width=True, type="primary")
    st.markdown('</div>', unsafe_allow_html=True)  # input-box
    st.markdown('</div>', unsafe_allow_html=True)  # input-bar

    # ── Resolution check popup + action buttons ───────────────
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "assistant" and len(msgs) >= 2:
        already_shown = st.session_state.get("resolution_check_shown", False)

        # Popup only when the AI has determined the issue is resolved
        if st.session_state.get("show_resolution_popup") and not already_shown:
            _show_resolution_dialog()

        # Persistent action buttons always visible after first assistant reply
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 2px;">'
            '<span style="font-size:12px;color:#64748b;font-weight:600;margin-right:4px;">'
            'Support level:</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        rc1, rc2, _ = st.columns([1.5, 1.7, 3])
        with rc1:
            if st.button("✅ Resolved at L1", use_container_width=True, type="primary"):
                st.session_state.resolution_check_shown = True
                st.session_state.page = "resolved"
                st.rerun(scope="app")
        with rc2:
            if st.button("🔺 Forward to L2", use_container_width=True):
                st.session_state.resolution_check_shown = True
                st.session_state.page = "escalated"
                st.rerun(scope="app")

    # ── Handle send ──────────────────────────────────────────
    if send and (user_input.strip() or uploaded):
        file_data = _process_upload(uploaded) if uploaded else None
        user_msg  = {"role": "user", "content": user_input.strip()}
        fname = uploaded.name if uploaded else ""
        ftype = (file_data or {}).get("type", "")
        if file_data:
            user_msg["file"] = file_data
        if not st.session_state.issue_text:
            st.session_state.issue_text = user_input.strip() or f"[Attached: {fname}]"

        # Auto-create session on first message (no login required)
        if not st.session_state.get("session_id"):
            st.session_state.session_id = support_db.create_session("Guest", "")

        st.session_state.messages.append(user_msg)
        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_message(sid, "user", user_input.strip(), fname, ftype)

        _typing_slot = st.empty()
        _typing_slot.html(_TYPING_HTML)
        _stream_slot = st.empty()
        st.session_state["_stream_slot"] = _stream_slot
        st.session_state["_typing_slot"] = _typing_slot

        reply = process_chat(user_input.strip(), st.session_state.messages, file_data)

        # Cleanup streaming state (may already be gone if streaming fired)
        st.session_state.pop("_stream_slot", None)
        st.session_state.pop("_typing_slot", None)
        _typing_slot.empty()
        _stream_slot.empty()

        st.session_state.messages.append({"role": "assistant", "content": reply})
        if sid:
            support_db.save_message(sid, "assistant", reply)
        st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: RESOLVED
# ═══════════════════════════════════════════════════════════
def render_resolved():
    render_navbar()
    st.markdown("""
<div style="max-width:480px;margin:48px auto;text-align:center;
     background:rgba(255,255,255,.88);backdrop-filter:blur(18px);
     border:1.5px solid rgba(22,163,74,.25);border-radius:24px;
     box-shadow:0 12px 40px rgba(22,163,74,.12);
     padding:48px 32px;" class="anim">
  <div style="font-size:56px;margin-bottom:12px;">🎉</div>
  <div style="font-size:22px;font-weight:900;color:#16a34a;margin-bottom:8px;">Issue Resolved!</div>
  <div style="font-size:14px;color:#475569;margin-bottom:24px;">
    Glad that sorted it!<br>
    Come back anytime you need Worksoft support.
  </div>
  <div style="background:#dcfce7;border:1px solid rgba(22,163,74,.25);
       border-radius:12px;padding:12px 20px;font-size:13px;color:#166534;font-weight:600;">
    ✅ No ticket raised
  </div>
</div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        if st.button("Start New Chat", use_container_width=True, type="primary"):
            sid = st.session_state.get("session_id")
            if sid:
                support_db.update_session_status(sid, "resolved")
            st.session_state.messages  = []
            st.session_state.issue_text = ""
            st.session_state.sf_ticket  = None
            st.session_state.session_id = None
            st.session_state.chat_started = False
            _reset_chat_state()
            st.session_state.page = "chat"; st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: ESCALATED
# ═══════════════════════════════════════════════════════════
def render_escalated():
    render_navbar()
    issue_text = st.session_state.issue_text or "Worksoft issue (see conversation)"

    if st.session_state.sf_ticket:
        user = st.session_state.user or {"name": "Guest", "email": ""}
        _render_ticket(user, st.session_state.sf_ticket); return

    st.markdown("""
<div style="max-width:540px;margin:16px auto;text-align:center;
     background:rgba(255,255,255,.88);backdrop-filter:blur(18px);
     border:1.5px solid rgba(30,64,175,.15);border-radius:20px;
     box-shadow:0 8px 28px rgba(30,64,175,.10);
     padding:24px 28px;" class="anim">
  <div style="font-size:28px;margin-bottom:8px;">🔺</div>
  <div style="font-size:17px;font-weight:800;color:#0f172a;margin-bottom:4px;">Forwarding to L2 Support</div>
  <div style="font-size:13px;color:#64748b;">
    A Salesforce case will be raised and the L2 team notified.<br>Add your contact details to receive email updates.
  </div>
</div>""", unsafe_allow_html=True)

    with st.form("esc_form"):
        c1, c2 = st.columns(2)
        with c1:
            esc_name  = st.text_input("Your Name (optional)", placeholder="e.g. Aravind R")
        with c2:
            esc_email = st.text_input("Your Email (optional)", placeholder="you@qualesce.com")
        extra    = st.text_area("Additional details (optional)",
                                placeholder="Error code, business impact, steps already tried…", height=90)
        priority = st.selectbox("Priority", ["High","Critical","Medium","Low"])
        submit   = st.form_submit_button("🚀 Raise Ticket & Notify IT Admin",
                                         use_container_width=True, type="primary")

    if submit:
        user_name  = esc_name.strip()  or "Guest"
        user_email = esc_email.strip() or ""
        user = {"name": user_name, "email": user_email}
        st.session_state.user = user

        convo = "\n\n".join(
            f"{'User' if m['role']=='user' else 'Agent'}: {m['content']}"
            for m in st.session_state.messages
        )
        desc = (
            f"Reported by: {user_name}" + (f" ({user_email})" if user_email else "") +
            f"\n\nIssue:\n{issue_text}"
            + (f"\n\nAdditional Details:\n{extra}" if extra.strip() else "")
            + f"\n\nAI Chat:\n{convo}"
        )
        subj = f"Worksoft Issue – {issue_text[:80]}{'…' if len(issue_text)>80 else ''}"

        ticket = None; sf_error = ""; email_ok = False; email_err = ""

        with st.spinner("Creating Salesforce case…"):
            try:
                ticket = sf_create_case(subj, desc, user["name"], user["email"], priority)
            except Exception as exc:
                raw = str(exc)
                if "CANNOT_EXECUTE_FLOW_TRIGGER" in raw:
                    sf_error = "A Salesforce Flow is blocking case creation. Ask your SF admin to deactivate 'Worksoft Case Email Notification'."
                elif "INVALID_SESSION_ID" in raw or "Authentication" in raw:
                    sf_error = "Salesforce auth failed. Check credentials in secrets.toml."
                else:
                    sf_error = raw
                import hashlib, time as _t
                ref = "QWS-" + hashlib.md5(f"{user['email']}{_t.time()}".encode()).hexdigest()[:6].upper()
                ticket = {"id": ref, "case_number": ref, "url": "#sf-not-configured"}

        with st.spinner("Sending email notifications…"):
            email_ok, email_err = send_escalation_email(
                ticket, user["name"], user["email"], issue_text, convo)

        ticket.update({"sf_error":sf_error,"email_ok":email_ok,"email_err":email_err,
                       "priority":priority,"created_at":datetime.now().strftime("%d %b %Y, %H:%M")})
        st.session_state.sf_ticket = ticket

        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_ticket(
                session_id=sid, user_name=user["name"], user_email=user["email"],
                issue_text=issue_text, priority=priority,
                sf_case_number=ticket.get("case_number",""),
                sf_case_url=ticket.get("url",""),
                sf_error=sf_error, email_sent=email_ok,
            )
            support_db.update_session_status(sid, "escalated")
        st.rerun()


def _render_ticket(user, ticket):
    case_num = ticket.get("case_number") or ticket.get("id","N/A")
    case_url = ticket.get("url","#")
    priority = ticket.get("priority","High")
    created  = ticket.get("created_at","")
    email_ok = ticket.get("email_ok",False)
    sf_error = ticket.get("sf_error","")

    p_colors = {
        "Critical":("rgba(220,38,38,.2)","#f87171"),
        "High":    ("rgba(220,38,38,.15)","#fca5a5"),
        "Medium":  ("rgba(217,119,6,.15)","#fcd34d"),
        "Low":     ("rgba(22,163,74,.15)","#86efac"),
    }
    pbg, pclr = p_colors.get(priority, ("rgba(220,38,38,.15)","#fca5a5"))

    sf_link = (
        f'<a href="{case_url}" target="_blank" class="ticket-link">🔗 View in Salesforce</a>'
        if case_url != "#sf-not-configured" else ""
    )

    st.markdown(f"""
<div class="ticket-card anim">
  <div class="ticket-id">Salesforce Case</div>
  <div class="ticket-num">#{case_num}</div>
  <div class="ticket-row">
    <span class="ticket-lbl">Raised by</span>
    <span class="ticket-val">{user["name"]}{(" (" + user["email"] + ")") if user.get("email") else ""}</span>
  </div>
  <div class="ticket-row">
    <span class="ticket-lbl">Priority</span>
    <span style="background:{pbg};color:{pclr};font-size:10px;font-weight:700;
          padding:2px 10px;border-radius:99px;">{priority}</span>
  </div>
  <div class="ticket-row">
    <span class="ticket-lbl">Status</span>
    <span class="badge-new">New</span>
  </div>
  <div class="ticket-row">
    <span class="ticket-lbl">Created</span>
    <span class="ticket-val">{created}</span>
  </div>
  <div class="ticket-row">
    <span class="ticket-lbl">IT Admin</span>
    <span class="ticket-val">{IT_ADMIN_EMAIL}</span>
  </div>
  {"" if not sf_error else f'<div style="margin-top:8px;font-size:12px;color:#f87171;">⚠️ {sf_error}</div>'}
  {sf_link}
</div>""", unsafe_allow_html=True)

    if email_ok:
        cc_note = f" · You've been CC'd at {user['email']}" if user.get("email") else ""
        st.success(f"✅ IT Admin notified ({IT_ADMIN_EMAIL}){cc_note}")
    else:
        st.warning(f"Email failed: {ticket.get('email_err','Unknown')}. Ticket exists in Salesforce.")

    st.markdown("""
<div style="text-align:center;padding:16px;font-size:13px;color:#475569;line-height:1.7;">
  Your ticket is with the IT Admin team.<br>
  Check your email for the case confirmation with the Salesforce link.
</div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🆕 New Chat", use_container_width=True, type="primary"):
            st.session_state.messages   = []
            st.session_state.issue_text = ""
            st.session_state.sf_ticket  = None
            st.session_state.session_id = None
            st.session_state.user       = {"name": "Guest", "email": ""}
            st.session_state.chat_started = False
            _reset_chat_state()
            st.session_state.page = "chat"; st.rerun()
    with c2:
        if st.button("💬 Back to Chat", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()


# ═══════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════
def main():
    p = st.session_state.page
    if   p == "resolved":  render_resolved()
    elif p == "escalated": render_escalated()
    else:                  render_chat()

if __name__ == "__main__":
    main()
