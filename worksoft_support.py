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
        "page":            "chat",
        "user":            None,
        "messages":        [],
        "issue_text":      "",
        "sf_ticket":       None,
        "fu_key":          0,
        "pending_file":    None,
        "session_id":      None,
        "sf_resolution":   "",
        "sf_case_context": "",
        "sf_steps":        [],
        "sf_step_idx":     0,
        "chat_phase":      "idle",
        "initial_issue":   "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

support_db.init_db()
github_sync.ensure_db_downloaded()   # pull DB from GitHub if missing (Streamlit Cloud restarts)
github_sync.start_sync_thread()       # auto-push DB to GitHub every 30s when it changes
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

        conn = support_db.get_conn()
        conn.execute("DELETE FROM sf_knowledge")
        conn.commit()
        conn.close()

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
_GROQ_MODELS      = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
_GROQ_FAST_MODELS = ["llama-3.1-8b-instant"]          # for cheap one-liners
_VISION_MODELS    = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]


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
    "You are a smart, warm Worksoft support expert at Qualesce. "
    "Talk exactly like ChatGPT or DeepSeek would — natural, human, conversational. "
    "Be empathetic, concise, and helpful. Use contractions. Ask follow-up questions when you need clarity. "
    "Never sound robotic, formal, or scripted. "
    "You have deep knowledge of Worksoft CTM, Certify, Portal, Capture, and agent machines. "
    "When case content is available you show it directly. When it's not, you engage naturally and troubleshoot."
)

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


def _ask_groq(system_prompt: str, user_prompt: str, max_tokens: int = 800,
              history: list = None, fast: bool = False) -> str:
    """
    fast=True  → uses llama-3.1-8b-instant (cheap tasks: clarifying Q, greeting, wrap-up)
    fast=False → uses llama-3.3-70b-versatile then falls back to 8b (answer generation)
    history    → last 4 turns included as context (trimmed to 400 chars each)
    """
    if not GROQ_API_KEY:
        return ""
    try:
        client = _groq_client()
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history[-4:]:          # 4 turns is enough context
                role    = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:400]})
        messages.append({"role": "user", "content": user_prompt})
        models = _GROQ_FAST_MODELS if fast else _GROQ_MODELS
        for model in models:
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )
                reply = r.choices[0].message.content or ""
                reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
                if reply:
                    return reply
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _describe_image(file_data: dict, user_text: str) -> str:
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
                    max_tokens=120, temperature=0.0,
                )
                return f"{user_text} {r.choices[0].message.content}"
            except Exception:
                continue
    except Exception:
        pass
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
    st.session_state.sf_resolution   = ""
    st.session_state.sf_case_context = ""
    st.session_state.sf_steps        = []
    st.session_state.sf_step_idx     = 0
    st.session_state.chat_phase      = "idle"
    st.session_state.initial_issue   = ""


_NEXT_WORDS = {"next","ok","done","continue","yes","sure","ready","proceed",
               "got","good","great","worked","fixed","move","go","yep","yeah"}


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


def _parse_steps(content: str) -> list:
    """Split case content into individual steps by numbered list, then paragraph, then line."""
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

    s1_resp = _ask_groq(
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

    s2_resp = _ask_groq(
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
# CHAT ENGINE
# ═══════════════════════════════════════════════════════════
def groq_chat(text: str, history: list, file_data: dict = None) -> str:
    if file_data and file_data["type"] == "image":
        query = _describe_image(file_data, text)
    elif file_data and file_data["type"] == "text":
        query = f"{text} {file_data['content'][:500]}"
    else:
        query = text

    user      = st.session_state.get("user")
    user_name = user["name"].split()[0] if user else "there"
    phase     = st.session_state.get("chat_phase", "idle")

    # ── GREETING ──────────────────────────────────────────────
    if _is_greeting(text) and not file_data and phase == "idle":
        return _ask_groq(
            system_prompt=(
                f"{_EXPERT_PERSONA} The user just greeted you. "
                f"Say hi to {user_name} by name, mention you're their Worksoft support buddy, "
                "and warmly ask what they're running into. One or two sentences max."
            ),
            user_prompt=f"User said: '{text}'",
            history=history,
            max_tokens=100,
            fast=True,
        ) or f"Hey {user_name}! I'm your Worksoft support buddy. What's going on today?"

    # ── RESOLVING PHASE — follow-ups from case context ────────
    sf_resolution = st.session_state.get("sf_resolution", "")

    if phase == "resolving" and sf_resolution:
        user_words = set(re.findall(r"[a-z]+", text.lower()))
        _DONE = {"thanks","thank","resolved","fixed","worked","done",
                 "sorted","great","perfect","awesome","solved","cheers"}
        if user_words & _DONE and len(text.strip()) < 80:
            _reset_chat_state()
            return _ask_groq(
                system_prompt=(
                    f"{_EXPERT_PERSONA} The issue is resolved. "
                    "Wrap up warmly in 1-2 sentences and tell them to hit '✅ Yes, resolved!' below."
                ),
                user_prompt=text,
                history=history,
                max_tokens=80,
                fast=True,
            ) or "Glad that sorted it! Go ahead and hit **✅ Yes, resolved!** below."

        case_ctx = st.session_state.get("sf_case_context", "")
        return _ask_groq(
            system_prompt=(
                f"{_EXPERT_PERSONA}\n\n"
                "The user got the resolution and is asking a follow-up. "
                "Respond like a colleague sitting next to them — conversational, helpful, human. "
                "You can draw on your own Worksoft knowledge to explain further, "
                "suggest what to check next, or troubleshoot if a step didn't work. "
                "Keep it short and natural.\n\n"
                + (f"Issue context: {case_ctx}\n" if case_ctx else "")
                + f"Resolution reference:\n{sf_resolution[:1500]}"
            ),
            user_prompt=text,
            history=history,
            max_tokens=300,
        ) or "Happy to help — which step are you stuck on? I'll walk you through it."

    # ── INTAKE PHASE — user answered our clarifying question, now search ──
    if phase == "intake":
        original   = st.session_state.get("initial_issue", "")
        # Combine original issue + clarification for richer search
        full_query = f"{original}. {text}".strip(". ") if original else text
        _reset_chat_state()
        return _resolve(full_query, text, history)

    # ── IDLE — first message on this issue ────────────────────
    # Images/files: skip clarification and go straight to answer
    if file_data:
        _reset_chat_state()
        return _resolve(query, text, history)

    # Store the issue and ask ONE smart clarifying question before answering
    st.session_state.initial_issue = text
    st.session_state.chat_phase    = "intake"

    clarifying_q = _ask_groq(
        system_prompt=(
            f"{_EXPERT_PERSONA}\n\n"
            "The user just described a Worksoft issue. Before looking up a solution, "
            "ask ONE short, targeted question to understand their situation better.\n\n"
            "Good questions to pick from (choose the most relevant ONE):\n"
            "- Which Worksoft module is this — CTM, Certify, Portal, or Capture?\n"
            "- What's the exact error message or error code you're seeing?\n"
            "- Is this happening on all machines or just one specific machine?\n"
            "- Did this start after a recent update, restart, or config change?\n"
            "- How long has this been happening — is it new or was it working before?\n\n"
            "Rules:\n"
            "- Pick the ONE question that would most help narrow down the fix.\n"
            "- Don't ask multiple questions at once.\n"
            "- Keep it short and conversational — one sentence.\n"
            "- Acknowledge their issue briefly before asking (e.g. 'Got it!' or 'Ah, that can be tricky —')."
        ),
        user_prompt=f"User's issue: {text}",
        history=history,
        max_tokens=100,
        fast=True,
    )

    return clarifying_q or "Got it! Just to point you to the right fix — which Worksoft module is this in: CTM, Certify, or Portal?"


def _resolve(query: str, original_text: str, history: list) -> str:
    """Search cases and return a conversational answer. Used by both intake and direct paths."""
    matches = _retrieve_best_cases(query, top_n=1)

    if not matches:
        # ── General AI fallback ───────────────────────────────
        # No Salesforce case matched — use Groq's own Worksoft training knowledge
        # to still try to help before suggesting a ticket.
        general_reply = _ask_groq(
            system_prompt=(
                f"{_EXPERT_PERSONA}\n\n"
                "No specific resolved case was found in our internal knowledge base.\n\n"
                "Use your general Worksoft knowledge (CTM, Certify, Portal, Capture, "
                "agent machines, IIS, appsettings, services) to help.\n\n"
                "Response structure:\n"
                "- 1 line: briefly say this is from general knowledge, not a specific resolved case\n"
                "- **Numbered steps** — each on its own line with a brief reason:\n"
                "  1. **Action** — why this helps\n"
                "  2. **Action** — why this helps\n"
                "- End with: '📸 Share a screenshot of the error if it persists — "
                "or hit **❌ Still need help** to raise a ticket.'\n\n"
                "If you genuinely don't know, skip the steps and go straight to the ticket suggestion."
            ),
            user_prompt=f"User's issue: {query}",
            history=history,
            max_tokens=500,
        )
        if general_reply:
            # Store as resolution context so follow-up questions work
            st.session_state.sf_resolution   = general_reply
            st.session_state.sf_case_context  = query
            st.session_state.chat_phase        = "resolving"
        return general_reply or (
            "I couldn't find a match in our knowledge base and don't have enough info to help directly. "
            "Hit **❌ Still need help** to raise a ticket and the team will dig in."
        )

    best     = matches[0]
    case_num = (best.get("case_number") or "").strip()
    subject  = (best.get("subject")     or "").strip()
    comments = (best.get("comments")    or "").strip()
    desc     = (best.get("description") or "").strip()
    content  = comments or desc

    if not content:
        return _ask_groq(
            system_prompt=(
                f"{_EXPERT_PERSONA}\n\n"
                "You found a related case but it has no resolution notes yet. "
                "Acknowledge the issue empathetically, say the team hasn't documented a fix yet, "
                "and encourage them to raise a ticket. Keep it warm and brief."
            ),
            user_prompt=f"User's issue: {query}. Related case: {subject}",
            history=history,
            max_tokens=120,
        ) or (
            "I found a related case but there aren't resolution notes yet. "
            "Hit **❌ Still need help** to raise a ticket and the team will dig in."
        )

    st.session_state.sf_resolution   = content
    st.session_state.sf_case_context = f"Case #{case_num}: {subject}" if case_num else subject
    st.session_state.sf_steps        = []
    st.session_state.sf_step_idx     = 0
    st.session_state.chat_phase      = "resolving"

    reply = _ask_groq(
        system_prompt=(
            f"{_EXPERT_PERSONA}\n\n"
            "You have a resolved case that matches the user's issue. "
            "Understand it and present the fix in a clean structured format.\n\n"
            "Response structure:\n"
            "**1 line** — What's causing this (the 'why'), short and clear.\n"
            "**Numbered steps** — Each step on its own line. Format:\n"
            "  1. **Action** — brief reason why this step matters\n"
            "  2. **Action** — brief reason\n"
            "  (keep technical details exact: file paths, config keys, values)\n"
            "**Screenshot note** — End with ONE of these based on the issue:\n"
            "  - If a screenshot from the user would help diagnose further: "
            "'📸 If this doesn't resolve it, share a screenshot of the error and I can dig deeper.'\n"
            "  - If the steps are self-sufficient: "
            "'Give that a try and let me know how it goes!'\n\n"
            "Rules:\n"
            "- Never invent steps not in the case — but you can add brief 'why' context to each\n"
            "- No walls of text — keep each step tight and scannable\n"
            "- Don't mention Salesforce or case numbers\n\n"
            f"Case content:\n{content[:2000]}"
        ),
        user_prompt=f"User's issue: {query}",
        history=history,
        max_tokens=700,
    )

    if not reply:
        formatted = _format_case_content(content)
        reply = f"Here's what usually fixes this:\n\n{formatted}\n\nLet me know if any step needs clarification!"

    return reply


# ═══════════════════════════════════════════════════════════
# NAVBAR
# ═══════════════════════════════════════════════════════════
def render_navbar():
    user     = st.session_state.get("user")
    usr_pill = f'<span class="nav-user">👤 {user["name"]}</span>' if user else ""
    st.html(f"""
<div class="nav">
  <div class="nav-left">
    <div class="nav-logo">🤖</div>
    <div>
      <div class="nav-title">Worksoft AI Support</div>
      <div class="nav-sub">Qualesce · Groq AI · Salesforce</div>
    </div>
  </div>
  <div class="nav-right">
    {usr_pill}
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
    user = st.session_state.get("user")
    feats = "".join([
        f'<div class="lp-feature"><span style="font-size:14px;">{i}</span>{l}</div>'
        for i, l in [("🔍","Smart AI search"),("📎","File & screenshot"),
                     ("🎫","Auto ticket"),("📧","Admin notify")]
    ])
    user_html = (
        f'<div class="lp-user"><div class="lp-uname">👤 {user["name"]}</div>'
        f'<div class="lp-uemail">{user["email"]}</div></div>' if user else ""
    )

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
  {user_html}
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

    user  = st.session_state.get("user")

    # ── Two-column layout ───────────────────────────────────
    left_col, right_col = st.columns([1, 2.6], gap="large")
    _render_left_panel(left_col)

    with right_col:
      # ── Home / Identity form ──────────────────────────────
      if not st.session_state.user:
        st.markdown("""
<div class="login-card anim">
  <div class="login-banner">
    <div class="login-icon">🤖</div>
    <div class="login-title">Worksoft AI Support</div>
    <div class="login-sub">Instant help for CTM, Certify &amp; Portal — powered by Groq AI</div>
    <div class="login-chips">
      <span class="chip chip-white">🔍 Smart AI Search</span>
      <span class="chip chip-white">📎 Screenshots</span>
      <span class="chip chip-white">🎫 Auto Ticket</span>
    </div>
  </div>
  <div class="login-body">
  <div class="login-body-title">👋 Let's get started</div>
  <div class="login-body-sub">Enter your details and describe your issue — or attach a screenshot.</div>
""", unsafe_allow_html=True)

        st.markdown('<div class="home-upload">', unsafe_allow_html=True)
        home_file = st.file_uploader(
            "📸 Upload a screenshot of your issue (optional)",
            type=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
            key=f"home_fu_{st.session_state.fu_key}",
            help="Attach an error screenshot and the AI will analyze it",
        )
        st.markdown('</div>', unsafe_allow_html=True)

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
                placeholder="e.g. CTM agent not connecting after server restart…",
                height=90,
            )
            go = st.form_submit_button(
                "🚀  Start Chat",
                use_container_width=True,
                type="primary",
            )

        st.markdown('</div></div>', unsafe_allow_html=True)

        if go:
            if not name.strip() or not email.strip():
                st.error("Please enter your name and email to continue.")
            else:
                st.session_state.user = {"name": name.strip(), "email": email.strip()}
                sid = support_db.create_session(name.strip(), email.strip())
                st.session_state.session_id = sid
                first_content = issue_desc.strip() or ""
                file_data = _process_upload(home_file) if home_file else None
                welcome_reply = (
                    f"Hi **{name.strip()}**! 👋 I'm your Worksoft AI support agent.\n\n"
                    "Describe your issue — or attach a **screenshot, log file, or PDF** "
                    "using the 📎 icon and I'll analyze it."
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
                    _typing_slot = st.empty()
                    _typing_slot.html(_TYPING_HTML)
                    reply = groq_chat(first_content, st.session_state.messages, file_data)
                    _typing_slot.empty()
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    support_db.save_message(sid, "assistant", reply)
                    st.session_state.fu_key += 1
                st.rerun()
        return

      _live_chat()


@st.fragment
def _live_chat():
    """
    Fragment: only the chat panel reruns on each message — sidebar/navbar stay frozen.
    """
    user  = st.session_state.get("user")
    uname = user["name"] if user else ""

    # ── Chat window header ───────────────────────────────────
    st.html(f"""
<div class="cwin">
  <div class="chead">
    <div class="chead-left">
      <div class="chead-av">🤖</div>
      <div>
        <div class="chead-name">Qualesce AI Support{(" — " + uname) if uname else ""}</div>
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

    # ── Action buttons ───────────────────────────────────────
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "assistant" and len(msgs) >= 2:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;padding:6px 0 2px;">'
            '<span style="font-size:12px;color:#64748b;font-weight:600;margin-right:4px;">Was this helpful?</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        rc1, rc2, _ = st.columns([1.3, 1.5, 4])
        with rc1:
            if st.button("✅ Yes, resolved!", use_container_width=True, type="primary"):
                st.session_state.page = "resolved"
                st.rerun(scope="app")
        with rc2:
            if st.button("❌ Still need help", use_container_width=True):
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

        st.session_state.messages.append(user_msg)
        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_message(sid, "user", user_input.strip(), fname, ftype)

        _typing_slot = st.empty()
        _typing_slot.html(_TYPING_HTML)
        reply = groq_chat(user_input.strip(), st.session_state.messages, file_data)
        _typing_slot.empty()

        st.session_state.messages.append({"role": "assistant", "content": reply})
        if sid:
            support_db.save_message(sid, "assistant", reply)
        st.rerun()


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
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        if st.button("Start New Chat", use_container_width=True, type="primary"):
            sid = st.session_state.get("session_id")
            if sid:
                support_db.update_session_status(sid, "resolved")
            for k in ["messages","issue_text","sf_ticket","user","session_id"]:
                st.session_state[k] = [] if k=="messages" else ("" if k=="issue_text" else None)
            _reset_chat_state()
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
