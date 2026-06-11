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
    page_title="AI Support Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)
# Note: layout stays "wide" — we control width via .block-container CSS per page

# ═══════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── RESET ── */
[data-testid="stHeader"]{display:none!important;}
[data-testid="stSidebar"]{display:none!important;}
header,#MainMenu,footer,.stDeployButton,
[data-testid="stFooter"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"]{display:none!important;}
[data-testid="stMain"]>div{padding-top:0!important;}
html,body,[data-testid="stAppViewContainer"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important;
  background:#f0f2f5!important;
}

/* ── NAVBAR ── */
.chat-navbar{
  background:#fff;border-bottom:1px solid #e5e7eb;
  box-shadow:0 1px 8px rgba(0,0,0,.06);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 28px;height:60px;position:sticky;top:0;z-index:9000;
}
.cn-brand{display:flex;align-items:center;gap:10px;}
.cn-icon{
  width:36px;height:36px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#6366f1);
  display:flex;align-items:center;justify-content:center;
  font-size:17px;color:#fff;box-shadow:0 2px 8px rgba(37,99,235,.3);}
.cn-brand-info{display:flex;flex-direction:column;gap:1px;}
.cn-title{font-size:14px;font-weight:700;color:#111827;}
.cn-online{font-size:10px;color:#10b981;font-weight:600;
  display:flex;align-items:center;gap:4px;}
.cn-online::before{content:'';display:inline-block;width:6px;height:6px;
  border-radius:50%;background:#10b981;}
.cn-portal{
  font-size:12px;color:#2563eb;background:#eff6ff;
  border:1px solid #bfdbfe;border-radius:20px;
  padding:4px 14px;font-weight:600;
  position:absolute;left:50%;transform:translateX(-50%);}
.cn-user-wrap{display:flex;align-items:center;gap:10px;}
.cn-user-text{text-align:right;line-height:1.3;}
.cn-user-name{font-size:13px;font-weight:600;color:#111827;display:block;}
.cn-user-co{font-size:11px;color:#9ca3af;display:block;}
.cn-avatar{
  width:34px;height:34px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#6366f1);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-size:12px;font-weight:700;box-shadow:0 2px 6px rgba(37,99,235,.25);}

/* ── MESSAGES ── */
@keyframes msgIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes dotBounce{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-5px);opacity:1}}
.chat-msgs{
  padding:24px 0 16px;display:flex;flex-direction:column;
  gap:4px;max-width:1140px;margin:0 auto;
}
.date-stamp{
  text-align:center;font-size:11px;color:#9ca3af;margin-bottom:16px;
  font-weight:500;display:flex;align-items:center;gap:10px;
}
.date-stamp::before,.date-stamp::after{content:'';flex:1;height:1px;background:#e5e7eb;}
.msg-row{display:flex;align-items:flex-end;padding:2px 0;}
.msg-row.new{animation:msgIn .22s ease both;}

/* Bot */
.msg-row.assistant{flex-direction:row;gap:10px;padding:6px 0;align-items:flex-start;}
.msg-av{width:32px;height:32px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;}
.msg-av.bot{
  background:linear-gradient(135deg,#2563eb,#6366f1);color:#fff;
  box-shadow:0 2px 6px rgba(37,99,235,.22);}
.bot-text{
  background:#fff;border:1px solid #e5e7eb;
  border-radius:4px 18px 18px 18px;
  padding:12px 16px;max-width:78%;
  font-size:14.5px;line-height:1.75;color:#111827;
  word-break:break-word;
  box-shadow:0 1px 4px rgba(0,0,0,.05);}
.bot-text p{margin:0 0 6px;}.bot-text p:last-child{margin:0;}
.bot-text ol,.bot-text ul{margin:4px 0 6px 18px;padding:0;}
.bot-text li{margin:3px 0;line-height:1.65;}
.bot-text strong{font-weight:600;color:#1e40af;}
.bot-text code{background:#eff6ff;color:#1d4ed8;padding:1px 5px;border-radius:4px;font-size:13px;}

/* User */
.msg-row.user{flex-direction:row-reverse;padding:6px 0;align-items:flex-end;}
.user-bubble{
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  color:#fff;border-radius:18px 4px 18px 18px;
  padding:12px 16px;font-size:14.5px;line-height:1.65;
  max-width:72%;word-break:break-word;
  box-shadow:0 3px 12px rgba(37,99,235,.28);}
.user-bubble p{margin:0;}

/* ── TYPING ── */
.typing-row{display:flex;gap:10px;align-items:flex-start;padding:6px 0;animation:msgIn .2s ease both;}
.typing-av{width:32px;height:32px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#2563eb,#6366f1);color:#fff;
  font-size:13px;font-weight:700;display:flex;align-items:center;
  justify-content:center;box-shadow:0 2px 6px rgba(37,99,235,.22);}
.typing-bubble{
  background:#fff;border:1px solid #e5e7eb;
  border-radius:4px 18px 18px 18px;
  padding:14px 18px;box-shadow:0 1px 4px rgba(0,0,0,.05);}
.typing-dots{display:flex;gap:5px;align-items:center;}
.typing-dot{width:7px;height:7px;border-radius:50%;background:#93c5fd;
  animation:dotBounce 1.2s infinite ease-in-out;}
.typing-dot:nth-child(2){animation-delay:.15s;}
.typing-dot:nth-child(3){animation-delay:.3s;}

/* ── FEEDBACK CARD ── */
.fb-card{max-width:1140px;margin:8px auto;background:#fff;
  border:1px solid #e5e7eb;border-radius:14px;
  padding:12px 18px;display:flex;align-items:center;gap:10px;
  box-shadow:0 2px 8px rgba(0,0,0,.05);}
.fb-text{font-size:13px;font-weight:600;color:#374151;flex:1;}

/* ── UPLOAD CARD ── */
.uc-card{max-width:1140px;margin:6px auto 0;background:#fff;
  border:1.5px dashed #93c5fd;border-radius:14px;
  padding:12px 18px;display:flex;align-items:center;gap:10px;}
.uc-icon{width:32px;height:32px;background:#eff6ff;border-radius:8px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:15px;}
.uc-title{font-size:13px;font-weight:600;color:#1e40af;}
.uc-sub{font-size:11px;color:#9ca3af;margin-top:1px;}

/* ── FILE UPLOADER ── */
div[data-testid="stFileUploader"]>label{display:none!important;}
section[data-testid="stFileUploaderDropzone"]{border:none!important;background:transparent!important;
  min-height:36px!important;max-height:40px!important;padding:0!important;
  display:flex!important;align-items:center!important;justify-content:flex-end!important;}
section[data-testid="stFileUploaderDropzone"]>div{
  width:auto!important;flex-direction:row!important;justify-content:flex-end!important;gap:0!important;}
section[data-testid="stFileUploaderDropzone"]>div>div:first-child{display:none!important;}
section[data-testid="stFileUploaderDropzone"] button{
  background:#fff!important;border:1.5px solid #c7d2fe!important;border-radius:8px!important;
  color:#2563eb!important;font-size:12px!important;font-weight:600!important;
  padding:4px 14px!important;width:auto!important;height:30px!important;
  min-height:0!important;box-shadow:none!important;}
section[data-testid="stFileUploaderDropzone"] button::before{content:"📎  ";}
div[data-testid="stFileUploader"] small{display:none!important;}
[data-testid="stFileUploaderFile"]{font-size:11px!important;}

/* ── SUPPORT LEVEL ROW ── */
.support-level-row{display:flex;align-items:center;gap:8px;padding:6px 0 2px;max-width:860px;margin:0 auto;}
.support-level-label{font-size:11px;color:#9ca3af;font-weight:600;white-space:nowrap;}

/* ── TICKET CARD ── */
.ticket-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;
  box-shadow:0 4px 16px rgba(0,0,0,.07);padding:18px 22px;margin:12px auto;max-width:520px;}
.ticket-id{font-size:10px;font-weight:700;color:#2563eb;letter-spacing:.8px;text-transform:uppercase;}
.ticket-num{font-size:22px;font-weight:800;color:#111827;margin:3px 0 12px;}
.ticket-row{display:flex;gap:8px;align-items:flex-start;margin-bottom:5px;font-size:12.5px;}
.ticket-lbl{color:#9ca3af;min-width:68px;flex-shrink:0;}
.ticket-val{color:#111827;font-weight:600;word-break:break-all;}
.ticket-link{display:inline-flex;align-items:center;gap:6px;margin-top:12px;
  background:linear-gradient(135deg,#2563eb,#3b82f6);
  color:#fff!important;text-decoration:none;font-size:12.5px;font-weight:600;
  padding:8px 18px;border-radius:9px;box-shadow:0 3px 10px rgba(37,99,235,.28);}
.badge-new{display:inline-block;background:#eff6ff;color:#2563eb;font-size:9px;font-weight:700;
  padding:2px 8px;border-radius:99px;text-transform:uppercase;letter-spacing:.4px;}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.anim{animation:fadeUp .28s ease both;}
@keyframes scaleIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}
.anim-scale{animation:scaleIn .24s ease both;}

/* ── PRIMARY BUTTON ── */
div.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#2563eb,#3b82f6)!important;color:#fff!important;
  border-radius:9px!important;border:none!important;font-weight:600!important;
  box-shadow:0 2px 8px rgba(37,99,235,.25)!important;}
div.stButton>button[kind="primary"]:hover{background:linear-gradient(135deg,#1d4ed8,#2563eb)!important;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════
def initials(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "U"
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][0].upper()


def _init_state():
    defaults = {
        "page":                    "intro",
        "user":                    {"name": "Guest", "email": ""},
        "company":                 "",
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
        # frontend state
        "show_upload":             False,
        "waiting_feedback":        False,
        "input_key":               0,
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
_GROQ_MODEL        = "llama-3.3-70b-versatile"  # primary — fast + capable
_GROQ_REASON_MODEL = "llama-3.3-70b-versatile"  # Phase 3 deep turns — same model + richer prompt
_GROQ_FAST_MODEL   = "llama-3.1-8b-instant"     # tiny calls (classification, 1-word answers)
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
    "You are a warm, friendly, and highly experienced Worksoft support specialist at Qualesce. "
    "Think of yourself as a patient and caring colleague sitting right next to the user — someone who genuinely "
    "wants to understand their problem before jumping to solutions. "
    "\n\nYOUR PERSONALITY:\n"
    "- Empathetic: always acknowledge how the user feels before diving into details. "
    "  E.g. 'That sounds really frustrating — let me help you sort this out.' "
    "- Curious: ask thoughtful follow-up questions to understand the full picture. "
    "  Never assume — always verify. "
    "- Encouraging: celebrate small wins ('Great, that's useful info!'), reassure when things are unclear. "
    "- Natural: use contractions (I've, you'll, let's, that's), vary your openers, never sound scripted. "
    "- Concise but human: no filler ('Great question!'), no walls of text — conversational paragraphs. "
    "\n\nYOUR APPROACH:\n"
    "- First understand, then solve. Never rush to give steps before you know what's really happening. "
    "- When you do give steps, walk the user through them like a friend would — explain each step in plain English. "
    "- After every response that includes steps, invite the user to tell you what happened. "
    "- If the user seems confused or frustrated, slow down, simplify, and show extra care. "
    "- Use the user's own words when reflecting the problem back to them — it builds trust. "
    "\n\nYou have deep expertise in Worksoft CTM, Certify, Portal, Capture, agent machines, IIS, and appsettings. "
    "When Salesforce case data is available, use it as your ground truth. "
    "When it's not, troubleshoot confidently from your domain knowledge."
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
    system_prompt:  str,
    user_prompt:    str,
    max_tokens:     int   = 800,
    history:        list  = None,
    fast:           bool  = False,
    stream:         bool  = False,
    temperature:    float = 0.3,
    model_override: str   = None,
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
        model  = model_override or (_GROQ_FAST_MODEL if fast else _GROQ_MODEL)

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            # Exclude the last message if it's a user message — it's added as user_prompt below
            hist = history[-20:]
            for i, msg in enumerate(hist):
                role    = msg.get("role", "")
                content = msg.get("content", "")
                # Skip the last entry if it duplicates the current user_prompt
                if i == len(hist) - 1 and role == "user" and content.strip() == user_prompt.strip():
                    continue
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)[:2000]})
        messages.append({"role": "user", "content": user_prompt})

        stream_slot = st.session_state.get("_stream_slot") if stream else None

        if stream_slot is not None:
            full           = ""    # content shown to the user
            think_buf      = ""    # raw buffer until <think>...</think> closes
            think_closed   = False # True once we know the <think> block (or its absence) is resolved
            typing_cleared = False
            completion = client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=effective_temp, stream=True,
            )
            for chunk in completion:
                delta = chunk.choices[0].delta.content or ""
                if not think_closed:
                    think_buf += delta
                    if "</think>" in think_buf:
                        # DeepSeek R1 reasoning block closed — display only what follows
                        after = think_buf.split("</think>", 1)[-1].lstrip("\n")
                        full = after
                        think_closed = True
                    elif "<think>" not in think_buf and len(think_buf) > 60:
                        # No <think> tag in first 60 chars — normal model, emit everything
                        full = think_buf
                        think_closed = True
                else:
                    full += delta
                if full:
                    if not typing_cleared:
                        typing = st.session_state.pop("_typing_slot", None)
                        if typing:
                            typing.empty()
                        typing_cleared = True
                    stream_slot.markdown(full + " ▌")
            if full:
                stream_slot.markdown(full)
            return full

        completion = client.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=effective_temp,
        )
        raw = (completion.choices[0].message.content or "").strip()
        # Strip DeepSeek R1 internal reasoning block when present
        if "<think>" in raw and "</think>" in raw:
            raw = raw.split("</think>", 1)[-1].strip()
        return raw
    except Exception as e:
        import traceback
        _err = str(e)
        print(f"[Groq error] {_err}\n{traceback.format_exc()}")
        # Store the real error so the UI can surface it
        try:
            st.session_state["_last_ai_error"] = _err
        except Exception:
            pass
        return _ask_claude_fallback(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature)


def _ai_connection_error() -> str:
    """Return a friendly error message that includes the real API error when available."""
    last = st.session_state.get("_last_ai_error", "")
    hint = ""
    if last:
        low = last.lower()
        if "401" in last or "invalid_api_key" in low or "authentication" in low:
            hint = "\n\n🔑 **Cause:** Invalid or expired API key."
        elif "429" in last or "rate_limit" in low or "rate limit" in low:
            hint = "\n\n⏱️ **Cause:** Rate limit reached — wait a moment and try again."
        elif "connection" in low or "timeout" in low or "network" in low:
            hint = "\n\n🌐 **Cause:** Network / connection error — check your internet."
        elif "model" in low and ("not found" in low or "does not exist" in low):
            hint = f"\n\n🤖 **Cause:** Model not found. Check `_GROQ_MODEL` in the code.\n`{last}`"
        else:
            hint = f"\n\n⚠️ **Error:** `{last}`"
    return (
        "❌ **I'm having trouble connecting to the AI right now.**"
        + hint
        + "\n\n**Fix:** Open `.streamlit/secrets.toml`, verify your `GROQ_API_KEY` is correct, then restart the app.\n"
        "Get a free key at [console.groq.com](https://console.groq.com)."
    )


def _ask_ai(system_prompt: str, user_prompt: str, max_tokens: int = 800,
            history: list = None, fast: bool = False, stream: bool = False,
            temperature: float = 0.3, model_override: str = None) -> str:
    """Single entry-point for all AI calls — routes through Groq."""
    return _ask_groq(system_prompt, user_prompt, max_tokens, history, fast, stream, temperature,
                     model_override=model_override)


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
    st.session_state.waiting_feedback       = False
    st.session_state.turn_count             = 0
    st.session_state.show_upload            = False
    st.session_state.input_key              = st.session_state.get("input_key", 0) + 1


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
<div class="typing-row" style="max-width:1200px;margin:0 auto;">
  <div class="typing-av">W</div>
  <div class="typing-bubble">
    <div class="typing-dots">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  </div>
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
            f"Pick the best 1-{top_n} cases whose content genuinely answers the user's question. "
            "Prefer cases with the most detailed resolution steps or comments. "
            "Return ONLY position numbers, e.g. '2' or '1, 3, 5'. "
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
    # In deeper turns the current message is often too short ("still not working") to be a
    # useful retrieval signal on its own. Combine last 4 user messages so we find the right
    # SF cases even when the follow-up lacks the original issue description.
    _prior_user_msgs = [m["content"] for m in history if m.get("role") == "user"]
    if len(_prior_user_msgs) >= 2:
        _combined = " | ".join(_prior_user_msgs[-4:])
        if text.strip().lower() not in _combined.lower():
            _combined = text + " | " + _combined
        _rich_query = _combined[:800]
    else:
        _rich_query = query
    matches = _retrieve_best_cases(_rich_query, top_n=5) if (_rich_query or query).strip() else []
    knowledge_text, has_content, ctx_summary = (
        _build_case_knowledge(matches, query) if matches else ("", False, "")
    )
    if has_content:
        st.session_state.sf_resolution   = knowledge_text[:6000]
        st.session_state.sf_case_context = ctx_summary

    sf_res = st.session_state.get("sf_resolution", "")

    # ── Build system prompt ────────────────────────────────────
    sf_section = ""
    if has_content:
        sf_section = (
            "\n\n=== SALESFORCE RESOLVED CASES — YOUR PRIMARY ANSWER SOURCE ===\n"
            "These are real tickets resolved by Qualesce Worksoft support engineers.\n"
            "RULES FOR USING THIS DATA:\n"
            "  • If resolution steps exist here → reproduce them exactly as the basis of your answer.\n"
            "  • Do NOT skip, reorder, or contradict any step that appears in these cases.\n"
            "  • You may add a one-line 'why' to help the user understand a step, but keep the steps intact.\n"
            "  • If multiple cases are present, pick the one whose problem description best matches the user's query.\n\n"
            + knowledge_text
            + "\n=== END OF SALESFORCE DATA ===\n"
        )
    elif sf_res:
        sf_section = (
            "\n\n=== SALESFORCE RESOLVED CASES (retrieved earlier in this conversation) ===\n"
            "Apply the resolution steps below if they remain relevant to the current message.\n\n"
            + sf_res[:4000]
            + "\n=== END OF SALESFORCE DATA ===\n"
        )

    # Determine how many user turns have happened so far
    user_turn = sum(1 for m in history if m.get("role") == "user")
    st.session_state.turn_count = user_turn

    # 3-phase conversation flow
    if user_turn <= 1:
        # ── PHASE 1: Understand the problem first, always ──────────────────────
        conversation_style = """
=== PHASE 1 — UNDERSTAND THE PROBLEM ===
This is the user's FIRST message. Your ONLY job right now is to understand their situation
before offering any solution. Even if they've given some details, there's always more to learn.

YOUR RESPONSE MUST:
1. Open with a warm, empathetic 1-sentence acknowledgment of what they described.
   Examples: "Oh no, that sounds really frustrating — let's figure this out together!"
             "I can see why that would be annoying, especially mid-work."
             "Thanks for reaching out — I'm on it!"

2. Then ask 2–3 specific, focused questions as a short bullet list. Choose from:
   • Which exact Worksoft product? (CTM / Certify / Portal / Capture) — SKIP if already stated.
   • What's the exact error message or what unexpected thing is happening on screen?
   • When did this start — was anything changed or updated recently?
   • What have you already tried to fix it?
   • Which environment — Production, UAT, or Dev?
   • Are other users affected or just you?

   Pick the questions most relevant to what they described. Don't ask what they already answered.

3. End with a warm, encouraging closer like:
   "Once I have those details I can dig into this properly for you 🙂"
   "The more detail you share, the faster we can sort this!"

HARD RULES FOR PHASE 1:
- Do NOT give any troubleshooting steps, fixes, or solutions.
- Do NOT jump ahead — gathering context now leads to a much better answer.
- Keep it conversational and light, not like a form or ticket system.
"""

    elif user_turn == 2:
        # ── PHASE 2: Acknowledge their answers, confirm understanding, then start solving ──
        conversation_style = """
=== PHASE 2 — ACKNOWLEDGE AND BEGIN SOLVING ===
The user has now answered your questions. Show them you've listened, then move into solving.

YOUR RESPONSE MUST:
1. Briefly reflect back what you now understand about their issue (1-2 sentences).
   E.g. "Okay, so it sounds like [their issue] started [when] and you've already tried [X]."
   This shows you were paying attention and builds trust.

2. If you have a strong match in the SALESFORCE CASE DATA above — begin walking them
   through the resolution steps now. Introduce it naturally:
   E.g. "I've seen this before — here's what usually fixes it:"
        "Good news, this is a known issue and there's a clear fix:"

3. If you need one more critical piece of info before you can solve it, ask that ONE question
   now — but only if it's truly essential. Don't fish for more info if you can already help.

4. Structure your steps conversationally:
   - 1 sentence on the likely cause
   - Numbered steps: "1. **Do X** — here's why this helps"
   - After the last step: "Give those a try and let me know what happens! 👇"

HARD RULES:
- Do NOT ask multiple questions here — one at most.
- Use Salesforce case data as your primary source for steps.
- NEVER mention Salesforce, case IDs, or database names.
"""

    else:
        # ── PHASE 3: Full solution mode with deep reasoning ────────────────────
        conversation_style = """
=== PHASE 3 — DEEP TROUBLESHOOTING ===
You are now in active troubleshooting. Think carefully before you answer.

BEFORE WRITING YOUR RESPONSE, REASON THROUGH:
1. What is the EXACT root cause based on the FULL conversation history (not just the latest message)?
2. What has the user already tried? Did those steps succeed, fail, or partially work?
3. Which Salesforce case (if any) matches this situation most precisely — and why?
4. What is the single most important next action that has NOT been tried yet?

HOW TO CONSTRUCT YOUR ANSWER:
1. SALESFORCE DATA FIRST — If the Salesforce case data above matches the user's issue,
   build your entire answer around those exact resolution steps. Quote them faithfully.
   Do NOT skip, reorder, or contradict any step from the case.

2. FILL GAPS — If the case is partially relevant, use your Worksoft expertise to fill
   what's missing. Make it seamless — the user shouldn't notice the join.

3. NO CASE MATCH — Answer confidently from your deep Worksoft domain knowledge.

ANSWER FORMAT:
- Acknowledge what the user just said in 1 sentence (especially if they tried something).
- 1 sentence naming the likely root cause.
- Numbered steps: "1. **Do X** — (plain-English reason)"
- Close with something warm:
  "Try those and let me know what happens — I'm right here! 👇"
  "Give step 2 especially a go and tell me what you see."
  "If that doesn't crack it, we'll dig deeper together!"

HARD RULES:
- Use ALL conversation history to understand the full context — never treat a short
  follow-up message in isolation.
- NEVER mention Salesforce, case IDs, case numbers, or any internal system name.
- NEVER invent steps that contradict the SF case data.
- NEVER give a cold, robotic or generic answer — always sound like a caring colleague.
- If user says it worked → celebrate warmly and suggest ✅ Resolved at L1.
- If user is still stuck → empathise, ask what happened at each step, try a different angle.
"""

    # Prompt order matters: SF data + rules go LAST so the model weights them highest.
    system_prompt = (
        f"{_EXPERT_PERSONA}\n\n"
        f"{_WORKSOFT_DOMAIN}\n"
        + sf_section
        + "\n"
        + conversation_style
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

    # Phase 3+ uses the reasoning model (DeepSeek R1) for deeper chain-of-thought accuracy.
    # Phase 1-2 use the standard fast model since they just gather details / begin solving.
    _model = _GROQ_REASON_MODEL if user_turn >= 3 else None

    reply = _ask_ai(
        system_prompt=system_prompt,
        user_prompt=query,
        history=history,
        max_tokens=1400,
        stream=True,
        temperature=0.15,
        model_override=_model,
    ) or _ai_connection_error()

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
            parts.append(f"Problem description:\n{desc[:1500]}")
        if resolution:
            parts.append(f"Resolution summary:\n{resolution[:1500]}")
        if comments:
            parts.append(f"Detailed steps/comments:\n{comments[:3500]}")

        if len(parts) > 1:   # must have more than just the subject
            blocks.append(f"── Knowledge Entry {i} ──\n" + "\n\n".join(parts))

    knowledge_text  = "\n\n".join(blocks) if blocks else ""
    has_content     = bool(blocks)
    context_summary = "; ".join(all_subjects[:3]) if all_subjects else query
    return knowledge_text, has_content, context_summary


# ═══════════════════════════════════════════════════════════
# PAGE: CHAT
# ═══════════════════════════════════════════════════════════
def render_chat():
    st.markdown("""
<style>
/* ══ FLEX LAYOUT — chatbar stays at bottom via flexbox, no position:fixed fighting ══ */
/* Full height chain: every ancestor must be 100vh or the flex container won't fill the viewport */
html,body,#root,.stApp,[data-testid="stApp"]{
  height:100vh!important;margin:0!important;padding:0!important;overflow:hidden!important;
}

/* The root flex column: stMain grows to fill space, chatbar sits at bottom as a natural flex item */
[data-testid="stAppViewContainer"]{
  display:flex!important;flex-direction:column!important;
  height:100vh!important;min-height:100vh!important;
  overflow:hidden!important;background:#f0f2f5!important;
}

/* ══ NAVBAR — sticky within stMain scroll ══ */
.chat-navbar{
  position:sticky!important;top:0!important;z-index:9000!important;
  background:#fff!important;border-bottom:1px solid #e5e7eb!important;
  box-shadow:0 1px 8px rgba(0,0,0,.06)!important;
  /* no left/right/width needed — sticky stays in flow */
}

/* ══ MESSAGES — fills all available space, scrolls internally ══ */
[data-testid="stMain"]{
  flex:1 1 0!important;min-height:0!important;
  overflow-y:auto!important;overflow-x:hidden!important;
  background:#f0f2f5!important;
}
[data-testid="stMain"]::-webkit-scrollbar{width:5px;}
[data-testid="stMain"]::-webkit-scrollbar-track{background:transparent;}
[data-testid="stMain"]::-webkit-scrollbar-thumb{background:#c7d2fe;border-radius:10px;}
[data-testid="stMainBlockContainer"],
[data-testid="stMain"]>div{height:auto!important;min-height:unset!important;overflow:visible!important;}
.block-container{
  background:transparent!important;box-shadow:none!important;border-radius:0!important;
  max-width:1200px!important;margin:0 auto!important;
  padding:20px 24px 16px!important;overflow:visible!important;
}

/* ══ CHATBAR WRAPPER — glassmorphism floating bar ══ */
[data-testid="stBottomBlockContainer"]{
  flex:0 0 auto!important;width:100%!important;
  position:relative!important;bottom:auto!important;
  transform:none!important;will-change:auto!important;
  /* frosted glass overcoat */
  background:rgba(255,255,255,0.72)!important;
  backdrop-filter:blur(18px) saturate(180%)!important;
  -webkit-backdrop-filter:blur(18px) saturate(180%)!important;
  border-top:1px solid rgba(99,102,241,0.12)!important;
  box-shadow:0 -8px 32px rgba(37,99,235,.09),0 -1px 0 rgba(99,102,241,.10)!important;
  padding:10px 16px 12px!important;box-sizing:border-box!important;
  z-index:100!important;overflow:hidden!important;
}
[data-testid="stBottomBlockContainer"] *::-webkit-scrollbar{display:none!important;width:0!important;}
[data-testid="stBottomBlockContainer"] *{scrollbar-width:none!important;}

/* Hide clutter */
[data-testid="stChatInputHint"],[data-testid="stFooter"],[data-testid="stDecoration"],
[data-testid="stStatusWidget"],footer,
[data-testid="stBottomBlockContainer"] p,
[data-testid="stBottomBlockContainer"] small{display:none!important;}

/* ══ INPUT BOX — compact glass pill ══ */
[data-testid="stChatInput"]{
  background:rgba(255,255,255,0.90)!important;
  border:1.5px solid rgba(99,102,241,0.22)!important;
  border-radius:999px!important;
  box-shadow:0 2px 12px rgba(37,99,235,.08),inset 0 1px 0 rgba(255,255,255,.9)!important;
  width:98%!important;max-width:98%!important;margin:0 auto!important;
  padding:12px 52px 12px 46px!important;min-height:58px!important;
  animation:none!important;position:relative!important;
  transition:border-color .2s,box-shadow .2s,background .2s!important;
  display:flex!important;align-items:center!important;
}
[data-testid="stChatInput"]:focus-within{
  background:rgba(255,255,255,1)!important;
  border-color:#6366f1!important;
  box-shadow:0 2px 16px rgba(99,102,241,.18),0 0 0 3px rgba(99,102,241,.10)!important;
}
[data-testid="stChatInput"] textarea{
  background:transparent!important;border:none!important;outline:none!important;
  box-shadow:none!important;font-size:14.5px!important;color:#1e293b!important;
  resize:none!important;min-height:42px!important;max-height:140px!important;
  padding:0!important;line-height:1.6!important;height:42px!important;
  font-weight:400!important;letter-spacing:.01em!important;
}
[data-testid="stChatInput"] textarea::placeholder{
  color:#94a3b8!important;font-size:14.5px!important;
}

/* ══ SEND BUTTON — compact glowing circle ══ */
[data-testid="stChatInputSubmitButton"]{
  background:linear-gradient(135deg,#4f46e5,#2563eb)!important;
  border-radius:50%!important;color:#fff!important;border:none!important;
  width:34px!important;height:34px!important;min-width:34px!important;padding:0!important;
  display:flex!important;align-items:center!important;justify-content:center!important;
  transition:transform .15s,box-shadow .15s!important;flex-shrink:0!important;
  box-shadow:0 2px 10px rgba(79,70,229,.45)!important;
}
[data-testid="stChatInputSubmitButton"]:hover{
  transform:scale(1.10)!important;
  box-shadow:0 4px 16px rgba(79,70,229,.60)!important;
}
[data-testid="stChatInputSubmitButton"]:active{transform:scale(.94)!important;}
[data-testid="stChatInputSubmitButton"]:disabled{
  background:#e2e8f0!important;color:#94a3b8!important;
  box-shadow:none!important;transform:none!important;
}

/* Hide native attach toggle */
button[key="toggle_upload_btn"],
[data-testid="stButton"]:has(button[key="toggle_upload_btn"]){display:none!important;}

/* In-chat buttons */
div.stButton>button{
  background:#fff!important;color:#2563eb!important;
  border:1.5px solid #e0e7ff!important;border-radius:9px!important;
  font-size:12px!important;font-weight:500!important;
  padding:5px 12px!important;min-height:0!important;height:auto!important;
  box-shadow:0 1px 3px rgba(0,0,0,.05)!important;
}
div.stButton>button:hover{background:#eff6ff!important;border-color:#93c5fd!important;}
div.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#2563eb,#3b82f6)!important;color:#fff!important;
  border:none!important;border-radius:9px!important;font-weight:600!important;
  box-shadow:0 2px 8px rgba(37,99,235,.25)!important;
}
div.stButton>button[kind="primary"]:hover{opacity:.9!important;}
</style>
""", unsafe_allow_html=True)

    _uname   = st.session_state.get("user", {}).get("name", "User")
    _company = st.session_state.get("company", "")
    _nav_init = initials(_uname)
    st.markdown(f"""
<div class="chat-navbar">
  <div class="cn-brand">
    <div class="cn-icon">🤖</div>
    <div class="cn-brand-info">
      <span class="cn-title">AI Support Assistant</span>
      <span class="cn-online">Online</span>
    </div>
  </div>
  <span class="cn-portal">Support Portal</span>
  <div class="cn-user-wrap">
    <div class="cn-user-text">
      <span class="cn-user-name">{_uname}</span>
      <span class="cn-user-co">{_company}</span>
    </div>
    <div class="cn-avatar">{_nav_init}</div>
  </div>
</div>
""", unsafe_allow_html=True)
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


def _build_messages_html(messages, user_initials, date_str):
    import html as _h

    def _md(text):
        lines = text.split('\n')
        out = []; in_ol = False; in_ul = False
        def flush():
            nonlocal in_ol, in_ul
            if in_ol: out.append('</ol>'); in_ol = False
            if in_ul: out.append('</ul>'); in_ul = False
        for line in lines:
            esc = _h.escape(line)
            esc = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', esc)
            m_n = re.match(r'^(\d+)\.\s+(.*)', esc)
            m_b = re.match(r'^[-•*]\s+(.*)', esc)
            if m_n:
                if not in_ol: flush(); out.append('<ol style="margin:6px 0 6px 18px;padding:0;">'); in_ol = True
                out.append(f'<li style="margin:3px 0;">{m_n.group(2)}</li>')
            elif m_b:
                if not in_ul: flush(); out.append('<ul style="margin:6px 0 6px 18px;padding:0;">'); in_ul = True
                out.append(f'<li style="margin:3px 0;">{m_b.group(1)}</li>')
            elif not esc.strip():
                flush()
            else:
                flush(); out.append(f'<p style="margin:0 0 5px;">{esc}</p>')
        flush()
        return ''.join(out)

    rows = [f'<div class="date-stamp">{date_str}</div>']
    last_idx = len(messages) - 1
    for i, msg in enumerate(messages):
        new_cls = " new" if i == last_idx else ""
        if msg["role"] == "assistant":
            rows.append(f'''
<div class="msg-row assistant{new_cls}">
  <div class="msg-av bot">W</div>
  <div class="bot-text">{_md(msg["content"])}</div>
</div>''')
        else:
            rows.append(f'''
<div class="msg-row user{new_cls}">
  <div class="user-bubble"><p style="margin:0;">{_h.escape(msg["content"])}</p></div>
</div>''')
    return f'<div class="chat-msgs">{"".join(rows)}</div>'


@st.fragment
def _live_chat():
    import streamlit.components.v1 as _cmp
    from datetime import datetime

    if "show_upload" not in st.session_state:
        st.session_state.show_upload = False

    # Auto-welcome on very first load
    if not st.session_state.get("chat_started"):
        st.session_state.chat_started = True
        _first_name = (st.session_state.get("user", {}).get("name") or "there").split()[0]
        welcome = (
            f"Hello, **{_first_name}**! 👋 I'm your **AI Support Assistant**. "
            f"How can I help you today? You can ask me about troubleshooting, "
            "account issues, or anything else."
        )
        st.session_state.messages.append({"role": "assistant", "content": welcome})

    msgs = st.session_state.messages

    # ── 1. PAST MESSAGES ────────────────────────────────────────
    _uname    = st.session_state.get("user", {}).get("name", "User")
    _initials = initials(_uname)
    _now      = datetime.now().strftime("Today, %I:%M %p").lstrip("0")
    st.markdown(_build_messages_html(msgs, _initials, _now), unsafe_allow_html=True)

    # Inline images attached to messages
    for msg in msgs:
        fdata = msg.get("file")
        if fdata and fdata["type"] == "image":
            st.image(
                f"data:{fdata['mime']};base64,{fdata['base64']}",
                caption=fdata["name"], width=260,
            )

    # ── 2. TYPING / STREAM SLOTS — declared HERE so they sit above the chatbar ──
    # Streamlit assigns render positions at declaration time, not at population time.
    # Declaring these before st.chat_input() guarantees they render inside the
    # scrollable messages area, not inside the bottom bar.
    _typing_slot = st.empty()
    _stream_slot = st.empty()
    st.session_state["_typing_slot"] = _typing_slot
    st.session_state["_stream_slot"] = _stream_slot

    # ── 3. RESOLUTION POPUP ─────────────────────────────────────
    if msgs and msgs[-1]["role"] == "assistant" and len(msgs) >= 2:
        if st.session_state.get("show_resolution_popup") and not st.session_state.get("resolution_check_shown"):
            _show_resolution_dialog()

    # ── 4. FEEDBACK CARD ────────────────────────────────────────
    if st.session_state.get("waiting_feedback") and msgs and msgs[-1]["role"] == "assistant":
        st.markdown("""
<div class="fb-card">
  <span class="fb-text">Did this resolve your issue?</span>
</div>""", unsafe_allow_html=True)
        fc1, fc2, _ = st.columns([1, 1.2, 5])
        with fc1:
            if st.button("✅ Resolved", key="btn_fb_resolved"):
                st.session_state.waiting_feedback = False
                st.session_state.resolution_check_shown = True
                st.session_state.page = "resolved"
                st.rerun(scope="app")
        with fc2:
            if st.button("❌ Not Resolved", key="btn_fb_not"):
                st.session_state.waiting_feedback = False
                st.session_state.resolution_check_shown = True
                st.session_state.page = "escalated"
                st.rerun(scope="app")

    # ── 5. UPLOAD CARD ──────────────────────────────────────────
    uploaded = None
    if st.session_state.show_upload:
        st.markdown("""
<div class="uc-card">
  <div class="uc-icon">⬆️</div>
  <div class="uc-text">
    <div class="uc-title">Upload screenshot or error log</div>
    <div class="uc-sub">Drag &amp; drop, or click to browse — PNG, JPG, PDF, TXT</div>
  </div>
</div>""", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Browse",
            type=["png","jpg","jpeg","gif","webp","pdf","txt","log","csv","xml"],
            key=f"fu_{st.session_state.fu_key}",
        )

    # Minimal attachment toggle — just a small icon link, not a full button
    _toggle_icon = "📎 Hide attachment" if st.session_state.show_upload else "📎 Attach file"
    st.markdown(
        f'<div style="text-align:right;max-width:1140px;margin:2px auto 0;padding-right:4px;">'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button(_toggle_icon, key="toggle_upload_btn"):
        st.session_state.show_upload = not st.session_state.show_upload
        st.rerun()

    # ── 6. FLEX ENFORCEMENT + PAPERCLIP + AUTO-SCROLL ───────────
    _cmp.html("""
<script>
(function(){
  var w = window.parent;
  var p = w.document;

  function pin(el, props){
    if(!el) return;
    for(var k in props) el.style.setProperty(k, props[k], 'important');
  }

  /* Enforce the flex-column layout.
     Every ancestor of stAppViewContainer must be height:100vh — if any shrinks,
     the flex container won't fill the viewport and the chatbar drifts up.
     stMain grows to fill all remaining space (flex:1 1 0).
     stBottomBlockContainer is a natural flex item at the bottom — it CANNOT move. */
  function applyFlex(){
    var html = p.documentElement;
    var body = p.body;
    var root = p.getElementById('root');
    var app  = p.querySelector('.stApp') || p.querySelector('[data-testid="stApp"]');
    var avc  = p.querySelector('[data-testid="stAppViewContainer"]');
    var main = p.querySelector('[data-testid="stMain"]');
    var mbc  = p.querySelector('[data-testid="stMainBlockContainer"]');
    var foot = p.querySelector('[data-testid="stBottomBlockContainer"]');

    // Full height chain — every ancestor must be 100vh
    [html, body, root, app].forEach(function(el){
      pin(el,{height:'100vh',overflow:'hidden',margin:'0',padding:'0'});
    });
    if(avc) pin(avc,{
      display:'flex','flex-direction':'column',
      height:'100vh','min-height':'100vh',overflow:'hidden'
    });
    if(main) pin(main,{
      flex:'1 1 0','min-height':'0',
      'overflow-y':'auto','overflow-x':'hidden'
    });
    if(mbc) pin(mbc,{overflow:'visible','min-height':'unset'});
    if(foot) pin(foot,{
      flex:'0 0 auto',width:'100%',
      position:'relative',bottom:'auto',
      transform:'none','will-change':'auto','z-index':'100'
    });
  }

  function injectClip(){
    var inp = p.querySelector('[data-testid="stChatInput"]');
    if(!inp || p.getElementById('wsa-clip')) return;
    var clip = p.createElement('button');
    clip.id = 'wsa-clip';
    clip.title = 'Attach file';
    clip.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"'+
      ' stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+
      '<path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66'+
      'l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/></svg>';
    clip.style.cssText='position:absolute;left:12px;top:50%;transform:translateY(-50%);'+
      'background:none;border:none;cursor:pointer;padding:6px;border-radius:8px;'+
      'color:#9ca3af;display:flex;align-items:center;justify-content:center;'+
      'transition:color .15s,background .15s;z-index:10;line-height:0';
    clip.onmouseover=function(){this.style.color='#2563eb';this.style.background='rgba(37,99,235,.08)';};
    clip.onmouseout =function(){this.style.color='#9ca3af';this.style.background='none';};
    clip.onclick=function(e){
      e.preventDefault();e.stopPropagation();
      var btns=p.querySelectorAll('[data-testid="stButton"] button');
      for(var i=0;i<btns.length;i++){
        var t=btns[i].textContent||'';
        if(t.indexOf('Attach')>-1||t.indexOf('Hide')>-1){btns[i].click();break;}
      }
    };
    inp.style.setProperty('position','relative','important');
    inp.appendChild(clip);
  }

  function scrollToBottom(){
    var m=p.querySelector('[data-testid="stMain"]');
    if(m) m.scrollTop=m.scrollHeight;
  }

  // Apply immediately
  applyFlex(); injectClip(); scrollToBottom();

  // Watch stBottomBlockContainer: if Streamlit resets its style, re-apply flex props instantly
  function watchFoot(){
    var foot=p.querySelector('[data-testid="stBottomBlockContainer"]');
    if(!foot||foot.__flexGuarded) return;
    foot.__flexGuarded=true;
    new w.MutationObserver(function(){
      pin(foot,{flex:'0 0 auto',width:'100%',
        position:'relative',bottom:'auto',transform:'none','will-change':'auto'});
    }).observe(foot,{attributes:true,attributeFilter:['style','class']});
  }

  // Watch for Streamlit <style> tag injections in <head> — Emotion CSS re-injection
  new w.MutationObserver(function(){ applyFlex(); }).observe(p.head,{childList:true});

  // Watch for DOM rerenders (new nodes added anywhere under the app)
  new w.MutationObserver(function(muts){
    var changed=false;
    muts.forEach(function(m){if(m.addedNodes.length) changed=true;});
    if(changed){ applyFlex(); watchFoot(); injectClip(); scrollToBottom(); }
  }).observe(p.querySelector('[data-testid="stAppViewContainer"]')||p.body,
    {childList:true,subtree:true});

  watchFoot();

  // Backup poll at 300ms (belt-and-suspenders)
  setInterval(function(){ applyFlex(); watchFoot(); injectClip(); },300);
})();
</script>""", height=0)

    # ── 7. CHAT INPUT (always at the bottom via stBottomBlockContainer) ──
    user_input = st.chat_input("Ask Anything...")

    # ── 8. HANDLE SEND ──────────────────────────────────────────
    if user_input or uploaded:
        text      = (user_input or "").strip()
        file_data = _process_upload(uploaded) if uploaded else None
        user_msg  = {"role": "user", "content": text}
        fname     = uploaded.name if uploaded else ""
        ftype     = (file_data or {}).get("type", "")
        if file_data:
            user_msg["file"] = file_data
        if not st.session_state.issue_text:
            st.session_state.issue_text = text or f"[Attached: {fname}]"

        if not st.session_state.get("session_id"):
            st.session_state.session_id = support_db.create_session("Guest", "")

        st.session_state.messages.append(user_msg)
        sid = st.session_state.get("session_id")
        if sid:
            support_db.save_message(sid, "user", text, fname, ftype)

        # Populate the pre-declared slots (they are already in the messages area)
        _typing_slot.markdown(_TYPING_HTML, unsafe_allow_html=True)
        _cmp.html("""<script>(function(){try{var m=window.parent.document.querySelector('[data-testid="stMain"]');if(m)m.scrollTop=m.scrollHeight;}catch(e){}})()</script>""", height=0)

        reply = process_chat(text, st.session_state.messages, file_data)

        st.session_state.pop("_stream_slot", None)
        st.session_state.pop("_typing_slot", None)
        _typing_slot.empty()
        _stream_slot.empty()

        st.session_state.messages.append({"role": "assistant", "content": reply})
        if sid:
            support_db.save_message(sid, "assistant", reply)

        st.session_state.turn_count = st.session_state.get("turn_count", 0) + 1
        if st.session_state.turn_count >= 3:
            st.session_state.waiting_feedback = True

        st.rerun()


# ═══════════════════════════════════════════════════════════
# PAGE: RESOLVED
# ═══════════════════════════════════════════════════════════
def render_resolved():
    st.markdown("""
<div class="chat-navbar">
  <div class="cn-brand">
    <div class="cn-icon">🤖</div>
    <span class="cn-title">AI Support Assistant</span>
  </div>
  <span class="cn-portal">Support Portal</span>
  <div></div>
</div>
""", unsafe_allow_html=True)
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
    st.markdown("""
<div class="chat-navbar">
  <div class="cn-brand">
    <div class="cn-icon">🤖</div>
    <span class="cn-title">AI Support Assistant</span>
  </div>
  <span class="cn-portal">Support Portal</span>
  <div></div>
</div>
""", unsafe_allow_html=True)
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
# PAGE: INTRO (onboarding gate)
# ═══════════════════════════════════════════════════════════
def render_intro():
    # Page-specific CSS: centre the block-container and style it as the white card.
    # Inputs keep visible borders here; the chat page overrides them to be borderless.
    st.markdown("""
<style>
/* ── INTRO: make stMain fill the viewport height so card is vertically centred ── */
[data-testid="stMain"]>div{
  display:flex!important;align-items:center!important;justify-content:center!important;
  min-height:100vh!important;padding:40px 16px!important;
}
/* ── INTRO: block-container = the white card ── */
.block-container{
  background:#fff!important;border-radius:18px!important;
  box-shadow:0 4px 32px rgba(0,0,0,.10)!important;
  padding:44px 48px 40px!important;
  max-width:580px!important;width:100%!important;
  margin:0!important;
}
/* ── INTRO: visible input fields ── */
.stTextInput label{display:block!important;font-size:13px!important;font-weight:500!important;color:#374151!important;margin-bottom:4px!important;}
.stTextInput>div>div>input{
  padding:10px 14px!important;
  border:1.5px solid #e5e7eb!important;border-radius:10px!important;
  font-size:14px!important;color:#111827!important;
  background:#f9fafb!important;height:auto!important;
  outline:none!important;box-shadow:none!important;
}
.stTextInput>div>div>input::placeholder{color:#9ca3af!important;}
.stTextInput>div>div>input:focus{
  border-color:#534AB7!important;
  box-shadow:0 0 0 3px rgba(83,74,183,.12)!important;
  background:#fff!important;
}
.stTextInput>div>div{border:none!important;background:transparent!important;box-shadow:none!important;}
/* ── INTRO: continue button ── */
div.stButton>button{width:100%!important;padding:12px!important;background:#534AB7!important;
  color:#fff!important;border:none!important;border-radius:10px!important;
  font-size:15px!important;font-weight:600!important;margin-top:4px!important;}
div.stButton>button:hover{background:#4338ca!important;}
</style>
""", unsafe_allow_html=True)

    # Logo / title / subtitle rendered as inline HTML (no Streamlit widgets = no nesting problem)
    st.markdown("""
<div style="display:flex;flex-direction:column;align-items:center;margin-bottom:28px;">
  <div style="width:60px;height:60px;border-radius:16px;
       background:linear-gradient(135deg,#534AB7,#7F77DD);
       display:flex;align-items:center;justify-content:center;
       font-size:30px;margin-bottom:16px;">🤖</div>
  <div style="font-size:24px;font-weight:700;color:#111827;margin-bottom:8px;text-align:center;">
    AI Support Assistant</div>
  <div style="font-size:14px;color:#6b7280;text-align:center;">
    Please provide your details to continue</div>
</div>
""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Name", placeholder="Alex Johnson")
    with c2:
        email = st.text_input("Corporate Email", placeholder="alex@acme.com")
    company = st.text_input("Company Name", placeholder="Acme Corp")

    if st.button("Continue →", use_container_width=True):
        name_val    = name.strip()
        email_val   = email.strip()
        company_val = company.strip()
        if not name_val:
            st.error("Please enter your name.")
        elif not email_val or "@" not in email_val:
            st.error("Please enter a valid corporate email.")
        elif not company_val:
            st.error("Please enter your company name.")
        else:
            st.session_state.user    = {"name": name_val, "email": email_val}
            st.session_state.company = company_val
            if not st.session_state.get("session_id"):
                st.session_state.session_id = support_db.create_session(name_val, email_val)
            st.session_state.page = "chat"
            st.rerun()

    st.markdown('<div style="margin-top:8px;border-top:1px solid #f3f4f6;padding-top:12px;"></div>', unsafe_allow_html=True)
    if st.button("🔄 Sync Salesforce Knowledge Base", key="intro_sync_sf", use_container_width=True):
        with st.spinner("Syncing…"):
            ok, msg = sync_sf_knowledge()
        if ok:
            _cached_case_subjects.clear()
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")


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
