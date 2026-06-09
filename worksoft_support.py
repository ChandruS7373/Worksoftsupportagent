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

GROQ_API_KEY      = _secret("GROQ_API_KEY")
ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")   # optional fallback
OPENAI_API_KEY    = _secret("OPENAI_API_KEY")       # optional fallback
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
/* ── RESET & BASE ── */
*{box-sizing:border-box;margin:0;padding:0;}
html,body,[data-testid="stAppViewContainer"]{
  background:#f5f5f5!important;
  min-height:100vh;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',sans-serif!important;
}
header,#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stSidebar"]{display:none!important;}
[data-testid="stMain"]>div{padding-top:0!important;}
.block-container{max-width:100%!important;padding:10px 16px 0!important;}

/* ── NAVBAR ── */
.nav{
  height:56px;background:#ffffff;
  border-bottom:1px solid #e5e7eb;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;margin-bottom:12px;border-radius:12px;
  box-shadow:0 1px 4px rgba(0,0,0,.06);
}
.nav-left{display:flex;align-items:center;gap:12px;}
.nav-logo{
  width:36px;height:36px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  display:flex;align-items:center;justify-content:center;
  font-size:18px;
}
.nav-title{font-size:14px;font-weight:700;color:#111827;letter-spacing:-.2px;}
.nav-sub{font-size:11px;color:#9ca3af;margin-top:1px;}
.nav-right{display:flex;align-items:center;gap:8px;}
.nav-pill{
  font-size:11px;font-weight:600;padding:5px 14px;border-radius:99px;
  background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;
  letter-spacing:.2px;
}
.nav-divider{width:1px;height:20px;background:#e5e7eb;}

/* ── LEFT PANEL (ChatPDF sidebar style) ── */
.lp{
  background:#111827;
  border-radius:16px;
  padding:20px 16px;display:flex;flex-direction:column;gap:14px;
  min-height:calc(100vh - 100px);
  box-shadow:0 4px 20px rgba(0,0,0,.18);
}
.lp-logo{display:flex;align-items:center;gap:11px;
  padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,.07);}
.lp-av{width:40px;height:40px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:20px;}
.lp-t{font-size:13px;font-weight:700;color:#f9fafb;}
.lp-s{font-size:10px;color:#6b7280;margin-top:2px;}
.lp-status{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);
  color:#4ade80;font-size:10px;font-weight:600;
  padding:4px 10px;border-radius:99px;text-transform:uppercase;letter-spacing:.4px;
  width:fit-content;
}
.lp-dot{width:5px;height:5px;border-radius:50%;background:#22c55e;
  animation:pulse 1.8s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(1.5)}}
.lp-sec-title{font-size:9px;font-weight:600;color:#4b5563;
  text-transform:uppercase;letter-spacing:.9px;margin-bottom:5px;}
.lp-stat{
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.07);
  border-radius:10px;padding:12px 14px;
}
.lp-num{font-size:26px;font-weight:800;color:#f3f4f6;line-height:1;}
.lp-numlbl{font-size:10px;color:#6b7280;margin-top:3px;}
.lp-feature{
  display:flex;align-items:center;gap:9px;padding:6px 0;
  border-bottom:1px solid rgba(255,255,255,.05);font-size:11.5px;color:#9ca3af;
}
.lp-feature:last-child{border-bottom:none;}
.lp-feat-icon{
  width:24px;height:24px;border-radius:6px;flex-shrink:0;
  background:rgba(37,99,235,.15);
  display:flex;align-items:center;justify-content:center;font-size:12px;
}

/* ── CHAT PANEL (ChatPDF main area) ── */
.cwin{
  background:#ffffff;border-radius:16px;
  border:1px solid #e5e7eb;
  box-shadow:0 2px 12px rgba(0,0,0,.06);
  overflow:hidden;
}
.chead{
  height:60px;display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;background:#ffffff;
  border-bottom:1px solid #f3f4f6;
}
.chead-left{display:flex;align-items:center;gap:12px;}
.chead-av{
  width:38px;height:38px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:18px;
}
.chead-name{font-size:14px;font-weight:700;color:#111827;}
.chead-sub{font-size:11px;color:#6b7280;margin-top:2px;}
.chead-status{
  display:inline-flex;align-items:center;gap:4px;
  color:#16a34a;font-size:10px;font-weight:600;
  margin-top:2px;
}
.chead-dot{width:6px;height:6px;border-radius:50%;background:#22c55e;
  animation:pulse 1.8s infinite;}
.chead-rt{text-align:right;}
.chead-rt-lbl{font-size:9.5px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px;}
.chead-rt-val{font-size:11.5px;font-weight:600;color:#374151;margin-top:2px;}

/* ── INPUT BAR (ChatPDF style) ── */
.cinput{background:#f9fafb;border-top:1px solid #f3f4f6;padding:10px 14px;}
.input-box{
  background:#ffffff;border:1.5px solid #e5e7eb;border-radius:14px;
  padding:8px 10px 8px 14px;display:flex;align-items:flex-end;gap:8px;
  box-shadow:0 1px 4px rgba(0,0,0,.05);transition:.18s;
}
.input-box:focus-within{
  border-color:#2563eb!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.08)!important;
}

/* ── INPUT TEXT AREA ── */
.input-bar .stTextArea textarea{
  background:transparent!important;border:none!important;
  color:#111827!important;font-size:14px!important;
  line-height:1.55!important;resize:none!important;
  box-shadow:none!important;outline:none!important;padding:6px 4px!important;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',sans-serif!important;
}
.input-bar .stTextArea textarea::placeholder{color:#9ca3af!important;font-size:13.5px!important;}
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
  border:1.5px solid #e5e7eb!important;background:#f9fafb!important;
  border-radius:10px!important;display:flex!important;align-items:center!important;
  justify-content:center!important;overflow:hidden!important;transition:.18s!important;}
section[data-testid="stFileUploaderDropzone"]:hover{
  border-color:#2563eb!important;background:#eff6ff!important;}
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
  font-size:10px!important;max-width:110px!important;overflow:hidden!important;
  white-space:nowrap!important;text-overflow:ellipsis!important;}

/* ── HOME FILE UPLOADER ── */
.home-upload div[data-testid="stFileUploader"]>label{
  font-size:12px!important;font-weight:600!important;color:#374151!important;
  margin-bottom:4px!important;display:block!important;}
.home-upload section[data-testid="stFileUploaderDropzone"]{
  border:2px dashed #d1d5db!important;background:#f9fafb!important;
  border-radius:12px!important;padding:16px!important;
  min-height:auto!important;max-height:none!important;}
.home-upload section[data-testid="stFileUploaderDropzone"] button{
  background:#2563eb!important;color:#fff!important;border:none!important;
  border-radius:8px!important;font-size:12px!important;font-weight:600!important;
  padding:6px 14px!important;cursor:pointer!important;
  width:auto!important;height:auto!important;}

/* ── SEND BUTTON (circular, ChatPDF style) ── */
.stFormSubmitButton button{
  background:#2563eb!important;color:#fff!important;border:none!important;
  border-radius:50%!important;font-weight:700!important;
  box-shadow:0 2px 8px rgba(37,99,235,.30)!important;transition:all .18s!important;
}
.stFormSubmitButton button:hover{
  background:#1d4ed8!important;
  box-shadow:0 4px 14px rgba(37,99,235,.40)!important;transform:scale(1.06)!important;}
.input-bar .stFormSubmitButton button{
  height:40px!important;width:40px!important;padding:0!important;
  font-size:16px!important;min-height:0!important;border-radius:50%!important;}

/* ── BUTTONS ── */
.stButton>button{
  border-radius:10px!important;font-weight:600!important;font-size:13px!important;
  padding:8px 18px!important;transition:all .18s!important;
  min-height:36px!important;line-height:1.2!important;
}
.stButton>button[kind="primary"],button[kind="primary"]{
  background:#2563eb!important;color:#fff!important;border:none!important;
  box-shadow:0 2px 8px rgba(37,99,235,.25)!important;}
.stButton>button[kind="primary"]:hover{
  background:#1d4ed8!important;
  box-shadow:0 4px 14px rgba(37,99,235,.38)!important;transform:translateY(-1px)!important;}
.stButton>button:not([kind="primary"]){
  background:#fff!important;color:#374151!important;
  border:1.5px solid #d1d5db!important;}
.stButton>button:not([kind="primary"]):hover{
  background:#f9fafb!important;border-color:#9ca3af!important;transform:translateY(-1px)!important;}

/* ── FORM INPUTS ── */
.stTextArea label,.stTextInput label{
  font-size:12px!important;font-weight:600!important;color:#374151!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{
  background:#ffffff!important;color:#111827!important;
  border:1.5px solid #d1d5db!important;border-radius:10px!important;font-size:13px!important;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',sans-serif!important;}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{
  border-color:#2563eb!important;box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;}
[data-testid="stAlert"]{border-radius:12px!important;}

/* ── SELECT BOX ── */
.stSelectbox>div>div{
  border:1.5px solid #d1d5db!important;border-radius:10px!important;
  background:#fff!important;font-size:13px!important;}
.stSelectbox>div>div:focus-within{border-color:#2563eb!important;}

/* ── LOGIN / INTRO CARD ── */
.login-wrap{max-width:480px;margin:20px auto;}
.login-banner{
  background:linear-gradient(135deg,#1e3a8a,#2563eb,#0ea5e9);
  border-radius:16px 16px 0 0;padding:32px 28px 24px;text-align:center;}
.login-icon{font-size:44px;margin-bottom:10px;}
.login-title{font-size:20px;font-weight:800;color:#fff;letter-spacing:-.3px;}
.login-sub{font-size:12px;color:rgba(255,255,255,.72);margin-top:5px;}
.login-chips{display:flex;justify-content:center;gap:6px;flex-wrap:wrap;margin-top:12px;}
.chip{font-size:10px;font-weight:600;padding:4px 12px;border-radius:99px;
  background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);color:#fff;}
.login-body{
  background:#fff;border-radius:0 0 16px 16px;
  border:1px solid #e5e7eb;border-top:none;padding:24px 28px;}

/* ── TICKET ── */
.ticket-card{
  background:#fff;border:1px solid #e5e7eb;border-radius:16px;
  box-shadow:0 4px 20px rgba(0,0,0,.07);padding:20px 24px;
  margin:12px auto;max-width:480px;}
.ticket-id{font-size:10px;font-weight:600;color:#2563eb;letter-spacing:.5px;
  text-transform:uppercase;}
.ticket-num{font-size:22px;font-weight:800;color:#111827;margin:4px 0 12px;}
.ticket-row{display:flex;gap:10px;align-items:flex-start;margin-bottom:6px;font-size:12.5px;}
.ticket-lbl{color:#6b7280;min-width:70px;flex-shrink:0;}
.ticket-val{color:#111827;font-weight:600;word-break:break-all;}
.ticket-link{
  display:inline-flex;align-items:center;gap:6px;margin-top:12px;
  background:#2563eb;color:#fff!important;
  text-decoration:none;font-size:12.5px;font-weight:600;
  padding:8px 18px;border-radius:9px;box-shadow:0 2px 8px rgba(37,99,235,.28);}
.badge-new{display:inline-block;background:#eff6ff;color:#2563eb;
  font-size:9px;font-weight:700;padding:2px 8px;border-radius:99px;
  text-transform:uppercase;letter-spacing:.4px;}

/* ── SUPPORT LEVEL ROW ── */
.support-level-row{
  display:flex;align-items:center;gap:10px;padding:8px 4px 4px;
}
.support-level-label{
  font-size:11.5px;color:#6b7280;font-weight:600;white-space:nowrap;
}

@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.anim{animation:fadeUp .3s ease both;}
@keyframes scaleIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}
.anim-scale{animation:scaleIn .28s ease both;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "page":                    "intro",
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
        "popup_reason":            "resolved",
        "help_count":              0,
        "chat_started":            False,
        "sf_diagnosis":            "",
        "turn_count":              0,
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
# AI HELPERS  — Groq primary, Claude/OpenAI optional fallback
# ═══════════════════════════════════════════════════════════
_GROQ_MODEL        = "llama-3.3-70b-versatile"       # primary — fast + capable
_GROQ_FAST_MODEL   = "llama-3.1-8b-instant"          # tiny calls (classification, 1-word answers)
_GROQ_VISION_MODEL = "llama-3.2-11b-vision-preview"  # image analysis

# kept only as fallback constants (used if Groq key is missing)
_OPENAI_MODEL      = "gpt-4o"
_OPENAI_FAST_MODEL = "gpt-4o-mini"
_CLAUDE_MODEL      = "claude-sonnet-4-6"
_CLAUDE_FAST_MODEL = "claude-haiku-4-5-20251001"


@st.cache_data(ttl=300, show_spinner=False)
def _cached_case_subjects():
    """Case subjects list — cached 300 s so the same case list is used within a session."""
    return support_db.get_all_case_subjects()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_case_pool():
    """Case pool with snippets — cached 300 s."""
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
def _groq_client():
    from groq import Groq
    return Groq(api_key=GROQ_API_KEY)


def _ask_groq(
    system_prompt: str,
    user_prompt:   str,
    max_tokens:    int   = 800,
    history:       list  = None,
    fast:          bool  = False,
    stream:        bool  = False,
    temperature:   float = 0.3,
) -> str:
    """
    Groq LLM call — primary AI engine.
    stream=True    → streams token-by-token into st.session_state['_stream_slot'].
    fast=True      → uses the smaller/faster model (for 1-word classifiers, greetings).
    temperature    → 0.0 for deterministic classification/retrieval, 0.3 for chat responses.
    Falls back to Claude then OpenAI if GROQ_API_KEY is not set.
    """
    if not GROQ_API_KEY:
        return _ask_claude_fallback(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature)

    # Classification calls (fast=True) must be fully deterministic
    effective_temp = 0.0 if fast else temperature

    try:
        client = _groq_client()
        model  = _GROQ_FAST_MODEL if fast else _GROQ_MODEL

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            # Exclude the last message if it's a user message — it's added as user_prompt below
            hist = history[-10:]
            for i, msg in enumerate(hist):
                role    = msg.get("role", "")
                content = msg.get("content", "")
                # Skip the last entry if it duplicates the current user_prompt
                if i == len(hist) - 1 and role == "user" and content.strip() == user_prompt.strip():
                    continue
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:800]})
        messages.append({"role": "user", "content": user_prompt})

        stream_slot = st.session_state.get("_stream_slot") if stream else None

        if stream_slot is not None:
            full       = ""
            completion = client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=effective_temp, stream=True,
            )
            for chunk in completion:
                delta = chunk.choices[0].delta.content or ""
                if not full and delta:
                    typing = st.session_state.pop("_typing_slot", None)
                    if typing:
                        typing.empty()
                full += delta
                stream_slot.markdown(full + " ▌")
            if full:
                stream_slot.markdown(full)
            return full

        completion = client.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=effective_temp,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        import traceback
        print(f"[Groq error] {e}\n{traceback.format_exc()}")
        return _ask_claude_fallback(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature)


def _ask_ai(system_prompt: str, user_prompt: str, max_tokens: int = 800,
            history: list = None, fast: bool = False, stream: bool = False,
            temperature: float = 0.3) -> str:
    """Single entry-point for all AI calls — routes through Groq."""
    return _ask_groq(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature)


def _ask_claude_fallback(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature=0.3):
    """Claude fallback when Groq key is not configured."""
    if not ANTHROPIC_API_KEY:
        return _ask_openai_fallback(system_prompt, user_prompt, max_tokens, history, fast)
    effective_temp = 0.0 if fast else temperature
    try:
        import anthropic
        client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        model    = _CLAUDE_FAST_MODEL if fast else _CLAUDE_MODEL
        msgs     = []
        if history:
            for m in history[-8:]:
                if m.get("role") in ("user","assistant") and m.get("content"):
                    msgs.append({"role": m["role"], "content": str(m["content"])[:600]})
        msgs.append({"role": "user", "content": user_prompt})
        stream_slot = st.session_state.get("_stream_slot") if (stream and not fast) else None
        if stream_slot:
            full = ""
            with client.messages.stream(model=model, system=system_prompt,
                                        messages=msgs, max_tokens=max_tokens) as s:
                for txt in s.text_stream:
                    if not full:
                        t = st.session_state.pop("_typing_slot", None)
                        if t: t.empty()
                    full += txt
                    stream_slot.markdown(full + " ▌")
            if full: stream_slot.markdown(full)
            return full
        r = client.messages.create(model=model, system=system_prompt,
                                   messages=msgs, max_tokens=max_tokens, temperature=effective_temp)
        return (r.content[0].text or "") if r.content else ""
    except Exception as e:
        import traceback
        print(f"[Claude fallback error] {e}\n{traceback.format_exc()}")
        return _ask_openai_fallback(system_prompt, user_prompt, max_tokens, history, fast)


def _ask_openai_fallback(system_prompt, user_prompt, max_tokens, history, fast):
    """OpenAI last-resort fallback."""
    if not OPENAI_API_KEY:
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        model  = _OPENAI_FAST_MODEL if fast else _OPENAI_MODEL
        msgs   = [{"role": "system", "content": system_prompt}]
        if history:
            for m in history[-8:]:
                if m.get("role") in ("user","assistant") and m.get("content"):
                    msgs.append({"role": m["role"], "content": str(m["content"])[:600]})
        msgs.append({"role": "user", "content": user_prompt})
        r = client.chat.completions.create(model=model, messages=msgs,
                                           max_tokens=max_tokens, temperature=0.45)
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        import traceback
        print(f"[OpenAI fallback error] {e}\n{traceback.format_exc()}")
        return ""


def _describe_image(file_data: dict, user_text: str) -> str:
    """Describe a screenshot using Groq vision model."""
    if not GROQ_API_KEY:
        return user_text
    try:
        client = _groq_client()
        r = client.chat.completions.create(
            model=_GROQ_VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{file_data['mime']};base64,{file_data['base64']}"}},
                {"type": "text",
                 "text": (
                     "Describe the error or issue visible in this Worksoft screenshot in 2 short sentences. "
                     "Focus on error messages, codes, UI state, or warnings. "
                     f"User also says: {user_text or '(no description provided)'}"
                 )},
            ]}],
            max_tokens=200,
        )
        desc = (r.choices[0].message.content or "").strip()
        return f"{user_text} — Screenshot shows: {desc}".strip() if desc else user_text
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
    st.session_state.popup_reason           = "resolved"
    st.session_state.help_count             = 0


def _ai_detects_resolution(history: list) -> bool:
    """Fast AI call: did the user's latest message indicate the issue is fixed?"""
    last_user = next(
        (m["content"] for m in reversed(history) if m.get("role") == "user"), ""
    )
    if not last_user or len(last_user.strip()) < 3:
        return False
    verdict = _ask_ai(
        system_prompt=(
            "You are reviewing a single support chat message. "
            "Answer with exactly one word — YES or NO:\n"
            "YES — the user is saying their issue is now fixed / resolved / working / sorted\n"
            "NO  — they are still having the problem, asking a question, or describing a failure\n"
            "One word only."
        ),
        user_prompt=f"User message: {last_user[:300]}",
        max_tokens=3,
        fast=True,
    )
    return verdict.strip().upper().startswith("YES")


def _ai_feels_stuck(history: list) -> bool:
    """
    Fast AI call: read the last few messages and decide if the conversation
    is stuck (same problem persisting, repeated failures) vs progressing.
    Returns True if stuck.
    """
    recent = [m for m in history[-8:] if m.get("role") in ("user", "assistant")]
    if not recent:
        return False
    convo_text = "\n".join(
        f"{m['role'].title()}: {m['content'][:300]}" for m in recent
    )
    verdict = _ask_ai(
        system_prompt=(
            "You are reviewing a Worksoft IT support chat. "
            "Read the conversation and respond with exactly one word:\n"
            "STUCK — the user's issue is not being resolved "
            "(same error keeps happening, steps not working, going in circles, no progress)\n"
            "PROGRESSING — things are moving forward and a fix seems likely\n"
            "One word only. No explanation."
        ),
        user_prompt=f"Conversation so far:\n{convo_text}",
        max_tokens=5,
        fast=True,
    )
    return verdict.strip().upper().startswith("STUCK")


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
html,body{
  background:#f9fafb;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Inter',sans-serif;
}
.msgs{
  height:560px;overflow-y:auto;overflow-x:hidden;
  padding:24px 20px 12px;
  scrollbar-width:thin;scrollbar-color:#d1d5db #f9fafb;
  background:#f9fafb;
}
.msgs::-webkit-scrollbar{width:4px;}
.msgs::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:4px;}
.msgs::-webkit-scrollbar-track{background:transparent;}
/* message rows */
.row{display:flex;align-items:flex-start;gap:12px;margin-bottom:20px;}
.row.u{flex-direction:row-reverse;}
/* avatars */
.av{width:34px;height:34px;border-radius:50%;flex-shrink:0;margin-top:2px;
    display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;}
.av.a{background:#2563eb;color:#fff;}
.av.u{background:#111827;color:#fff;font-size:12px;}
@keyframes avIn{from{opacity:0;transform:scale(.5)}to{opacity:1;transform:scale(1)}}
.row.new .av{animation:avIn .25s ease both;}
/* bubbles */
.bub{
  max-width:76%;padding:12px 16px;font-size:13.5px;
  line-height:1.75;word-break:break-word;
}
.bub.a{
  background:#ffffff;border:1px solid #e5e7eb;color:#111827;
  border-radius:4px 16px 16px 16px;
  box-shadow:0 1px 3px rgba(0,0,0,.06);
}
.bub.u{
  background:#111827;color:#f9fafb;
  border-radius:16px 4px 16px 16px;
}
@keyframes botIn{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:none}}
@keyframes usrIn{from{opacity:0;transform:translateX(12px)}to{opacity:1;transform:none}}
.row.new.a .bub{animation:botIn .28s ease both;}
.row.new.u .bub{animation:usrIn .24s ease both;}
/* bubble text */
.bub p{margin:0 0 8px;}.bub p:last-child{margin-bottom:0;}
.bub ol,.bub ul{margin:8px 0 8px 20px;}.bub li{margin-bottom:6px;line-height:1.7;}
.bub strong{color:#1d4ed8;font-weight:700;}.bub.u strong{color:#93c5fd;}
.bub code{background:#f3f4f6;color:#1d4ed8;padding:2px 6px;border-radius:4px;font-size:12px;font-family:'SFMono-Regular',Consolas,monospace;}
.bub.u code{background:rgba(255,255,255,.12);color:#bfdbfe;}
.bub hr{border:none;border-top:1px solid #f3f4f6;margin:10px 0;}
/* step cards */
.vstep{
  background:#f9fafb;border:1px solid #e5e7eb;border-left:3px solid #2563eb;
  border-radius:0 10px 10px 10px;
  padding:10px 14px;margin:7px 0;font-size:13px;
}
.vstep-num{
  display:inline-flex;align-items:center;justify-content:center;
  width:22px;height:22px;border-radius:50%;
  background:#2563eb;color:#fff;font-size:10px;font-weight:700;
  margin-right:9px;flex-shrink:0;
}
.vstep-row{display:flex;align-items:flex-start;}
.vstep-body{flex:1;}
.vstep-action{font-weight:700;color:#111827;margin-bottom:3px;font-size:13px;}
.vstep-why{font-size:12px;color:#6b7280;margin-bottom:4px;line-height:1.65;}
.vpath{display:flex;align-items:center;flex-wrap:wrap;gap:3px;
  background:#1f2937;border-radius:6px;padding:7px 10px;margin-top:4px;}
.vpath-seg{color:#9ca3af;font-family:'SFMono-Regular',Consolas,monospace;font-size:11px;}
.vpath-sep{color:#4b5563;margin:0 1px;}
.vpath-seg.file{color:#7dd3fc;font-weight:700;}
.vcode{
  background:#1f2937;border-radius:6px;padding:8px 12px;margin-top:4px;
  font-family:'SFMono-Regular',Consolas,monospace;font-size:11.5px;
  color:#e5e7eb;white-space:pre-wrap;border-left:3px solid #2563eb;
}
.vcode .ck{color:#7dd3fc;}.vcode .cv{color:#86efac;}
/* typing indicator */
@keyframes db{0%,60%,100%{transform:translateY(0);opacity:.3}30%{transform:translateY(-5px);opacity:1}}
@keyframes tIn{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}
.qtyping-row{display:flex;align-items:flex-end;gap:12px;margin-bottom:14px;animation:tIn .22s ease both;}
.qtyping-av{width:34px;height:34px;border-radius:50%;background:#2563eb;
  display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;}
.qtyping-bubble{background:#ffffff;border:1px solid #e5e7eb;
  border-radius:4px 16px 16px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06);
  padding:12px 16px;display:flex;gap:5px;align-items:center;}
.qtyping-bubble span{width:7px;height:7px;border-radius:50%;background:#9ca3af;
  display:inline-block;animation:db 1.1s infinite ease-in-out;}
.qtyping-bubble span:nth-child(2){animation-delay:.16s;}
.qtyping-bubble span:nth-child(3){animation-delay:.32s;}
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
@keyframes typingFade{from{opacity:0;transform:translateX(-16px) translateY(8px);}to{opacity:1;transform:none;}}
@keyframes dotBounce{0%,60%,100%{transform:translateY(0);opacity:.3;}30%{transform:translateY(-8px);opacity:1;}}
.qt-row{display:flex;align-items:flex-end;gap:10px;padding:6px 16px 10px;animation:typingFade .32s ease both;}
.qt-av{
  width:34px;height:34px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:17px;
  box-shadow:0 2px 10px rgba(59,130,246,.34);
}
.qt-bubble{
  background:#fff;
  border:1.5px solid rgba(99,102,241,.14);
  border-radius:4px 18px 18px 18px;
  box-shadow:0 2px 12px rgba(99,102,241,.09);
  padding:13px 18px;display:flex;gap:6px;align-items:center;
}
.qt-bubble span{
  width:8px;height:8px;border-radius:50%;background:#a5b4fc;
  display:inline-block;animation:dotBounce 1.15s infinite ease-in-out;
}
.qt-bubble span:nth-child(2){animation-delay:.18s;}
.qt-bubble span:nth-child(3){animation-delay:.36s;}
</style>
<div class="qt-row">
  <div class="qt-av">🤖</div>
  <div class="qt-bubble"><span></span><span></span><span></span></div>
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
        temperature=0.0,
    )

    candidate_ids: list = []
    if s1_resp and re.sub(r"[^a-zA-Z]", "", s1_resp).upper() != "NONE":
        for token in re.findall(r"\d+", s1_resp):
            idx = int(token) - 1
            if 0 <= idx < len(all_subs):
                cid = all_subs[idx]["sf_case_id"]
                if cid not in candidate_ids:
                    candidate_ids.append(cid)

    # Merge keyword-search hits — larger pool gives retrieval more chances to find the right case
    kw_hits = support_db.search_knowledge(query, top_n=12)
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
        temperature=0.0,
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
# CHAT ENGINE  — Groq AI + Salesforce knowledge, fully conversational
# ═══════════════════════════════════════════════════════════
def process_chat(text: str, history: list, file_data: dict = None) -> str:
    """
    Single entry-point for every user message.
    1. Describes any uploaded image/file.
    2. Searches Salesforce for relevant resolved cases.
    3. Sends everything to Groq and streams the response.
    4. Detects resolution or stuck conversation for the L1/L2 popup.
    No phase state machine — the AI handles the full conversation naturally.
    """
    # ── Resolve file/image input ───────────────────────────────
    if file_data and file_data["type"] == "image":
        query = _describe_image(file_data, text)
    elif file_data and file_data["type"] == "text":
        query = f"{text}\n\nAttached file content:\n{file_data['content'][:1200]}"
    else:
        query = text

    # ── Pull matching Salesforce cases ─────────────────────────
    matches = _retrieve_best_cases(query, top_n=5) if query.strip() else []
    knowledge_text, has_content, ctx_summary = (
        _build_case_knowledge(matches, query) if matches else ("", False, "")
    )
    if has_content:
        st.session_state.sf_resolution   = knowledge_text[:3000]
        st.session_state.sf_case_context = ctx_summary

    sf_res = st.session_state.get("sf_resolution", "")

    # ── Build system prompt ────────────────────────────────────
    sf_section = ""
    if has_content:
        sf_section = (
            "\n\n=== SALESFORCE KNOWLEDGE BASE (real resolved cases) ===\n"
            + knowledge_text
            + "\n=== END OF KNOWLEDGE BASE ===\n"
        )
    elif sf_res:
        sf_section = (
            "\n\n=== SALESFORCE KNOWLEDGE BASE (from earlier in this conversation) ===\n"
            + sf_res[:2000]
            + "\n=== END ===\n"
        )

    # Determine how many user turns have happened so far
    user_turn = sum(1 for m in history if m.get("role") == "user")
    st.session_state.turn_count = user_turn

    if user_turn <= 1:
        conversation_style = """

=== PHASE 1 — UNDERSTAND BEFORE SOLVING ===
The user has just sent their FIRST message. Your job right now is to understand the problem,
NOT to provide solutions or troubleshooting steps yet.

Respond with:
  1. A brief, warm acknowledgment of what they said (1 sentence max).
  2. Then ask 2–3 focused clarifying questions (bullet list), such as:
     • Which exact product are they using? (CTM / Certify / Portal / Capture) — skip if already stated.
     • What exact error message or behaviour are they seeing?
     • What have they already tried, if anything?

Keep the response SHORT, friendly, and conversational.
DO NOT give any steps, fixes, or solutions in this turn — that comes after you understand the issue.
"""
    else:
        conversation_style = """

=== PHASE 2 — RESOLVE THE ISSUE ===
CONVERSATION STYLE:
- Be warm, direct, and concise — like a knowledgeable colleague
- For technical Worksoft issues: give numbered steps (1. **Action** — reason)
- For general questions: answer naturally, no steps needed
- Keep follow-up replies SHORT (2-4 sentences) — this is a chat, not a report
- After giving steps, always invite the user: "Let me know what happens! 👇"
- If the user says the issue is fixed → celebrate briefly, suggest clicking ✅ Resolved at L1
- Never mention Salesforce case IDs or database internals to the user
"""

    system_prompt = (
        f"{_EXPERT_PERSONA}\n\n"
        f"{_WORKSOFT_DOMAIN}"
        + sf_section
        + f"""

You are a smart, conversational AI support assistant for Worksoft products at Qualesce.
You can answer ANY question the user asks.
Your PRIMARY knowledge source is the Salesforce resolved cases above — always use them when available.
When Salesforce case data is present, follow those resolution steps exactly — do not substitute, skip, or invent alternative steps.
For questions outside Worksoft, answer naturally from your general knowledge.
{conversation_style}"""
    )

    # ── Stream Groq response ───────────────────────────────────
    # Guard: surface a clear message if no LLM key is configured at all
    if not GROQ_API_KEY and not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
        return (
            "⚠️ **No AI API key is configured.**\n\n"
            "Please add your `GROQ_API_KEY` (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) "
            "to `.streamlit/secrets.toml` and restart the app.\n\n"
            "Get a free Groq key at **console.groq.com** — it takes under a minute."
        )

    reply = _ask_ai(
        system_prompt=system_prompt,
        user_prompt=query,
        history=history,
        max_tokens=900,
        stream=True,
    ) or "I'm having trouble connecting to the AI right now. Please check your API key in `.streamlit/secrets.toml` and restart."

    st.session_state.chat_phase = "resolving"

    # ── Resolution / stuck detection ───────────────────────────
    if not st.session_state.get("show_resolution_popup") and not st.session_state.get("resolution_check_shown"):
        if _ai_detects_resolution(history + [{"role": "user", "content": text}]):
            st.session_state.show_resolution_popup = True
            st.session_state.popup_reason          = "resolved"
        else:
            user_msg_count = sum(1 for m in history if m.get("role") == "user")
            st.session_state.help_count = st.session_state.get("help_count", 0) + 1
            if user_msg_count >= 4 and (st.session_state.help_count >= 2 or user_msg_count >= 5):
                if _ai_feels_stuck(history):
                    st.session_state.show_resolution_popup = True
                    st.session_state.popup_reason          = "stuck"

    return reply


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
      <div class="nav-sub">Qualesce &nbsp;·&nbsp; Salesforce Knowledge Base</div>
    </div>
  </div>
  <div class="nav-right">
    <div class="nav-divider"></div>
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
        f'<div class="lp-feature"><span class="lp-feat-icon">{i}</span>{l}</div>'
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
    _live_chat()


@st.dialog("Support Level Check 🔔")
def _show_resolution_dialog():
    """Popup shown when AI detects resolution OR when conversation is stuck after 4-5 turns."""
    reason = st.session_state.get("popup_reason", "resolved")

    if reason == "stuck":
        icon    = "⚠️"
        heading = "This looks like it needs L2 support"
        subtext = (
            "We've tried a few steps but the issue doesn't seem to be resolving. "
            "Would you like to escalate to the <strong>L2 specialist team</strong>, "
            "or continue troubleshooting with AI?"
        )
    else:
        icon    = "🔍"
        heading = "Can we close this at L1?"
        subtext = (
            "It looks like your issue may be sorted. "
            "Confirm below — or keep chatting if you still need help."
        )

    st.markdown(f"""
<div style="text-align:center;padding:6px 0 18px;">
  <div style="font-size:52px;margin-bottom:12px;">{icon}</div>
  <div style="font-size:18px;font-weight:800;color:#0f172a;margin-bottom:8px;">
    {heading}
  </div>
  <div style="font-size:13px;color:#64748b;line-height:1.7;">
    {subtext}
  </div>
</div>
""", unsafe_allow_html=True)

    # For stuck conversations, swap button prominence (L2 is the recommended action)
    is_stuck = (st.session_state.get("popup_reason") == "stuck")
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        l1_type = "secondary" if is_stuck else "primary"
        if st.button("✅  Resolved at L1", use_container_width=True, type=l1_type):
            st.session_state.resolution_check_shown = True
            st.session_state.show_resolution_popup  = False
            st.session_state.page = "resolved"
            st.rerun(scope="app")
    with btn_col2:
        l2_type = "primary" if is_stuck else "secondary"
        if st.button("🔺  Forward to L2", use_container_width=True, type=l2_type):
            st.session_state.resolution_check_shown = True
            st.session_state.show_resolution_popup  = False
            st.session_state.page = "escalated"
            st.rerun(scope="app")

    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    keep_label = "💬  Keep chatting with AI" if is_stuck else "💬  Not yet — keep chatting"
    if st.button(keep_label, use_container_width=True):
        # Dismiss this popup instance; AI can trigger it again later if still stuck
        st.session_state.resolution_check_shown = False
        st.session_state.show_resolution_popup  = False
        st.session_state.help_count             = 0   # reset counter so it re-evaluates fresh
        st.rerun()


@st.fragment
def _live_chat():
    """
    Fragment: only the chat panel reruns on each message — sidebar/navbar stay frozen.
    """
    # ── Auto-welcome on very first load ──────────────────────
    if not st.session_state.get("chat_started"):
        st.session_state.chat_started = True
        _first_name = (st.session_state.get("user", {}).get("name") or "there").split()[0]
        welcome = (
            f"Hello, **{_first_name}**! 👋 I'm your **Worksoft AI Support Assistant**, "
            f"powered by real resolved cases from our Salesforce knowledge base.\n\n"
            "I'm here to help with **CTM, Certify, Portal, and Capture** — and I'll make sure I fully understand your issue before suggesting any fix.\n\n"
            "Go ahead and describe what's happening. You can also attach a **screenshot, log file, or PDF** using the 📎 icon below."
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})

    # ── Full-width chat top bar ──────────────────────────────
    _user  = st.session_state.get("user", {})
    _uname = _user.get("name", "Guest")
    _uemail = _user.get("email", "")
    _initials = (_uname[0].upper()) if _uname and _uname != "Guest" else "G"
    _user_tag = _uname + (f" &nbsp;&middot;&nbsp; {_uemail}" if _uemail else "")
    st.html(f"""
<style>
/* Full-width chat page */
html,body,[data-testid="stAppViewContainer"]{{background:#f9fafb!important;}}
.block-container{{max-width:860px!important;margin:0 auto!important;padding:0 0 0!important;}}
/* Top bar */
.ctop{{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 20px;background:#ffffff;
  border-bottom:1px solid #e5e7eb;
  border-radius:16px 16px 0 0;
  margin-bottom:0;
}}
.ctop-left{{display:flex;align-items:center;gap:12px;}}
.ctop-av{{
  width:38px;height:38px;border-radius:50%;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:18px;
}}
.ctop-name{{font-size:15px;font-weight:700;color:#111827;}}
.ctop-sub{{font-size:11px;color:#9ca3af;margin-top:1px;}}
.ctop-online{{
  display:inline-flex;align-items:center;gap:5px;
  font-size:10.5px;font-weight:600;color:#16a34a;margin-top:2px;
}}
.ctop-dot{{width:6px;height:6px;border-radius:50%;background:#22c55e;animation:pulse 1.8s infinite;}}
.ctop-right{{display:flex;align-items:center;gap:8px;}}
.ctop-user{{
  display:flex;align-items:center;gap:8px;
  background:#f3f4f6;border:1px solid #e5e7eb;
  border-radius:8px;padding:6px 12px;
}}
.ctop-user-av{{
  width:26px;height:26px;border-radius:50%;
  background:#111827;color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;flex-shrink:0;
}}
.ctop-user-name{{font-size:12px;font-weight:600;color:#374151;}}
</style>
<div class="ctop">
  <div class="ctop-left">
    <div class="ctop-av">🤖</div>
    <div>
      <div class="ctop-name">Worksoft AI Support</div>
      <span class="ctop-online"><span class="ctop-dot"></span>Online &amp; Ready</span>
    </div>
  </div>
  <div class="ctop-right">
    <div class="ctop-user">
      <div class="ctop-user-av">{_initials}</div>
      <span class="ctop-user-name">{_user_tag}</span>
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
            '<div class="support-level-row">'
            '<span class="support-level-label">Close ticket:</span>'
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
            st.session_state.page = "intro"; st.rerun()


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

    if st.button("← Back to Chat", key="esc_back"):
        st.session_state.page = "chat"
        st.session_state.show_resolution_popup = False
        st.rerun()

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
            st.session_state.page = "intro"; st.rerun()
    with c2:
        if st.button("💬 Back to Chat", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: INTRO (name + email gate)
# ═══════════════════════════════════════════════════════════
def render_intro():
    info = support_db.get_sync_info()
    cnt  = info.get("case_count", 0)
    last = info.get("last_sync", "")[:16].replace("T", " ") if info.get("last_sync") else "Never"

    # ── Global CSS injected once ─────────────────────────────
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:#f3f4f6!important;}
.block-container{max-width:100%!important;padding:16px 20px 0!important;}

/* ── LEFT PANEL content ── */
.il-panel{background:#111827;border-radius:16px;padding:36px 28px;
  min-height:87vh;display:flex;flex-direction:column;gap:22px;}
.il-brand{display:flex;align-items:center;gap:14px;}
.il-av{width:46px;height:46px;border-radius:13px;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;}
.il-name{font-size:17px;font-weight:800;color:#f9fafb;letter-spacing:-.3px;}
.il-tagline{font-size:11px;color:#6b7280;margin-top:2px;}
.il-divider{height:1px;background:rgba(255,255,255,.07);margin:2px 0;}
.il-desc{font-size:12.5px;color:#9ca3af;line-height:1.75;
  border-left:3px solid #2563eb;padding-left:14px;}
.il-section-title{font-size:9px;font-weight:700;color:#4b5563;
  text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;}
.il-stat-card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);
  border-radius:11px;padding:14px 18px;position:relative;overflow:hidden;}
.il-stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,#2563eb,#0ea5e9);}
.il-stat-num{font-size:28px;font-weight:900;color:#f9fafb;line-height:1;}
.il-stat-lbl{font-size:11px;color:#6b7280;margin-top:4px;}
.il-feat{display:flex;align-items:center;gap:10px;padding:7px 0;
  border-bottom:1px solid rgba(255,255,255,.06);font-size:12px;color:#9ca3af;}
.il-feat:last-child{border-bottom:none;}
.il-feat-icon{width:26px;height:26px;border-radius:7px;
  background:rgba(37,99,235,.15);
  display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;}
.il-products{display:flex;gap:6px;flex-wrap:wrap;}
.il-prod{font-size:11px;font-weight:600;padding:4px 13px;border-radius:6px;
  background:rgba(37,99,235,.15);border:1px solid rgba(37,99,235,.25);color:#93c5fd;}

/* ── RIGHT PANEL ── */
.ir-header{padding:44px 8px 20px;}
.ir-welcome{font-size:26px;font-weight:800;color:#111827;letter-spacing:-.4px;margin-bottom:8px;}
.ir-sub{font-size:13px;color:#6b7280;line-height:1.65;}
.ir-footer{text-align:center;font-size:11.5px;color:#9ca3af;line-height:1.6;margin-top:8px;}

/* ── Rectangle Start Chat button ── */
.stFormSubmitButton>button{
  border-radius:8px!important;height:50px!important;
  font-size:15px!important;font-weight:700!important;
  background:#111827!important;color:#fff!important;
  border:none!important;letter-spacing:.3px!important;box-shadow:none!important;
}
.stFormSubmitButton>button:hover{background:#1f2937!important;transform:none!important;}

/* ── Sync Salesforce button ── */
[data-testid="stBaseButton-secondary"]{
  border-radius:8px!important;height:40px!important;
  font-size:13px!important;font-weight:600!important;
  background:#f9fafb!important;color:#374151!important;
  border:1.5px solid #d1d5db!important;letter-spacing:.1px!important;
}
[data-testid="stBaseButton-secondary"]:hover{
  background:#f3f4f6!important;border-color:#9ca3af!important;
}

/* Form field labels */
.stTextInput label{font-size:13px!important;font-weight:600!important;color:#374151!important;}
.stTextInput>div>div>input{
  height:46px!important;border-radius:8px!important;
  border:1.5px solid #d1d5db!important;font-size:14px!important;
  padding:0 14px!important;background:#fff!important;color:#111827!important;
}
.stTextInput>div>div>input:focus{border-color:#2563eb!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;}
</style>""", unsafe_allow_html=True)

    # ── Two-column layout — Streamlit handles the split ──────
    left_col, right_col = st.columns([1.1, 1.4], gap="medium")

    # ── LEFT: pure self-contained HTML (no widgets) ──────────
    with left_col:
        st.markdown(f"""
<div class="il-panel">
  <div class="il-brand">
    <div class="il-av">🤖</div>
    <div>
      <div class="il-name">Worksoft AI Support</div>
      <div class="il-tagline">Qualesce &nbsp;·&nbsp; Powered by Salesforce</div>
    </div>
  </div>

  <div class="il-divider"></div>

  <div class="il-desc">
    Intelligent L1 support for Worksoft products — trained on real resolved cases
    from your Salesforce knowledge base.
  </div>

  <div>
    <div class="il-section-title">Knowledge Base</div>
    <div class="il-stat-card">
      <div class="il-stat-num">{cnt}</div>
      <div class="il-stat-lbl">Resolved cases &nbsp;·&nbsp; Last sync: {last}</div>
    </div>
  </div>

  <div>
    <div class="il-section-title">Products Supported</div>
    <div class="il-products">
      <span class="il-prod">CTM</span>
      <span class="il-prod">Certify</span>
      <span class="il-prod">Portal</span>
      <span class="il-prod">Capture</span>
    </div>
  </div>

  <div>
    <div class="il-section-title">Capabilities</div>
    <div class="il-feat"><span class="il-feat-icon">🔍</span>&nbsp; Smart AI semantic search</div>
    <div class="il-feat"><span class="il-feat-icon">📎</span>&nbsp; File, screenshot &amp; PDF support</div>
    <div class="il-feat"><span class="il-feat-icon">🎫</span>&nbsp; Auto Salesforce ticket creation</div>
    <div class="il-feat"><span class="il-feat-icon">📧</span>&nbsp; IT Admin email notification</div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── RIGHT: welcome header + Streamlit form ────────────────
    with right_col:
        st.markdown("""
<div class="ir-header">
  <div class="ir-welcome">Welcome 👋</div>
  <div class="ir-sub">Tell us who you are to get started.<br>
  Your AI support session will be personalised.</div>
</div>""", unsafe_allow_html=True)

        with st.form("intro_form"):
            name  = st.text_input("Your Name",  placeholder="e.g. Aravind R")
            email = st.text_input("Work Email", placeholder="you@qualesce.com")
            st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "Start Chat  →", use_container_width=True, type="primary"
            )

        st.markdown('<div class="ir-footer">Your details are used only to personalise<br>support and attach to any ticket raised.</div>',
                    unsafe_allow_html=True)

        st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)
        st.markdown('<hr style="border:none;border-top:1px solid #e5e7eb;margin:0;">', unsafe_allow_html=True)
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        sync_clicked = st.button("🔄  Sync Salesforce", key="intro_sync_sf", use_container_width=True)

    # ── Handle sync (must be outside columns so spinner renders full-width) ──
    if sync_clicked:
        with st.spinner("Syncing knowledge base from Salesforce…"):
            ok, msg = sync_sf_knowledge()
        if ok:
            _cached_case_subjects.clear()
            st.success(f"✅ {msg}")
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    # ── Handle submit (outside columns — variables still in scope) ──
    if submitted:
        name_val  = name.strip()  or "Guest"
        email_val = email.strip() or ""
        if email_val and "@" not in email_val:
            st.error("Please enter a valid email address.")
        else:
            st.session_state.user = {"name": name_val, "email": email_val}
            if not st.session_state.get("session_id"):
                st.session_state.session_id = support_db.create_session(name_val, email_val)
            st.session_state.page = "chat"
            st.rerun()


# ═══════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════
def main():
    p = st.session_state.page
    if   p == "intro":     render_intro()
    elif p == "resolved":  render_resolved()
    elif p == "escalated": render_escalated()
    else:                  render_chat()

if __name__ == "__main__":
    main()
