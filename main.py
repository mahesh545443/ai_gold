"""
ANALYTICS AVENUE — AI Gold Negotiation Orchestrator
"""
import os, sys, tempfile, base64
import streamlit as st
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── SECRETS — load GROQ key from Streamlit secrets ───────────────
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

from agents.intake import IntakeAgent
from agents.classifier import ClassificationAgent
from agents.rag_agent import RAGPricingAgent
from agents.proposal_agent import ProposalGeneratorAgent
from agents.negotiation_agent import NegotiationAgent

st.set_page_config(page_title="Analytics Avenue | AI Gold Negotiation", layout="wide", page_icon="⚜️")

# ── LOGO — tries multiple locations, works on Windows + Linux ─────
def find_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "aard_new_logo.png"),          # same folder as main.py
        os.path.join(base_dir, "assets", "aard_new_logo.png"),# assets subfolder
        "aard_new_logo.png",                                   # current working dir
        r"C:\Users\User\Downloads\gold_jewellery_ai_automation\aard_new_logo.png",  # Windows local
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return None

LOGO_PATH = find_logo()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #fff; }

.stTabs [data-baseweb="tab-list"] { background:white; border-bottom:1.5px solid #E0E0E0; padding:0 4px; gap:0; }
.stTabs [data-baseweb="tab"] { color:#555; font-size:14px; font-weight:500; padding:12px 24px; border-bottom:2px solid transparent; }
.stTabs [aria-selected="true"] { color:#C9952A !important; border-bottom:2px solid #C9952A !important; background:transparent !important; }

.card { background:white; border-radius:8px; padding:18px 22px; border:1px solid #EBEBEB; margin-bottom:14px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }
.card-gold { background:#FFFBF0; border-radius:8px; padding:16px 20px; border:1px solid #C9952A; margin-bottom:14px; }

.sec { font-size:15px; font-weight:700; color:#1A1A2E; border-bottom:2px solid #C9952A; padding-bottom:5px; margin:20px 0 12px; }

.mc { background:white; border:1px solid #E8D8A0; border-radius:8px; padding:14px; text-align:center; margin-bottom:8px; }
.mv { font-size:20px; font-weight:700; color:#8B6914; }
.ml { font-size:10px; color:#999; margin-top:3px; text-transform:uppercase; letter-spacing:0.5px; }

.cs { background:#F9F5EB; border-left:3px solid #C9952A; padding:7px 12px; margin:3px 0; border-radius:0 6px 6px 0; font-family:monospace; font-size:11.5px; color:#333; line-height:1.6; }

.email-box { background:white; border:1px solid #DDDDDD; border-radius:8px; overflow:hidden; margin-bottom:14px; }
.email-header { background:#F5F5F5; padding:12px 16px; border-bottom:1px solid #DDDDDD; font-size:12px; color:#444; }
.email-body { padding:16px; font-size:13px; color:#333; line-height:1.8; white-space:pre-wrap; }

.cb  { background:#EEF2FF; border-left:3px solid #5C6BC0; border-radius:0 10px 10px 10px; padding:10px 14px; margin:6px 0; font-size:13px; }
.cs2 { background:#FFFBF0; border-right:3px solid #C9952A; border-radius:10px 0 10px 10px; padding:10px 14px; margin:6px 0; font-size:13px; }

.pb { display:inline-flex; align-items:center; gap:5px; padding:5px 14px; border-radius:20px; font-size:11px; font-weight:600; }
.pd { background:#E8F5E9; color:#2E7D32; border:1px solid #A5D6A7; }
.pa { background:#FFF8E1; color:#E65100; border:1px solid #FFE082; }
.pw { background:#F5F5F5; color:#9E9E9E; border:1px solid #E0E0E0; }

.waiting { background:#FFF3E0; border:1px solid #FFB74D; border-radius:8px; padding:14px 18px; font-size:13px; color:#E65100; }

.logo-wrap { display:flex; align-items:center; gap:16px; padding:16px 0 8px; }
.logo-text  { font-size:20px; font-weight:700; color:#1A3A6B; line-height:1.35; }
.logo-box   { width:54px; height:54px; background:#1A3A6B; border-radius:8px;
              display:flex; align-items:center; justify-content:center;
              font-size:18px; font-weight:700; color:white; letter-spacing:1px; flex-shrink:0; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────
for k, v in {
    "step":"UPLOAD","lead":None,"ai":None,"pricing":None,
    "quote_path":None,"neg_rounds":[],"revised_path":None,
    "rag":None,"email_sent":False,"waiting":False,
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ── HELPERS ───────────────────────────────────────────────────────
def get_rag():
    if not st.session_state.rag:
        with st.spinner("Initialising Pricing Engine & Vector DB..."):
            st.session_state.rag = RAGPricingAgent()
    return st.session_state.rag

def pbadge(name):
    order = ["UPLOAD","PRICED","QUOTED","DONE"]
    cur   = st.session_state.step
    try:
        if order.index(name) < order.index(cur): return "pd"
        if order.index(name) == order.index(cur): return "pa"
    except: pass
    return "pw"

def show_calc(item):
    for key, lbl in [
        ("step1_base_cost",         "① Base Cost / gram"),
        ("step2_unit_raw_cost",     "② Unit Raw Cost"),
        ("step3_market_adjustment", "③ Market Adjustment"),
        ("step4_selling_price",     "④ Selling Price — 30% Margin"),
        ("step5_gst",               "⑤ GST — CGST 1.5% + SGST 1.5%"),
        ("step6_invoice_price",     "⑥ Invoice Price / unit"),
        ("step7_line_total",        "⑦ Line Total"),
    ]:
        if key in item.get("calculation_steps", {}):
            st.markdown(f'<div class="cs"><b style="color:#8B6914">{lbl}</b><br/>{item["calculation_steps"][key]}</div>',
                        unsafe_allow_html=True)

def show_logo():
    """
    Show logo image if found.
    Fallback: clean navy 'AA' box — NO emoji at all.
    For Streamlit Cloud: copy aard_new_logo.png into root of your repo.
    """
    if LOGO_PATH:
        try:
            with open(LOGO_PATH, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
            <div class="logo-wrap">
                <img src="data:image/png;base64,{b64}"
                     style="height:54px;width:auto;object-fit:contain;flex-shrink:0;"/>
                <div class="logo-text">
                    Analytics Avenue &amp;<br/>Advanced Analytics
                </div>
            </div>
            <hr style="border:none;border-top:1px solid #EBEBEB;margin:4px 0 16px;"/>
            """, unsafe_allow_html=True)
            return
        except Exception:
            pass

    # Fallback — navy AA box, no emoji
    st.markdown("""
    <div class="logo-wrap">
        <div class="logo-box">AA</div>
        <div class="logo-text">
            Analytics Avenue &amp;<br/>Advanced Analytics
        </div>
    </div>
    <hr style="border:none;border-top:1px solid #EBEBEB;margin:4px 0 16px;"/>
    """, unsafe_allow_html=True)

def make_email(ai, pricing):
    customer = ai.get("customer_name","Valued Customer")
    email    = ai.get("sender_email","—")
    total    = pricing.get("grand_total_invoice",0)
    pretax   = pricing.get("grand_total_pretax",0)
    cgst     = pricing.get("grand_total_cgst",0)
    sgst     = pricing.get("grand_total_sgst",0)
    live     = pricing.get("live_gold_price_24k_inr",0)
    date_str = datetime.now().strftime("%d-%B-%Y")
    lines    = ""
    for item in pricing.get("line_items",[]):
        if item.get("product_name") != "NOT MATCHED":
            lines += (f"  - {item.get('product_name')} | Qty: {item.get('qty')} | "
                      f"Unit: Rs.{item.get('invoice_price_per_unit',0):,.2f} | "
                      f"Total: Rs.{item.get('line_total_invoice',0):,.2f}\n")
    return {
        "to": email,
        "subject": f"Commercial Quotation - Gold Products | Analytics Avenue | {date_str}",
        "body": f"""Dear {customer},

Thank you for your Request for Quotation. Please find our commercial quotation below.

ITEMS:
{lines}
Sub Total (Pre-GST) : Rs.{pretax:,.2f}
CGST @ 1.5%         : Rs.{cgst:,.2f}
SGST @ 1.5%         : Rs.{sgst:,.2f}
-------------------------------------
GRAND TOTAL         : Rs.{total:,.2f} (Incl. GST)

Gold Rate Used : Rs.{live:,.2f}/gram (24K, MCX Live as on {date_str})
PDF quotation  : Attached for your reference
Validity       : 7 days from date of issue

We look forward to your response.

Warm regards,
Sales Team
Analytics Avenue & Advanced Analytics
Email: sales@analyticsavenue.com | Phone: +91-44-2345-6789"""
    }

def make_neg_email(ai, rnd):
    email    = ai.get("sender_email","—")
    decision = rnd.get("decision","COUNTER_OFFER")
    date_str = datetime.now().strftime("%d-%B-%Y")
    return {
        "to": email,
        "subject": f"Re: Commercial Quotation - {'Counter Offer' if decision=='COUNTER_OFFER' else decision} | Analytics Avenue | {date_str}",
        "body": rnd.get("reply_email_draft","—")
    }

def show_email(e):
    st.markdown(f"""
    <div class="email-box">
        <div class="email-header">
            <b>To:</b> {e['to']}<br/>
            <b>Subject:</b> {e['subject']}
        </div>
        <div class="email-body">{e['body']}</div>
    </div>
    """, unsafe_allow_html=True)

def reset():
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

# ══════════════════════════════════════════════════════════════════
#  LOGO + TITLE
# ══════════════════════════════════════════════════════════════════
show_logo()
st.markdown("## AI Gold Negotiation Orchestrator")

# ══════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════
t1, t2 = st.tabs(["Overview", "Application"])

# ═════════════════════════════════════════════════════════════════
#  OVERVIEW
# ═════════════════════════════════════════════════════════════════
with t1:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="sec">Purpose</div>', unsafe_allow_html=True)
        st.markdown("""<div class="card" style="border-left:4px solid #C9952A;">
        <p style="margin:0;font-size:13.5px;color:#333;line-height:1.8;">
            Analytics Avenue receives gold RFQs from buyers. This system reads the RFQ,
            matches products, fetches <b>live MCX gold price</b>, calculates a quote with
            <b>30% pre-GST margin</b>, generates a professional PDF, sends the quote email
            and handles buyer negotiations — accepting, countering or rejecting based on
            a <b>20% minimum margin floor</b>.
        </p></div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec">Capabilities</div>', unsafe_allow_html=True)
        st.markdown("""<div class="card"><ul style="margin:0;padding-left:16px;font-size:13px;line-height:2.1;">
            <li>Upload buyer RFQ — <b>.txt / .docx / .pdf</b></li>
            <li>AI classification: <b>HOT / WARM / COLD</b> with TAT</li>
            <li>Live <b>MCX/COMEX gold price</b> — USD/oz to INR/gram</li>
            <li>ChromaDB <b>vector search</b> — product matching</li>
            <li><b>7-step pricing formula</b> — full transparency in UI</li>
            <li>Guaranteed <b>30% pre-GST margin</b> on every quote</li>
            <li><b>CGST 1.5% + SGST 1.5%</b> shown separately</li>
            <li>Auto <b>email draft</b> after quote + each negotiation round</li>
            <li>Multi-round — <b>ACCEPT / COUNTER / REJECT</b></li>
            <li>Professional <b>branded PDF</b> — initial + revised</li>
        </ul></div>""", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="sec">Pricing Equation</div>', unsafe_allow_html=True)
        st.markdown("""<div class="card-gold">
        <div style="font-family:monospace;font-size:12px;line-height:2.1;color:#333;">
            <b style="color:#8B6914">From CSV:</b> C=PurchaseCost/g | M=Making/g | W%=Wastage | P=Packaging | H=Hallmark<br/>
            <b style="color:#8B6914">From Live:</b> L = MCX Gold Price (INR/gram)<br/><br/>
            (1) BaseCost/g   = C + M + (C x W%)<br/>
            (2) UnitRawCost  = (BaseCost x Weight) + P + H<br/>
            (3) MarketFactor = max(L / C, 1.0)<br/>
            (4) AdjustedCost = UnitRawCost x MarketFactor<br/>
            (5) <b>SellingPrice = AdjustedCost / 0.70</b>  &lt;-- 30% margin<br/>
            (6) CGST = SellingPrice x 1.5% | SGST = SellingPrice x 1.5%<br/>
            (7) <b>InvoicePrice = SellingPrice + CGST + SGST</b>
        </div></div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec">Negotiation Logic</div>', unsafe_allow_html=True)
        st.markdown("""<div class="card">
        <div style="font-size:13px;line-height:2.1;">
            Quote at <b>30% margin</b>. Floor = <b>20% margin</b><br/>
            Floor = AdjustedCost / 0.80 (per item)<br/><br/>
            <b>ACCEPT</b>  — Buyer is greater than or equal to Our Quote<br/>
            <b>COUNTER</b> — Floor less than or equal to Buyer less than Quote, midpoint offered<br/>
            <b>REJECT</b>  — Buyer is below 20% floor<br/>
            <span style="font-size:11px;color:#999;">All math in Python. LLM writes the email only.</span>
        </div></div>""", unsafe_allow_html=True)

        st.markdown('<div class="sec">Business Impact</div>', unsafe_allow_html=True)
        st.markdown("""<div class="card"><ul style="margin:0;padding-left:16px;font-size:13px;line-height:2.1;">
            <li><b>Never undersell</b> — 30% margin locked in every quote</li>
            <li><b>Instant quotes</b> — RFQ to PDF in 30 seconds</li>
            <li><b>Auto email drafts</b> — quote + negotiation emails ready</li>
            <li><b>Auto-negotiation</b> — no manual intervention needed</li>
            <li><b>Professional PDFs</b> — logo, GST, T&C, bank details</li>
        </ul></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="sec">Agent Pipeline</div>', unsafe_allow_html=True)
    for col, (icon, name, desc) in zip(st.columns(6), [
        ("📂","Intake",      "Reads RFQ\n.txt/.docx/.pdf"),
        ("🧠","Classifier",  "Groq LLaMA\nHOT/WARM/COLD"),
        ("📊","RAG Pricing", "ChromaDB match\n+ Live MCX"),
        ("📄","Proposal",    "Branded PDF\ngeneration"),
        ("🤝","Negotiation", "ACCEPT/COUNTER\n/REJECT"),
        ("🔄","Revised PDF", "Updated quote\nnegotiated price"),
    ]):
        with col:
            st.markdown(f"""<div class="card" style="text-align:center;padding:14px 8px;">
                <div style="font-size:26px;margin-bottom:6px;">{icon}</div>
                <div style="font-weight:700;font-size:12px;color:#1A1A2E;">{name}</div>
                <div style="font-size:11px;color:#888;margin-top:4px;white-space:pre-line;">{desc}</div>
            </div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════
#  APPLICATION
# ═════════════════════════════════════════════════════════════════
with t2:

    # Pipeline status bar
    for col, (name, label) in zip(st.columns(4), [
        ("UPLOAD","📂 Upload RFQ"),("PRICED","📊 Priced"),
        ("QUOTED","📄 Quote & Email"),("DONE","✅ Closed"),
    ]):
        with col:
            cls  = pbadge(name)
            icon = "✅" if cls=="pd" else ("⚙️" if cls=="pa" else "⏳")
            st.markdown(f'<span class="pb {cls}">{icon} {label}</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── UPLOAD ────────────────────────────────────────────────
    if st.session_state.step == "UPLOAD":
        st.markdown('<div class="sec">📂 Upload Buyer RFQ</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            uploaded = st.file_uploader("Upload buyer's Request for Quotation", type=["txt","docx","pdf"])
            if uploaded:
                st.success(f"✅ **{uploaded.name}** — {uploaded.size:,} bytes")
                if st.button("🚀 Run AI Pipeline", type="primary", use_container_width=True):
                    fpath = os.path.join(tempfile.mkdtemp(), uploaded.name)
                    with open(fpath,"wb") as f: f.write(uploaded.read())

                    with st.status("📂 Intake — Reading file...", expanded=True):
                        raw = IntakeAgent().read_file(fpath)
                        if "error" in raw: st.error(raw["error"]); st.stop()
                        st.write(f"✅ Email: `{raw.get('sender_email','—')}` | Company: `{raw.get('sender_company','—')}`")

                    with st.status("🧠 Classifier — Groq LLaMA analysing...", expanded=True):
                        ai = ClassificationAgent().process(raw)
                        st.write(f"✅ **{ai.get('classification')}** | Customer: **{ai.get('customer_name')}** | Items: **{len(ai.get('extracted_items',[]))}**")

                    with st.status("📊 RAG Pricing — Live MCX + Product Match...", expanded=True):
                        pricing = get_rag().lookup_and_price(ai)
                        st.write(f"✅ Live Gold 24K: **Rs.{pricing.get('live_gold_price_24k_inr',0):,.2f}/gram** ({pricing.get('price_source')})")
                        st.write(f"✅ Grand Total: **Rs.{pricing.get('grand_total_invoice',0):,.2f}**")

                    st.session_state.ai      = ai
                    st.session_state.pricing = pricing
                    st.session_state.lead    = {"ai_analysis":ai,"pricing_data":pricing,"raw_doc":raw}
                    st.session_state.step    = "PRICED"
                    st.rerun()

        with c2:
            st.markdown("""<div class="card-gold">
                <b style="color:#8B6914">What happens when you click Run?</b>
                <div style="font-size:13px;line-height:1.9;color:#555;margin-top:8px;">
                    1. File read — buyer info extracted<br/>
                    2. Groq LLaMA classifies and extracts items<br/>
                    3. Products matched from gold catalogue<br/>
                    4. Live MCX price fetched and quote calculated<br/>
                    5. Review pricing — Generate PDF — Send Email
                </div>
            </div>
            <div class="card">
                <b>Sample file for testing:</b><br/>
                <code style="font-size:11px;background:#F5F5F5;padding:4px 8px;border-radius:4px;">input_folder/sample_rfq.txt</code>
            </div>""", unsafe_allow_html=True)

    # ── PRICED ────────────────────────────────────────────────
    elif st.session_state.step == "PRICED":
        pricing = st.session_state.pricing
        st.markdown('<div class="sec">📊 Live Pricing Results</div>', unsafe_allow_html=True)

        for col, (val, lbl, clr) in zip(st.columns(4), [
            (f"Rs.{pricing.get('live_gold_price_24k_inr',0):,.2f}", "Live Gold 24K / gram", "#8B6914"),
            (f"${pricing.get('gold_usd_per_oz',0):,.2f}",            "Gold USD / oz",        "#555"),
            (f"Rs.{pricing.get('usd_inr_rate',0):,.2f}",             "USD / INR",            "#555"),
            (pricing.get('price_source','—'), "Price Source",
             "#1A6B1A" if pricing.get('price_source')=='LIVE' else "#C0392B"),
        ]):
            with col:
                st.markdown(f'<div class="mc"><div class="mv" style="color:{clr}">{val}</div>'
                            f'<div class="ml">{lbl}</div></div>', unsafe_allow_html=True)

        st.markdown("<br/>", unsafe_allow_html=True)

        for idx, item in enumerate(pricing.get("line_items",[]), 1):
            if item.get("product_name") == "NOT MATCHED":
                st.error(f"Item {idx}: '{item.get('requested_item')}' — not found in catalogue")
                continue

            with st.expander(
                f"{'🥇' if item.get('purity')=='24K' else '🥈'} **{item.get('product_name')}**  |  "
                f"Qty: {item.get('qty')}  |  Invoice/unit: Rs.{item.get('invoice_price_per_unit',0):,.2f}  |  "
                f"Line Total: Rs.{item.get('line_total_invoice',0):,.2f}  |  Margin: {item.get('actual_margin_percent',0):.1f}%",
                expanded=(idx==1)
            ):
                L, R = st.columns(2)
                with L:
                    st.markdown("**Input Parameters:**")
                    for k, v in [
                        ("Product",     item.get("product_name")),
                        ("SKU",         item.get("sku")),
                        ("Purity",      item.get("purity")),
                        ("Weight/unit", f"{item.get('weight_per_unit_grams')}g"),
                        ("Qty",         item.get("qty")),
                        ("Purchase/g",  f"Rs.{item.get('purchase_cost_per_gram',0):,.2f}"),
                        ("Live MCX/g",  f"Rs.{item.get('live_price_per_gram',0):,.2f}"),
                        ("Making/g",    f"Rs.{item.get('making_charges_per_gram',0):,.2f}"),
                        ("Wastage",     f"{item.get('wastage_percent',0)}%"),
                        ("Packaging",   f"Rs.{item.get('packaging_cost',0):,.2f}"),
                        ("Hallmarking", f"Rs.{item.get('hallmarking_fee',0):,.2f}"),
                    ]:
                        st.markdown(f"<span style='color:#666;font-size:12px'>{k}:</span> "
                                    f"<b style='font-size:12px'>{v}</b>", unsafe_allow_html=True)
                with R:
                    st.markdown("**7-Step Calculation:**")
                    show_calc(item)

                st.markdown("---")
                for col, (label, val) in zip(st.columns(5), [
                    ("Selling Price/unit", f"Rs.{item.get('selling_price_per_unit',0):,.2f}"),
                    ("CGST/unit",          f"Rs.{item.get('cgst_per_unit',0):,.2f}"),
                    ("SGST/unit",          f"Rs.{item.get('sgst_per_unit',0):,.2f}"),
                    ("Invoice/unit",       f"Rs.{item.get('invoice_price_per_unit',0):,.2f}"),
                    ("Line Total",         f"Rs.{item.get('line_total_invoice',0):,.2f}"),
                ]):
                    with col: st.metric(label, val)

        st.markdown("---")
        for col, (label, val) in zip(st.columns(4), [
            ("Sub Total (Pre-GST)", f"Rs.{pricing.get('grand_total_pretax',0):,.2f}"),
            ("Total CGST (1.5%)",   f"Rs.{pricing.get('grand_total_cgst',0):,.2f}"),
            ("Total SGST (1.5%)",   f"Rs.{pricing.get('grand_total_sgst',0):,.2f}"),
            ("GRAND TOTAL",         f"Rs.{pricing.get('grand_total_invoice',0):,.2f}"),
        ]):
            with col: st.metric(label, val)

        st.markdown("---")
        if st.button("📄 Generate Quote PDF & Prepare Email", type="primary", use_container_width=True):
            with st.spinner("Generating PDF..."):
                path = ProposalGeneratorAgent().generate_quote(st.session_state.lead)
                st.session_state.quote_path = path
                st.session_state.email_sent = False
                st.session_state.waiting    = False
            st.session_state.step = "QUOTED"
            st.rerun()

        if st.button("⬅️ Upload New File"): reset()

    # ── QUOTED ────────────────────────────────────────────────
    elif st.session_state.step == "QUOTED":
        pricing = st.session_state.pricing
        ai      = st.session_state.ai

        st.success("✅ Quote PDF Generated!")
        st.markdown(f"""<div class="card-gold">
            <b>📄 PDF saved at:</b><br/>
            <code style="font-size:12px;">{os.path.abspath(st.session_state.quote_path)}</code>
            <span style="font-size:12px;color:#888;margin-left:16px;">{datetime.now().strftime('%d-%b-%Y %H:%M')}</span>
        </div>""", unsafe_allow_html=True)

        for col, (label, val) in zip(st.columns(3), [
            ("Pre-GST Total", f"Rs.{pricing.get('grand_total_pretax',0):,.2f}"),
            ("GST (3%)",      f"Rs.{pricing.get('grand_total_gst',0):,.2f}"),
            ("Invoice Total", f"Rs.{pricing.get('grand_total_invoice',0):,.2f}"),
        ]):
            with col: st.metric(label, val)

        st.markdown("---")

        # Past negotiation rounds
        if st.session_state.neg_rounds:
            st.markdown('<div class="sec">📧 Negotiation History</div>', unsafe_allow_html=True)
            for i, rnd in enumerate(st.session_state.neg_rounds, 1):
                with st.expander(
                    f"Round {i} — **{rnd.get('decision')}**  |  "
                    f"Buyer: Rs.{rnd.get('buyer_offered_total_invoice',0):,.2f}  |  "
                    f"Counter: Rs.{rnd.get('new_invoice_total',0):,.2f}",
                    expanded=False
                ):
                    L, R = st.columns(2)
                    with L:
                        st.markdown(f'<div class="cb"><b>Buyer Message:</b><br/>{rnd.get("buyer_message","—")}</div>',
                                    unsafe_allow_html=True)
                        st.markdown("**Negotiation Calculation:**")
                        for lbl, val in [
                            ("Buyer offered (incl. GST)",  f"Rs.{rnd.get('buyer_offered_total_invoice',0):,.2f}"),
                            ("Buyer offered (pre-GST)",    f"Rs.{rnd.get('buyer_offered_pretax',0):,.2f}"),
                            ("Our quote (pre-GST)",        f"Rs.{rnd.get('original_total_pretax',0):,.2f}"),
                            ("20% floor (pre-GST)",        f"Rs.{rnd.get('floor_pretax',0):,.2f}"),
                            ("20% floor (incl. GST)",      f"Rs.{rnd.get('floor_invoice',0):,.2f}"),
                            ("Gap from quote",             f"{rnd.get('gap_from_original_pct',0):.1f}%"),
                            ("Decision",                   rnd.get("decision","")),
                            ("Counter (pre-GST)",          f"Rs.{rnd.get('new_offered_pretax',0):,.2f}"),
                            ("Counter CGST",               f"Rs.{rnd.get('new_offered_cgst',0):,.2f}"),
                            ("Counter SGST",               f"Rs.{rnd.get('new_offered_sgst',0):,.2f}"),
                            ("Counter total (incl. GST)",  f"Rs.{rnd.get('new_invoice_total',0):,.2f}"),
                            ("Discount applied",           f"{rnd.get('discount_percent',0):.2f}%"),
                        ]:
                            st.markdown(f'<div class="cs"><b style="color:#8B6914">{lbl}:</b> {val}</div>',
                                        unsafe_allow_html=True)
                        st.caption(f"Reasoning: {rnd.get('reasoning','—')}")
                    with R:
                        st.markdown("**📧 Email Sent to Buyer:**")
                        show_email(make_neg_email(ai, rnd))

        # Email not sent yet
        if not st.session_state.email_sent:
            st.markdown('<div class="sec">📧 Email Ready to Send</div>', unsafe_allow_html=True)
            draft = make_email(ai, pricing) if not st.session_state.neg_rounds \
                    else make_neg_email(ai, st.session_state.neg_rounds[-1])
            show_email(draft)

            if st.button("📤 Send Email to Buyer", type="primary", use_container_width=True):
                st.session_state.email_sent = True
                st.session_state.waiting    = True
                st.rerun()

        # Waiting for buyer reply
        elif st.session_state.waiting:
            st.markdown('<div class="sec">📧 Email Sent</div>', unsafe_allow_html=True)
            st.success("✅ Email sent to buyer successfully!")
            st.markdown('<div class="waiting"><b>Waiting for buyer response...</b> — Enter buyer reply below when received</div>',
                        unsafe_allow_html=True)

            if st.session_state.revised_path and os.path.exists(st.session_state.revised_path):
                st.markdown(f"""<div class="card-gold" style="margin-top:12px;">
                    <b>📄 Revised Quote:</b><br/>
                    <code style="font-size:12px;">{os.path.abspath(st.session_state.revised_path)}</code>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown('<div class="sec">🤝 Buyer Negotiation</div>', unsafe_allow_html=True)
            reply = st.chat_input("e.g. 'Can you give 5% discount?' or 'We can pay Rs.50,00,00,000'")

            if reply:
                with st.status("🤝 Negotiation Agent running...", expanded=True):
                    updated = NegotiationAgent().handle_counter_offer(st.session_state.lead, reply)
                    out     = updated["negotiation_outcome"]
                    st.write(f"✅ Decision: **{out['decision']}** | Counter: Rs.{out.get('new_invoice_total',0):,.2f} | Discount: {out.get('discount_percent',0):.2f}%")

                st.session_state.neg_rounds.append(out)
                st.session_state.lead = updated

                with st.spinner("Generating revised PDF..."):
                    st.session_state.revised_path = ProposalGeneratorAgent().generate_quote(updated)

                st.session_state.email_sent = False
                st.session_state.waiting    = False

                if out["decision"] == "REJECT": st.session_state.step = "DONE"
                st.rerun()

            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Close Deal", type="primary", use_container_width=True):
                    st.session_state.step = "DONE"; st.rerun()
            with c2:
                if st.button("🔄 Start New RFQ", use_container_width=True): reset()

    # ── DONE ──────────────────────────────────────────────────
    elif st.session_state.step == "DONE":
        st.balloons()
        last = st.session_state.neg_rounds[-1] if st.session_state.neg_rounds else {}

        if last.get("decision") == "REJECT":
            st.error("🚫 Negotiation Closed — REJECTED. Buyer went below our 20% margin floor.")
        else:
            st.success("🎉 Deal Closed Successfully!")

        pricing = st.session_state.pricing
        for col, (label, val) in zip(st.columns(3), [
            ("Original Quote",     f"Rs.{pricing.get('grand_total_invoice',0):,.2f}"),
            ("Final Agreed Price", f"Rs.{last.get('new_invoice_total', pricing.get('grand_total_invoice',0)):,.2f}"),
            ("Negotiation Rounds", str(len(st.session_state.neg_rounds))),
        ]):
            with col: st.metric(label, val)

        st.markdown("**📁 Output Files:**")
        if st.session_state.quote_path:
            st.markdown(f"📄 Initial Quote: `{os.path.abspath(st.session_state.quote_path)}`")
        if st.session_state.revised_path:
            st.markdown(f"📄 Revised Quote: `{os.path.abspath(st.session_state.revised_path)}`")

        st.markdown("---")
        if st.button("🔄 Start New RFQ", type="primary", use_container_width=True): reset()
