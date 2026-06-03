import os
import sys
import re
import base64
import requests as _req
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auth
import support_db

# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════
def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default) or default
    except Exception:
        return os.environ.get(key, default)

GROQ_API_KEY      = _secret("GROQ_API_KEY")
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
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Global ─────────────────────────────────────────────── */
html,body,[data-testid="stAppViewContainer"]{
  background:#f0f4ff!important;min-height:100vh;
}
[data-testid="stMain"]{position:relative;z-index:1;}
header[data-testid="stHeader"]{display:none!important;}
[data-testid="stSidebar"]{display:none!important;}
#MainMenu,footer,.stDeployButton{display:none!important;}
[data-testid="stMain"]>div{padding-top:0!important;}
/* hide streamlit top padding */
.block-container{padding-top:0!important;padding-bottom:120px!important;}

/* ── Navbar ─────────────────────────────────────────────── */
.qnav{
  background:linear-gradient(90deg,#0f172a 0%,#1e3a5f 60%,#1e40af 100%);
  box-shadow:0 4px 24px rgba(30,64,175,.35);
  padding:0 24px;display:flex;align-items:center;justify-content:space-between;
  height:60px;border-radius:0 0 16px 16px;margin-bottom:20px;
}
.qnav-brand{display:flex;align-items:center;gap:12px;}
.qnav-logo{
  width:36px;height:36px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#0ea5e9);
  display:flex;align-items:center;justify-content:center;
  font-size:20px;font-weight:900;color:#fff;letter-spacing:-1px;
  box-shadow:0 2px 10px rgba(59,130,246,.45);
}
.qnav-sep{width:1px;height:28px;background:rgba(255,255,255,.15);margin:0 2px;}
.qnav-title{font-size:14px;font-weight:700;color:#e2e8f0;letter-spacing:.2px;}
.qnav-right{display:flex;align-items:center;gap:12px;}
.qnav-badge{
  background:linear-gradient(135deg,#0ea5e9,#3b82f6);
  color:#fff;font-size:10px;font-weight:700;padding:5px 13px;
  border-radius:99px;letter-spacing:.6px;text-transform:uppercase;
  box-shadow:0 2px 8px rgba(14,165,233,.35);
}
.qnav-user{color:#94a3b8;font-size:12px;}

/* ── Bot header bar ─────────────────────────────────────── */
.bot-bar{
  background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#1e40af 100%);
  border-radius:18px;padding:16px 22px;margin-bottom:16px;
  display:flex;align-items:center;gap:16px;
  box-shadow:0 10px 36px rgba(30,64,175,.25);
}
.bot-av{
  width:50px;height:50px;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#0ea5e9);
  border-radius:14px;display:flex;align-items:center;
  justify-content:center;font-size:24px;
  box-shadow:0 4px 14px rgba(59,130,246,.5);
}
.bot-name{font-size:16px;font-weight:800;color:#f1f5f9;}
.bot-sub{font-size:11px;color:#94a3b8;margin-top:2px;}
.bot-pill{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(22,163,74,.15);border:1px solid rgba(22,163,74,.3);
  color:#4ade80;font-size:10px;font-weight:700;
  padding:3px 10px;border-radius:99px;margin-top:6px;
  text-transform:uppercase;letter-spacing:.4px;
}
.dp{width:5px;height:5px;border-radius:50%;background:#4ade80;
    animation:dp 1.6s ease-in-out infinite;}
@keyframes dp{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.4)}}

/* ── Welcome card ───────────────────────────────────────── */
.welcome-card{
  background:rgba(255,255,255,.82);backdrop-filter:blur(18px);
  border:1.5px solid rgba(30,64,175,.12);border-radius:18px;
  box-shadow:0 8px 28px rgba(30,64,175,.10);
  padding:22px 28px;margin:0 0 16px;
}
.welcome-title{font-size:16px;font-weight:800;color:#0f172a;margin-bottom:4px;}
.welcome-sub{font-size:13px;color:#64748b;}

/* ── Chat messages ──────────────────────────────────────── */
[data-testid="stChatMessage"]{
  background:transparent!important;border:none!important;
  padding:6px 0!important;
}
/* Bot bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"]:not([data-testid*="user"]) [data-testid="stChatMessageContent"]{
  background:#ffffff!important;
  border:1px solid #e2e8f0!important;
  border-radius:4px 18px 18px 18px!important;
  padding:14px 18px!important;
  font-size:14px!important;line-height:1.75!important;color:#1e293b!important;
  box-shadow:0 2px 8px rgba(0,0,0,.06)!important;
  max-width:82%!important;
}
/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"]{
  background:linear-gradient(135deg,#2563eb,#1d4ed8)!important;
  color:#fff!important;border:none!important;
  border-radius:18px 4px 18px 18px!important;
  padding:14px 18px!important;font-size:14px!important;line-height:1.75!important;
  box-shadow:0 4px 14px rgba(37,99,235,.35)!important;
  max-width:82%!important;
}
[data-testid="stChatMessageContent"] p{margin:0 0 8px!important;}
[data-testid="stChatMessageContent"] ol,[data-testid="stChatMessageContent"] ul{margin:8px 0 8px 20px!important;}
[data-testid="stChatMessageContent"] li{margin-bottom:6px!important;}
[data-testid="stChatMessageContent"] strong{color:#1d4ed8!important;}
[data-testid="stChatMessageContent"] code{background:#eff6ff!important;color:#2563eb!important;padding:2px 6px!important;border-radius:4px!important;}

/* ── Resolution strip ───────────────────────────────────── */
.res-row{display:flex;align-items:center;gap:10px;padding:6px 0 14px 52px;flex-wrap:wrap;}
.res-label{font-size:12px;color:#64748b;font-weight:600;}

/* ── Sticky input bar ───────────────────────────────────── */
.input-wrap{
  position:fixed;bottom:0;left:0;right:0;z-index:100;
  background:linear-gradient(to top,#f0f4ff 80%,transparent);
  padding:10px 16px 14px;
}
.input-box{
  background:#fff;border:1.5px solid #c7d2fe;border-radius:16px;
  padding:8px 10px;display:flex;align-items:flex-end;gap:6px;
  box-shadow:0 4px 20px rgba(37,99,235,.12);
  max-width:860px;margin:0 auto;
}
.input-box:focus-within{border-color:#2563eb!important;}

/* ── File uploader — home page (full box with label) ─────── */
.home-upload div[data-testid="stFileUploader"]>label{
  font-size:13px!important;font-weight:600!important;color:#374151!important;
  margin-bottom:6px!important;display:block!important;
}
.home-upload section[data-testid="stFileUploaderDropzone"]{
  border:2px dashed #93c5fd!important;background:#f0f7ff!important;
  border-radius:14px!important;padding:20px 16px!important;transition:all .2s!important;
}
.home-upload section[data-testid="stFileUploaderDropzone"]:hover{
  border-color:#3b82f6!important;background:#dbeafe!important;
}
.home-upload section[data-testid="stFileUploaderDropzone"] button{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;border-radius:8px!important;
  font-size:12px!important;font-weight:700!important;
  padding:7px 16px!important;cursor:pointer!important;
  box-shadow:0 2px 8px rgba(30,64,175,.25)!important;
  width:auto!important;height:auto!important;
}

/* ── Chat bar file uploader — small aligned box ──────────── */
/* Applied globally — Streamlit can't scope to parent divs */
div[data-testid="stFileUploader"]{min-height:0!important;}
div[data-testid="stFileUploader"]>label{display:none!important;}
section[data-testid="stFileUploaderDropzone"]{
  min-height:44px!important;max-height:44px!important;
  padding:0 6px!important;
  border:1.5px solid #bfdbfe!important;
  background:#eff6ff!important;
  border-radius:10px!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  overflow:hidden!important;
}
section[data-testid="stFileUploaderDropzone"]>div{
  flex-direction:row!important;gap:0!important;align-items:center!important;
  width:100%!important;justify-content:center!important;
}
/* hide "Drag and drop" text, keep only Browse button */
section[data-testid="stFileUploaderDropzone"]>div>div:first-child{display:none!important;}
section[data-testid="stFileUploaderDropzone"] button{
  background:transparent!important;border:none!important;
  padding:0!important;min-height:0!important;width:auto!important;height:auto!important;
  font-size:0!important;cursor:pointer!important;box-shadow:none!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
}
section[data-testid="stFileUploaderDropzone"] button::before{
  content:"📎";font-size:22px;line-height:1;display:block;
}
section[data-testid="stFileUploaderDropzone"] button:hover::before{
  content:"📎";opacity:.75;
}
div[data-testid="stFileUploader"] small{display:none!important;}
[data-testid="stFileUploaderDeleteBtn"]{color:#dc2626!important;}
/* When file selected — show chip inline compactly */
div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"]{
  font-size:11px!important;max-width:120px!important;overflow:hidden!important;
  white-space:nowrap!important;text-overflow:ellipsis!important;
}

/* ── Text area inside bar ───────────────────────────────── */
.input-bar .stTextArea textarea{
  background:transparent!important;border:none!important;
  color:#0f172a!important;font-size:14px!important;
  line-height:1.6!important;resize:none!important;
  box-shadow:none!important;outline:none!important;padding:8px 6px!important;
}
.input-bar .stTextArea textarea::placeholder{color:#94a3b8!important;}
.input-bar .stTextArea textarea:focus{box-shadow:none!important;border:none!important;}
.input-bar div[data-baseweb="textarea"]{background:transparent!important;border:none!important;}
/* Align columns inside chat bar to center vertically */
.input-bar [data-testid="stHorizontalBlock"]{align-items:center!important;}
.input-bar [data-testid="stHorizontalBlock"] [data-testid="column"]{
  display:flex!important;align-items:center!important;padding-bottom:0!important;
}

/* ── Form submit buttons ─────────────────────────────────── */
.stFormSubmitButton button{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;
  border-radius:10px!important;font-weight:700!important;
  box-shadow:0 4px 14px rgba(30,64,175,.28)!important;
  transition:all .2s!important;
}
.stFormSubmitButton button:hover{
  box-shadow:0 6px 20px rgba(30,64,175,.45)!important;transform:translateY(-1px)!important;
}
/* Send ➤ — match the 44px height of the upload box */
.input-bar .stFormSubmitButton button{
  height:44px!important;width:44px!important;
  padding:0!important;font-size:20px!important;
  min-height:0!important;border-radius:12px!important;
}

/* ── All regular buttons — proper visible boxes ─────────── */
.stButton>button{
  border-radius:10px!important;font-weight:700!important;font-size:13px!important;
  padding:10px 22px!important;transition:all .2s!important;
  min-height:40px!important;line-height:1.2!important;
}
/* Primary buttons — solid blue */
.stButton>button[kind="primary"],
button[kind="primary"]{
  background:linear-gradient(135deg,#1e40af,#3b82f6)!important;
  color:#fff!important;border:none!important;
  box-shadow:0 4px 14px rgba(30,64,175,.30)!important;
}
.stButton>button[kind="primary"]:hover,
button[kind="primary"]:hover{
  box-shadow:0 6px 20px rgba(30,64,175,.45)!important;
  transform:translateY(-1px)!important;
}
/* Secondary buttons — white box with blue border */
.stButton>button:not([kind="primary"]){
  background:#ffffff!important;
  color:#1e40af!important;
  border:2px solid #3b82f6!important;
  box-shadow:0 2px 8px rgba(30,64,175,.12)!important;
}
.stButton>button:not([kind="primary"]):hover{
  background:#eff6ff!important;
  border-color:#1e40af!important;
  box-shadow:0 4px 14px rgba(30,64,175,.20)!important;
  transform:translateY(-1px)!important;
}

/* ── Ticket card ────────────────────────────────────────── */
.ticket-card{
  background:rgba(255,255,255,.92);
  border:2px solid #bfdbfe;border-radius:20px;
  box-shadow:0 8px 32px rgba(30,64,175,.12);
  padding:24px 28px;margin:16px auto;max-width:500px;
}
.ticket-id{font-size:11px;font-weight:700;color:#1e40af;letter-spacing:.5px;text-transform:uppercase;}
.ticket-num{font-size:26px;font-weight:900;color:#0f172a;margin:4px 0 14px;}
.ticket-row{display:flex;gap:8px;align-items:flex-start;margin-bottom:8px;font-size:13px;}
.ticket-lbl{color:#64748b;min-width:76px;flex-shrink:0;}
.ticket-val{color:#0f172a;font-weight:600;word-break:break-all;}
.ticket-link{
  display:inline-flex;align-items:center;gap:6px;margin-top:14px;
  background:linear-gradient(135deg,#1e40af,#3b82f6);
  color:#fff!important;text-decoration:none;
  font-size:13px;font-weight:700;padding:9px 22px;border-radius:10px;
  box-shadow:0 4px 14px rgba(30,64,175,.30);
}
.badge-new{
  display:inline-block;background:#dbeafe;color:#1e40af;
  font-size:10px;font-weight:700;padding:2px 10px;border-radius:99px;
  text-transform:uppercase;letter-spacing:.4px;
}

/* ── Form inputs ────────────────────────────────────────── */
.stTextArea label,.stTextInput label{font-size:13px!important;font-weight:600!important;color:#374151!important;}
.input-bar .stTextArea label{display:none!important;}
.stSelectbox>div>div,
.stTextInput>div>div>input,
.stTextArea>div>div>textarea{
  background:#fff!important;color:#0f172a!important;
  border:1.5px solid rgba(30,64,175,.20)!important;
  border-radius:10px!important;
}
[data-testid="stAlert"]{border-radius:12px!important;}

@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.anim{animation:fadeUp .3s ease both;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "page":          "chat",
        "user":          None,
        "messages":      [],
        "issue_text":    "",
        "sf_ticket":     None,
        "fu_key":        0,
        "pending_file":  None,
        "session_id":    None,
        "sf_resolution": "",   # full resolution text for step-by-step chat
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

support_db.init_db()
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
    try:
        cfg = auth.get_email_settings()
        if cfg["outlook_email"] and cfg["outlook_password"]:
            return cfg["outlook_email"], cfg["outlook_password"]
    except Exception:
        pass
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
    """Pull open cases + comments from Salesforce. Clears DB first so only fresh data remains."""
    try:
        sf = _sf_client()

        # Clear existing cached cases before fresh sync
        conn = support_db.get_conn()
        conn.execute("DELETE FROM sf_knowledge")
        conn.commit()
        conn.close()

        # Open cases only from Salesforce
        result = sf.query_all(
            "SELECT Id, CaseNumber, Subject, Description, Status "
            "FROM Case WHERE Status != 'Closed' "
            "ORDER BY LastModifiedDate DESC LIMIT 500"
        )
        cases = result.get("records", [])
        if not cases:
            return False, "No open cases found in Salesforce."

        synced = 0
        active_ids = []
        for case in cases:
            cid         = case["Id"]
            case_number = case.get("CaseNumber", "")
            subject     = case.get("Subject", "") or ""
            description = case.get("Description", "") or ""
            status      = case.get("Status", "") or ""

            active_ids.append(cid)

            # ── CaseComments (internal + public) ──────────────
            comments_list = []
            try:
                res = sf.query_all(
                    f"SELECT CommentBody, IsPublished, CreatedDate "
                    f"FROM CaseComment WHERE ParentId='{cid}' "
                    f"ORDER BY CreatedDate ASC"
                )
                for c in res.get("records", []):
                    body = (c.get("CommentBody") or "").strip()
                    if body:
                        comments_list.append(body)
            except Exception:
                pass

            # ── Chatter / FeedItem (Text Posts on case) ───────
            try:
                res = sf.query_all(
                    f"SELECT Body FROM FeedItem "
                    f"WHERE ParentId='{cid}' AND Type='TextPost' "
                    f"ORDER BY CreatedDate ASC LIMIT 30"
                )
                for f in res.get("records", []):
                    body = (f.get("Body") or "").strip()
                    if body:
                        comments_list.append(body)
            except Exception:
                pass

            # ── EmailMessage bodies ────────────────────────────
            try:
                res = sf.query_all(
                    f"SELECT TextBody FROM EmailMessage "
                    f"WHERE ParentId='{cid}' "
                    f"ORDER BY MessageDate ASC LIMIT 20"
                )
                for e in res.get("records", []):
                    body = (e.get("TextBody") or "").strip()
                    if body:
                        comments_list.append(body)
            except Exception:
                pass

            comments = "\n\n".join(comments_list)

            support_db.upsert_sf_case(
                sf_case_id  = cid,
                case_number = case_number,
                subject     = subject,
                description = description,
                status      = status,
                resolution  = "",
                comments    = comments,
            )
            synced += 1

        # Remove cases that no longer exist in Salesforce
        deleted = support_db.delete_removed_cases(active_ids)

        support_db.update_sync_log(synced)
        msg = f"✅ Synced {synced} cases from Salesforce."
        if deleted:
            msg += f" Removed {deleted} deleted case(s)."
        return True, msg

    except Exception as exc:
        return False, f"❌ Sync failed: {exc}"


# ═══════════════════════════════════════════════════════════
# KNOWLEDGE RETRIEVAL — pure DB lookup, no AI generation
# ═══════════════════════════════════════════════════════════

_VISION_MODELS = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]


def _image_to_query(file_data: dict, user_text: str) -> str:
    """Use vision only to get a text description of the screenshot for searching."""
    if not GROQ_API_KEY:
        return user_text
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        for model in _VISION_MODELS:
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": "Describe the error or issue in this screenshot in 2 short sentences. Only describe what you see."},
                        {"type": "image_url", "image_url": {"url": f"data:{file_data['mime']};base64,{file_data['base64']}"}},
                    ]}],
                    max_tokens=100, temperature=0.0,
                )
                return f"{user_text} {r.choices[0].message.content}"
            except Exception:
                continue
    except Exception:
        pass
    return user_text


# Lines that are portal metadata, not answer content
_META_PREFIXES = (
    "Reported By:", "User Email:", "Issue Reported by:",
    "Issue Description:", "AI Troubleshooting Conversation:",
    "Additional Details:", "Troubleshooting Conversation:",
)


def _extract_answer(raw: str) -> str:
    """
    From a Salesforce case description, extract only the answer text.
    - If an Agent/Bot reply exists in the text, return that reply.
    - Otherwise strip metadata headers and return the remaining content.
    """
    if not raw:
        return ""

    # If the text contains an Agent/Bot reply, extract from there
    for marker in ("\nAgent:", "\nBot:"):
        if marker in raw:
            answer = raw.split(marker, 1)[1].strip()
            # Remove any trailing "User:" follow-up lines
            answer = re.split(r"\nUser:", answer)[0].strip()
            return answer

    # No conversation format — strip metadata lines and return description
    lines = raw.splitlines()
    cleaned = []
    skip_next_blank = False
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in _META_PREFIXES):
            skip_next_blank = True
            continue
        if skip_next_blank and stripped == "":
            skip_next_blank = False
            continue
        skip_next_blank = False
        if re.match(r"^User\s*:", stripped):
            continue
        # Strip email addresses first, then dangling labels
        line = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "", line)
        line = re.sub(r"[-–,]?\s*\bCustomer(\s+\w+)?\s*:\s*\w*\s*\(?\s*\)?", "", line, flags=re.IGNORECASE)
        line = re.sub(r",?\s*\bEmail\s*:\s*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\(\s*\)", "", line)       # remove empty parens
        line = re.sub(r"\.{2,}", ".", line)        # collapse double dots
        line = re.sub(r"\s{2,}", " ", line).strip(" -,.")
        if line.strip():
            cleaned.append(line)

    return "\n".join(cleaned).strip()


_GROQ_MODELS   = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
_EXCEL_PATH    = r"C:\Users\ChandruS\Downloads\Worksoft Support Queries.xlsx"
_EXCEL_SHEET   = "Sheet2"


def _load_sf_cases() -> list:
    """Load Salesforce cases from local knowledge source."""
    try:
        import pandas as pd
        df = pd.read_excel(_EXCEL_PATH, sheet_name=_EXCEL_SHEET, engine="openpyxl")
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception:
        return []


def _search_sf_cases(query: str, rows: list, top_n: int = 3) -> list:
    """
    Score each Salesforce case against the query using keyword matching on
    Question/Problem, Error Message, Root Cause, Resolution columns.
    Returns top matching cases sorted by score.
    """
    stop = {"the","a","an","is","it","in","on","at","to","and","or","of",
            "my","i","can","not","be","for","are","was","this","that",
            "with","from","have","has","do","did","get","got","how","why",
            "what","when","where","please","help","issue","problem","error"}
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower())
             if w not in stop and len(w) > 2]
    if not words:
        return rows[:top_n]

    def score(row: dict) -> int:
        q  = str(row.get("Question/Problem", "")).lower()
        em = str(row.get("Error Message",    "")).lower()
        rc = str(row.get("Root Cause",       "")).lower()
        rs = str(row.get("Resolution Steps", "")).lower()
        s  = 0
        for w in words:
            s += q.count(w)  * 4
            s += em.count(w) * 3
            s += rc.count(w) * 2
            s += rs.count(w) * 1
        return s

    scored = sorted(rows, key=score, reverse=True)
    return [r for r in scored if score(r) > 0][:top_n]


def _query_sf_knowledge(query: str) -> str:
    """
    Search Salesforce cases and return resolution steps via Groq.
    """
    rows = _load_sf_cases()
    if not rows:
        return ""

    matches = _search_sf_cases(query, rows)
    if not matches:
        return ""

    # Build context from matched Salesforce cases
    blocks = []
    for i, row in enumerate(matches, 1):
        parts = [f"=== Salesforce Case {i}: {row.get('Question/Problem','')[:120]} ==="]
        if row.get("Error Message"):
            parts.append(f"Error Message: {row['Error Message']}")
        if row.get("Root Cause"):
            parts.append(f"Root Cause: {row['Root Cause']}")
        if row.get("Resolution"):
            parts.append(f"Resolution: {row['Resolution']}")
        if row.get("Resolution Steps"):
            parts.append(f"Resolution Steps:\n{row['Resolution Steps']}")
        blocks.append("\n".join(parts))

    context = ("\n\n" + "=" * 60 + "\n\n").join(blocks)

    ai_answer = _ask_groq(
        system_prompt=(
            "You are a friendly Worksoft Certify support specialist at Qualesce. "
            "You chat with users to help them fix their issues — keep replies SHORT and conversational. "
            "When you find a matching Salesforce case: "
            "1) In 1 sentence say what the issue is. "
            "2) Give the top 3-4 key steps only (numbered). "
            "3) End with: 'Does this help? Let me know if you need more details on any step.' "
            "Do not dump all steps at once. Be concise. "
            "If no case matches, say so in 1 sentence and ask them to describe more."
        ),
        user_prompt=(
            f"User: {query}\n\n"
            f"Salesforce cases:\n{context}\n\n"
            "Reply conversationally with a short answer."
        ),
        max_tokens=400,
    )
    if ai_answer:
        return ai_answer

    # Groq unavailable — return raw Resolution Steps from best matching case
    for row in matches:
        steps = str(row.get("Resolution Steps", "")).strip()
        if steps:
            return steps
    return ""


def _ask_groq(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    """Call Groq chat, tries models in order. Returns empty string on failure."""
    if not GROQ_API_KEY:
        return ""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        for model in _GROQ_MODELS:
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                reply = r.choices[0].message.content.strip()
                if reply:
                    return reply
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _get_all_case_subjects() -> list:
    """Return sf_case_id + subject for all synced cases."""
    conn = support_db.get_conn()
    rows = conn.execute(
        "SELECT sf_case_id, subject FROM sf_knowledge ORDER BY synced_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_cases_by_ids(sf_case_ids: list) -> list:
    """Fetch full case records (description + comments) by ID list."""
    if not sf_case_ids:
        return []
    placeholders = ",".join("?" * len(sf_case_ids))
    conn = support_db.get_conn()
    rows = conn.execute(
        f"SELECT * FROM sf_knowledge WHERE sf_case_id IN ({placeholders})",
        sf_case_ids,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _identify_relevant_cases(user_query: str, all_subjects: list) -> list:
    """
    STEP 1 — Brain scan:
    Show Groq ALL open SF case subjects. It picks which case IDs are relevant
    to the user's issue purely by reading the case names.
    Returns a list of sf_case_ids.
    """
    if not all_subjects:
        return []

    lines = [
        f"{c['sf_case_id']}|{(c['subject'] or 'No subject')[:120]}"
        for c in all_subjects
    ]
    subjects_text = "\n".join(lines)

    reply = _ask_groq(
        system_prompt=(
            "You are a Salesforce case matching engine. "
            "You will receive a user's issue and a list of open case entries in the format: ID|Subject. "
            "Identify which case IDs are relevant to the user's issue by reading the subjects. "
            "Return ONLY the matching case IDs, one per line — nothing else. "
            "Return at most 5 IDs. If nothing matches, return exactly: NONE"
        ),
        user_prompt=(
            f"User issue: {user_query}\n\n"
            f"Salesforce cases:\n{subjects_text}\n\n"
            "Return the matching case IDs only (one per line)."
        ),
        max_tokens=150,
    )

    if not reply or reply.strip().upper() == "NONE":
        return []

    returned_ids = {line.strip() for line in reply.splitlines() if line.strip()}
    valid_ids = [c["sf_case_id"] for c in all_subjects if c["sf_case_id"] in returned_ids]
    return valid_ids


def groq_chat(text: str, history: list, file_data: dict = None) -> str:
    """
    AI-driven step-by-step chat.
    - First message: finds matching SF case, stores full resolution, gives Step 1.
    - Follow-up messages: Groq reads the conversation + full resolution and
      continues naturally — next step, answers questions, wraps up.
    """
    if file_data and file_data["type"] == "image":
        query = _image_to_query(file_data, text)
    elif file_data and file_data["type"] == "text":
        query = f"{text} {file_data['content'][:500]}"
    else:
        query = text

    # ── Greeting detection ──────────────────────────────────
    _GREET_WORDS = {"hi","hello","hey","hii","helo","heya","howdy","greetings",
                    "morning","afternoon","evening","sup","yo","namaste","hai","hola"}
    _GREETINGS   = _GREET_WORDS | {
        "good morning","good afternoon","good evening","good day",
        "what's up","whats up","hi there","hey there","hello there",
        "hi all","hello all",
    }
    clean = re.sub(r"[^a-z\s']", "", text.lower()).strip()
    # Match exact phrase OR first word is a greeting and message is very short (≤4 words)
    first_word = clean.split()[0] if clean.split() else ""
    is_greeting = (
        clean in _GREETINGS
        or all(w in _GREET_WORDS for w in clean.split())
        or (first_word in _GREET_WORDS and len(clean.split()) <= 4
            and not any(c.isdigit() for c in clean))
    )
    if is_greeting:
        user = st.session_state.get("user")
        name = f" {user['name'].split()[0]}" if user else ""
        return _ask_groq(
            system_prompt=(
                "You are a friendly Worksoft Certify AI support agent at Qualesce. "
                "The user has greeted you. Respond warmly in 2-3 sentences: "
                "greet them back, introduce yourself briefly, and ask what Worksoft issue they need help with today."
            ),
            user_prompt=f"User greeted: '{text}'. User name: {name.strip() or 'unknown'}.",
            max_tokens=120,
        ) or (
            f"Hello{name}! 👋 I'm your Worksoft Certify AI support agent at Qualesce.\n\n"
            "How can I help you today? Describe your issue and I'll walk you through the fix step by step."
        )

    # ── Continuing an active resolution with Groq ───────────
    sf_resolution = st.session_state.get("sf_resolution", "")
    if sf_resolution:
        # Build conversation history string for Groq
        chat_history = ""
        for m in history[-10:]:  # last 10 messages for context
            role = "Support Agent" if m["role"] == "assistant" else "User"
            chat_history += f"{role}: {m['content']}\n\n"

        reply = _ask_groq(
            system_prompt=(
                "You are a friendly Worksoft Certify support specialist at Qualesce. "
                "You are guiding a user through a troubleshooting process step by step. "
                "You have the full resolution steps below. "
                "Rules:\n"
                "- Give ONE step at a time only.\n"
                "- After each step say: 'Reply **next** when ready for the next step.'\n"
                "- If the user says next/ok/continue/yes/sure/done — give the next step.\n"
                "- If the user asks a question about a step — answer it briefly, then remind them to say next.\n"
                "- If all steps are done — say the issue should be resolved and ask if it helped.\n"
                "- Never give more than one step per reply.\n"
                f"\nFull resolution steps:\n{sf_resolution}"
            ),
            user_prompt=(
                f"Conversation so far:\n{chat_history}\n"
                f"User just said: {text}\n\n"
                "Continue the step-by-step troubleshooting. Give only the next step."
            ),
            max_tokens=350,
        )
        if reply:
            return reply

    # ── New question — find matching SF case ────────────────
    st.session_state.sf_resolution = ""

    rows = _load_sf_cases()
    if not rows:
        return "No Salesforce cases available. Please contact support."

    matches = _search_sf_cases(query, rows)
    if not matches:
        return (
            "I couldn't find a matching Salesforce case for your issue.\n\n"
            "Please click **'Still need help'** to raise a support ticket."
        )

    best      = matches[0]
    problem   = str(best.get("Question/Problem", "your issue")).strip()
    raw_steps = str(best.get("Resolution Steps", "")).strip()
    if not raw_steps:
        raw_steps = str(best.get("Resolution", "")).strip()

    if not raw_steps:
        return (
            "A related Salesforce case was found but no resolution steps are recorded.\n\n"
            "Please click **'Still need help'** to raise a support ticket."
        )

    # Store resolution in session so follow-ups can continue
    st.session_state.sf_resolution = raw_steps

    # Ask Groq to introduce the case and give only Step 1
    reply = _ask_groq(
        system_prompt=(
            "You are a friendly Worksoft Certify support specialist at Qualesce. "
            "You found a matching Salesforce case. "
            "Introduce the case in 1 sentence, then give ONLY Step 1 of the resolution. "
            "End with: 'Reply **next** when you are ready for the next step.' "
            "Never give more than one step."
            f"\nFull resolution steps:\n{raw_steps}"
        ),
        user_prompt=(
            f"User issue: {text}\n"
            f"Matching case: {problem}\n\n"
            "Introduce and give only Step 1."
        ),
        max_tokens=300,
    )

    if reply:
        return reply

    # Groq unavailable — return first line as step 1
    first_line = raw_steps.splitlines()[0].strip()
    return f"**{problem}**\n\nStep 1: {first_line}\n\nReply **next** when ready for the next step."


# ═══════════════════════════════════════════════════════════
# NAVBAR
# ═══════════════════════════════════════════════════════════
def render_navbar():
    user = st.session_state.get("user")
    usr  = f'<span class="qnav-user">👤 {user["name"]}</span>' if user else ""
    st.html(f"""
<div style="background:linear-gradient(90deg,#0f172a 0%,#1e3a5f 60%,#1e40af 100%);
     box-shadow:0 4px 24px rgba(30,64,175,.35);padding:0 24px;
     display:flex;align-items:center;justify-content:space-between;
     height:60px;border-radius:0 0 16px 16px;margin-bottom:4px;">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="width:36px;height:36px;border-radius:10px;flex-shrink:0;
         background:linear-gradient(135deg,#2563eb,#0ea5e9);
         display:flex;align-items:center;justify-content:center;
         font-size:20px;font-weight:900;color:#fff;
         box-shadow:0 2px 10px rgba(59,130,246,.45);">Q</div>
    <div style="width:1px;height:28px;background:rgba(255,255,255,.18);margin:0 4px;"></div>
    <span style="font-size:14px;font-weight:700;color:#e2e8f0;letter-spacing:.2px;">Worksoft Support Portal</span>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    {usr}
    <span style="background:linear-gradient(135deg,#0ea5e9,#3b82f6);color:#fff;
         font-size:11px;font-weight:700;padding:5px 14px;border-radius:99px;
         letter-spacing:.5px;text-transform:uppercase;
         box-shadow:0 2px 8px rgba(14,165,233,.4);">🤖 AI Agent</span>
  </div>
</div>""")


# ═══════════════════════════════════════════════════════════
# PAGE: CHAT
# ═══════════════════════════════════════════════════════════
def render_chat():
    render_navbar()

    # ── Compact bot status bar ──────────────────────────────
    user = st.session_state.get("user")
    uname = f" · {user['name']}" if user else ""
    st.html(f"""
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:14px;
     padding:10px 18px;margin-bottom:8px;display:flex;align-items:center;
     justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.05);">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,#2563eb,#0ea5e9);
         display:flex;align-items:center;justify-content:center;font-size:20px;">🤖</div>
    <div>
      <div style="font-size:14px;font-weight:700;color:#0f172a;">Qualesce AI Support Agent{uname}</div>
      <div style="font-size:11px;color:#64748b;margin-top:1px;">Salesforce Cases · Powered by Groq AI</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:6px;">
    <span style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
    <span style="font-size:11px;color:#22c55e;font-weight:600;">Online</span>
  </div>
</div>""")

    # ── Home / Identity form ────────────────────────────────
    if not st.session_state.user:

        # Hero section
        st.markdown("""
<div style="text-align:center;padding:28px 0 20px;" class="anim">
  <div style="font-size:52px;margin-bottom:12px;">🤖</div>
  <div style="font-size:26px;font-weight:900;color:#0f172a;letter-spacing:-.5px;margin-bottom:6px;">
    Worksoft AI Support Agent
  </div>
  <div style="font-size:14px;color:#64748b;max-width:400px;margin:0 auto;">
    Get instant troubleshooting help for Worksoft Certify issues.<br>
    Attach a screenshot and our AI will analyze it for you.
  </div>
</div>""", unsafe_allow_html=True)

        # Feature pills
        st.markdown("""
<div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin-bottom:24px;">
  <span style="background:#eff6ff;border:1.5px solid #bfdbfe;color:#1e40af;
        font-size:12px;font-weight:700;padding:6px 14px;border-radius:99px;">
    🔍 AI Analysis
  </span>
  <span style="background:#f0fdf4;border:1.5px solid #bbf7d0;color:#166534;
        font-size:12px;font-weight:700;padding:6px 14px;border-radius:99px;">
    📎 Screenshot Upload
  </span>
  <span style="background:#faf5ff;border:1.5px solid #e9d5ff;color:#7e22ce;
        font-size:12px;font-weight:700;padding:6px 14px;border-radius:99px;">
    🎫 Auto Ticket Raising
  </span>
</div>""", unsafe_allow_html=True)

        # Main form card
        st.markdown("""
<div style="background:rgba(255,255,255,.90);backdrop-filter:blur(18px);
     border:1.5px solid rgba(30,64,175,.14);border-radius:20px;
     box-shadow:0 10px 36px rgba(30,64,175,.12);padding:28px 32px;
     max-width:580px;margin:0 auto 8px;" class="anim">
  <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:4px;">
    👋 Let&#39;s get started
  </div>
  <div style="font-size:13px;color:#64748b;margin-bottom:20px;">
    Fill in your details and describe your issue or upload a screenshot.
  </div>
</div>""", unsafe_allow_html=True)

        # Home page screenshot upload — full box style via .home-upload wrapper
        st.markdown('<div class="home-upload">', unsafe_allow_html=True)
        home_file = st.file_uploader(
            "📸 Upload a screenshot of your issue (optional)",
            type=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
            key=f"home_fu_{st.session_state.fu_key}",
            help="Attach an error screenshot and the AI will analyze it",
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # Show preview if file selected
        if home_file:
            col_prev, _ = st.columns([1, 2])
            with col_prev:
                st.image(home_file, caption=f"📎 {home_file.name}", use_container_width=True)

        with st.form("id_form", clear_on_submit=False):
            c1, c2 = st.columns(2)
            with c1:
                name  = st.text_input("Your Name *", placeholder="e.g. Aravind R")
            with c2:
                email = st.text_input("Your Email *", placeholder="you@qualesce.com")

            issue_desc = st.text_area(
                "Describe your issue (optional)",
                placeholder="e.g. Worksoft agent is not connecting after server restart…",
                height=100,
            )

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            go = st.form_submit_button(
                "🚀  Start Chatting with AI Agent",
                use_container_width=True,
                type="primary",
            )

        if go:
            if not name.strip() or not email.strip():
                st.error("Please enter your name and email to continue.")
            else:
                st.session_state.user = {"name": name.strip(), "email": email.strip()}

                # Create DB session
                sid = support_db.create_session(name.strip(), email.strip())
                st.session_state.session_id = sid

                first_content = issue_desc.strip() or ""
                file_data = _process_upload(home_file) if home_file else None

                welcome_reply = (
                    f"Hi **{name.strip()}**! 👋 I'm your Worksoft Certify support agent.\n\n"
                    "Describe your issue below — or attach a **screenshot, log file, or PDF** "
                    "using the 📎 icon and I'll analyze it for you."
                )
                st.session_state.messages.append({"role": "assistant", "content": welcome_reply})
                support_db.save_message(sid, "assistant", welcome_reply)

                if first_content or file_data:
                    user_msg = {"role": "user", "content": first_content}
                    fname = home_file.name if home_file else ""
                    ftype = (file_data or {}).get("type", "")
                    if file_data:
                        user_msg["file"] = file_data
                    if not st.session_state.issue_text:
                        st.session_state.issue_text = first_content or f"[Screenshot: {fname}]"
                    st.session_state.messages.append(user_msg)
                    support_db.save_message(sid, "user", first_content, fname, ftype)

                    with st.spinner("Agent is analyzing your issue…"):
                        reply = groq_chat(first_content, st.session_state.messages, file_data)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    support_db.save_message(sid, "assistant", reply)
                    st.session_state.fu_key += 1

                st.rerun()
        return

    # ── Render messages ─────────────────────────────────────
    for msg in st.session_state.messages:
        role = msg["role"]
        av   = "🤖" if role == "assistant" else "👤"
        with st.chat_message(role, avatar=av):
            st.markdown(msg["content"])
            # Show attached file if present
            fdata = msg.get("file")
            if fdata:
                if fdata["type"] == "image":
                    st.image(
                        f"data:{fdata['mime']};base64,{fdata['base64']}",
                        caption=fdata["name"], width=300
                    )
                else:
                    st.caption(f"📎 {fdata['name']}")

    # ── Resolution strip ────────────────────────────────────
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "assistant" and len(msgs) >= 2:
        st.markdown('<div class="res-row">', unsafe_allow_html=True)
        st.markdown('<span class="res-label">Was this helpful?</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        rc1, rc2, _ = st.columns([1.2, 1.4, 4])
        with rc1:
            if st.button("✅ Yes, resolved!", use_container_width=True, type="primary"):
                st.session_state.page = "resolved"; st.rerun()
        with rc2:
            if st.button("❌ Still need help", use_container_width=True):
                st.session_state.page = "escalated"; st.rerun()

    # ── Fixed input bar at bottom ────────────────────────────
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

    # ── Process send ────────────────────────────────────────
    if send and (user_input.strip() or uploaded):
        file_data = _process_upload(uploaded) if uploaded else None

        user_msg = {"role": "user", "content": user_input.strip()}
        fname = uploaded.name if uploaded else ""
        ftype = (file_data or {}).get("type", "")
        if file_data:
            user_msg["file"] = file_data
        if not st.session_state.issue_text:
            st.session_state.issue_text = user_input.strip() or f"[Attached: {fname}]"

        st.session_state.messages.append(user_msg)
        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_message(sid, "user", user_input.strip(), fname, ftype)

        with st.spinner(""):
            reply = groq_chat(user_input.strip(), st.session_state.messages, file_data)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        if sid:
            support_db.save_message(sid, "assistant", reply)
        st.rerun()

    # ── New chat button ─────────────────────────────────────
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    _, nc, _ = st.columns([4, 1.5, 4])
    with nc:
        if st.button("🔄 New Chat", use_container_width=True):
            for k in ["messages","issue_text","sf_ticket","user","pending_file"]:
                st.session_state[k] = [] if k=="messages" else ("" if k=="issue_text" else None)
            st.session_state.sf_resolution = ""
            st.session_state.fu_key += 1
            st.session_state.page = "chat"; st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: RESOLVED
# ═══════════════════════════════════════════════════════════
def render_resolved():
    render_navbar()
    user = st.session_state.user or {"name": "there"}
    st.markdown(f"""
<div style="max-width:480px;margin:48px auto;text-align:center;
     background:rgba(255,255,255,.88);backdrop-filter:blur(18px);
     border:1.5px solid rgba(22,163,74,.25);border-radius:24px;
     box-shadow:0 12px 40px rgba(22,163,74,.12);
     padding:48px 32px;" class="anim">
  <div style="font-size:56px;margin-bottom:12px;">🎉</div>
  <div style="font-size:22px;font-weight:900;color:#16a34a;margin-bottom:8px;">Issue Resolved!</div>
  <div style="font-size:14px;color:#475569;margin-bottom:24px;">
    Glad I could help, <strong style="color:#0f172a;">{user["name"]}</strong>!<br>
    Come back anytime you need Worksoft support.
  </div>
  <div style="background:#dcfce7;border:1px solid rgba(22,163,74,.25);
       border-radius:12px;padding:12px 20px;font-size:13px;color:#166534;font-weight:600;">
    ✅ No ticket raised
  </div>
</div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1,1.4,1])
    with col:
        if st.button("Start New Chat", use_container_width=True, type="primary"):
            sid = st.session_state.get("session_id")
            if sid:
                support_db.update_session_status(sid, "resolved")
            for k in ["messages","issue_text","sf_ticket","user","session_id"]:
                st.session_state[k] = [] if k=="messages" else ("" if k=="issue_text" else None)
            st.session_state.sf_resolution = ""
            st.session_state.page = "chat"; st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: ESCALATED
# ═══════════════════════════════════════════════════════════
def render_escalated():
    render_navbar()
    user       = st.session_state.user or {"name":"User","email":""}
    issue_text = st.session_state.issue_text or "Worksoft issue (see conversation)"

    if st.session_state.sf_ticket:
        _render_ticket(user, st.session_state.sf_ticket); return

    st.markdown("""
<div style="max-width:540px;margin:16px auto;text-align:center;
     background:rgba(255,255,255,.88);backdrop-filter:blur(18px);
     border:1.5px solid rgba(30,64,175,.15);border-radius:20px;
     box-shadow:0 8px 28px rgba(30,64,175,.10);
     padding:24px 28px;" class="anim">
  <div style="font-size:28px;margin-bottom:8px;">🔔</div>
  <div style="font-size:17px;font-weight:800;color:#0f172a;margin-bottom:4px;">Escalating to IT Admin</div>
  <div style="font-size:13px;color:#64748b;">
    We'll raise a Salesforce case and notify the IT Admin.<br>You'll be CC'd on the email with the case link.
  </div>
</div>""", unsafe_allow_html=True)

    with st.form("esc_form"):
        extra    = st.text_area("Additional details (optional)",
                                placeholder="Error code, business impact, steps already tried…", height=90)
        priority = st.selectbox("Priority", ["High","Critical","Medium","Low"])
        submit   = st.form_submit_button("🚀 Raise Ticket & Notify IT Admin",
                                         use_container_width=True, type="primary")

    if submit:
        convo = "\n\n".join(
            f"{'User' if m['role']=='user' else 'Agent'}: {m['content']}"
            for m in st.session_state.messages
        )
        desc = (
            f"Reported by: {user['name']} ({user['email']})\n\nIssue:\n{issue_text}"
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

        # Persist to support DB
        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_ticket(
                session_id   = sid,
                user_name    = user["name"],
                user_email   = user["email"],
                issue_text   = issue_text,
                priority     = priority,
                sf_case_number = ticket.get("case_number",""),
                sf_case_url    = ticket.get("url",""),
                sf_error       = sf_error,
                email_sent     = email_ok,
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
    <span class="ticket-val">{user["name"]} ({user["email"]})</span>
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
        st.success(f"✅ IT Admin notified ({IT_ADMIN_EMAIL}) · You've been CC'd at {user['email']}")
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
            for k in ["messages","issue_text","sf_ticket","user","session_id"]:
                st.session_state[k] = [] if k=="messages" else ("" if k=="issue_text" else None)
            st.session_state.sf_resolution = ""
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
