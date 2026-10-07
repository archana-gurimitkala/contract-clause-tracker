import html
from urllib.parse import quote

import streamlit as st

import dashboard
import memo
import parser
import portfolio_filter
import renewal_email
import storage
from extractor import CLAUSE_TYPES, DATE_FIELDS, extract_contract
from labels import CLAUSE_LABELS, DATE_LABELS, STATUS_COLORS
from risk_score import compute_risk_score

BUCKET_STATUS = {
    "overdue": ("critical", "Overdue"),
    "0-30": ("serious", "Due ≤ 30 days"),
    "31-60": ("warning", "Due ≤ 60 days"),
    "61-90": ("good", "Due ≤ 90 days"),
}

KPI_ORDER = ["overdue", "0-30", "31-60", "61-90"]
KPI_LABELS = {
    "overdue": "Overdue",
    "0-30": "Due in 30 days",
    "31-60": "Due in 60 days",
    "61-90": "Due in 90 days",
}

HEATMAP_SHORT_LABELS = {
    "termination": "Term.",
    "auto_renewal": "Renewal",
    "confidentiality": "Confid.",
    "indemnification": "Indemn.",
    "limitation_of_liability": "Liability",
    "governing_law": "Gov. Law",
    "payment_terms": "Payment",
}


def esc(s):
    return html.escape(s) if s else ""


def badge_html(label, color_hex):
    return (
        f'<span style="background:{color_hex}1f;color:{color_hex};'
        f"border:1px solid {color_hex}55;border-radius:999px;padding:4px 14px;"
        f'font-size:0.9rem;font-weight:600;white-space:nowrap;letter-spacing:0.01em;">'
        f"{esc(label)}</span>"
    )


def clause_status_badge(clause):
    if not clause["found"]:
        return badge_html("Not found", STATUS_COLORS["neutral"])
    if clause["flagged"]:
        return badge_html("Flagged", STATUS_COLORS["critical"])
    return badge_html("Standard", STATUS_COLORS["good"])


st.set_page_config(page_title="Contract Clause Tracker", page_icon="📄", layout="wide")

st.markdown(
    """
<style>
:root {
  --cc-bg: #F7F4EC;
  --cc-surface: #FFFFFF;
  --cc-ink: #2A2721;
  --cc-ink-secondary: #5E584C;
  --cc-ink-muted: #948D7C;
  --cc-border: #E4DECE;
  --cc-accent: #C96442;
  --cc-accent-soft: #C964421A;
}
html { font-size: 19px; }
.stApp { background: var(--cc-bg); }
.block-container { padding-top: 2.2rem; max-width: 1150px; }
h1, h2, h3 { color: var(--cc-ink) !important; letter-spacing: -0.01em; }
[data-testid="stSidebar"] { background: var(--cc-surface); border-right: 1px solid var(--cc-border); }
[data-testid="stSidebar"] * { font-size: 1rem !important; }
.cc-subtitle { color: var(--cc-ink-secondary); font-size: 1.05rem; margin-top: -0.7rem; margin-bottom: 1.8rem; }
.cc-section-label { color: var(--cc-ink-muted); font-size: 0.88rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; margin: 1.6rem 0 0.6rem 0; }
.cc-card { background: var(--cc-surface); border: 1px solid var(--cc-border); border-radius: 12px;
  padding: 18px 22px; margin-bottom: 14px; box-shadow: 0 1px 2px rgba(42,39,33,0.04); }
.cc-card--muted { background: transparent; border-style: dashed; box-shadow: none; }
.cc-run-summary { color: var(--cc-ink-secondary); font-size: 1rem; margin: -0.3rem 0 1rem 0; }
.cc-clause-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.cc-clause-title { font-weight: 600; font-size: 1.15rem; color: var(--cc-ink); }
.cc-quote { border-left: 3px solid var(--cc-accent-soft); background: var(--cc-bg); padding: 10px 16px;
  margin: 12px 0 10px 0; color: var(--cc-ink-secondary); font-size: 1.02rem; font-style: italic; border-radius: 0 6px 6px 0; }
.cc-summary { color: var(--cc-ink); font-size: 1.03rem; margin-bottom: 4px; }
.cc-flag-box { background: #B23B3B14; border-left: 3px solid #B23B3B; padding: 10px 16px;
  border-radius: 0 6px 6px 0; font-size: 0.98rem; color: #7A2A2A; margin-top: 12px; }
.cc-redline-box { background: #0ca30c14; border-left: 3px solid #0ca30c; padding: 10px 16px;
  border-radius: 0 6px 6px 0; font-size: 0.98rem; color: #1E5E1E; margin-top: 10px; }
.cc-empty { color: var(--cc-ink-muted); font-size: 1rem; font-style: italic; }
.cc-date-tile { background: var(--cc-surface); border: 1px solid var(--cc-border); border-radius: 12px;
  padding: 16px 18px; height: 100%; }
.cc-date-label { font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--cc-ink-muted); margin-bottom: 8px; }
.cc-date-value { font-size: 1.3rem; font-weight: 700; color: var(--cc-ink); }
.cc-date-quote { font-size: 0.88rem; color: var(--cc-ink-muted); margin-top: 8px; font-style: italic; }
.cc-kpi-tile { background: var(--cc-surface); border: 1px solid var(--cc-border); border-top: 3px solid var(--cc-border);
  border-radius: 12px; padding: 18px; text-align: center; }
.cc-kpi-value { font-size: 2rem; font-weight: 700; color: var(--cc-ink); }
.cc-kpi-label { font-size: 0.88rem; color: var(--cc-ink-secondary); margin-top: 4px; }
.cc-risk-tile { background: var(--cc-surface); border: 1px solid var(--cc-border); border-radius: 14px;
  padding: 20px 24px; margin-bottom: 16px; display: flex; align-items: center; gap: 20px; border-left: 6px solid var(--cc-border); }
.cc-risk-score { font-size: 2.6rem; font-weight: 800; }
.cc-risk-label { font-size: 1.05rem; color: var(--cc-ink-secondary); }
table.cc-dash, table.cc-heat { width: 100%; border-collapse: collapse; font-size: 1rem; }
table.cc-dash th, table.cc-heat th { text-align: left; color: var(--cc-ink-muted); font-weight: 700; font-size: 0.82rem;
  text-transform: uppercase; letter-spacing: 0.04em; padding: 10px 12px; border-bottom: 1px solid var(--cc-border); }
table.cc-dash td, table.cc-heat td { padding: 13px 12px; border-bottom: 1px solid var(--cc-border); color: var(--cc-ink); vertical-align: middle; }
table.cc-dash tbody tr { transition: background 0.1s ease; }
table.cc-dash tbody tr:hover td { background: var(--cc-bg); }
table.cc-heat td.cc-heat-cell { text-align: center; }
.cc-heat-chip { display: inline-block; width: 100%; border-radius: 6px; padding: 5px 0; font-size: 0.85rem; font-weight: 700; }
.stButton > button[kind="primary"] { background: var(--cc-accent); border-color: var(--cc-accent); }
.stButton > button[kind="primary"]:hover { background: #B2552F; border-color: #B2552F; }
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Analyze a Contract")
    uploaded = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])
    model = st.selectbox(
        "Extraction model",
        ["gpt-4o", "gpt-4o-mini"],
        index=0,
        help="gpt-4o is the default — more reliable on clause flagging. gpt-4o-mini is cheaper but missed real red flags in testing.",
    )
    analyze_clicked = st.button("Analyze Contract", type="primary", use_container_width=True, disabled=uploaded is None)
    if analyze_clicked and uploaded is not None:
        with st.spinner("Extracting text and analyzing clauses..."):
            text = parser.extract_text(uploaded, filename=uploaded.name)
            result = extract_contract(text, model=model)
            storage.save_run(uploaded.name, result, model)
            st.session_state["last_result"] = result
            st.session_state["last_name"] = uploaded.name

    st.markdown("---")
    st.markdown("### Display Mode")
    display_mode = st.radio(
        "How should summaries and flag reasons read?",
        ["Plain-English", "Legal"],
        index=0,
        label_visibility="collapsed",
        help="Plain-English: client-friendly, no jargon. Legal: precise terminology with playbook references.",
    )
    mode = "legal" if display_mode == "Legal" else "plain"
    summary_key = "summary_legal" if mode == "legal" else "summary_plain"
    reason_key = "flag_reason_legal" if mode == "legal" else "flag_reason_plain"

st.title("Contract Clause Extractor")
st.markdown(
    '<div class="cc-subtitle">AI-assisted clause review, red-flag detection, and renewal tracking.</div>',
    unsafe_allow_html=True,
)

tab_upload, tab_dashboard = st.tabs(["Analysis", "Renewal Dashboard"])

with tab_upload:
    result = st.session_state.get("last_result")
    if not result:
        st.markdown(
            '<div class="cc-card"><span class="cc-empty">Upload a contract in the sidebar and click '
            '"Analyze Contract" to get started.</span></div>',
            unsafe_allow_html=True,
        )
    else:
        contract_name = st.session_state.get("last_name")
        st.subheader(f"{contract_name} — {result['contract_type_guess']}")

        risk = compute_risk_score(result)
        risk_color = STATUS_COLORS[risk["status"]]
        st.markdown(
            f'<div class="cc-risk-tile" style="border-left-color:{risk_color};">'
            f'<div class="cc-risk-score" style="color:{risk_color};">{risk["score"]}</div>'
            f'<div><div class="cc-risk-label"><strong>{esc(risk["label"])}</strong></div>'
            '<div class="cc-risk-label">Heuristic triage score — not a substitute for attorney review.</div></div>'
            "</div>",
            unsafe_allow_html=True,
        )

        memo_bytes = memo.build_memo(result, contract_name, mode=mode)
        st.download_button(
            "Download Negotiation Memo (.docx)",
            data=memo_bytes,
            file_name=f"{contract_name.rsplit('.', 1)[0]}_review_memo.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        n_flagged = sum(1 for c in result["clauses"].values() if c["flagged"])
        n_not_found = sum(1 for c in result["clauses"].values() if not c["found"])
        n_standard = len(CLAUSE_TYPES) - n_flagged - n_not_found
        st.markdown(
            f'<div class="cc-run-summary">{len(CLAUSE_TYPES)} clause types reviewed · '
            f'<strong style="color:{STATUS_COLORS["critical"]};">{n_flagged} flagged</strong> · '
            f"{n_standard} standard · {n_not_found} not found</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="cc-section-label">Key Dates</div>', unsafe_allow_html=True)
        cols = st.columns(len(DATE_FIELDS))
        for col, field in zip(cols, DATE_FIELDS):
            entry = result["dates"][field]
            with col:
                if entry["found"] and entry["date"]:
                    tile = (
                        '<div class="cc-date-tile">'
                        f'<div class="cc-date-label">{esc(DATE_LABELS[field])}</div>'
                        f'<div class="cc-date-value">{esc(entry["date"])}</div>'
                        f'<div class="cc-date-quote">“{esc(entry["quote"])}”</div>'
                        "</div>"
                    )
                else:
                    tile = (
                        '<div class="cc-date-tile">'
                        f'<div class="cc-date-label">{esc(DATE_LABELS[field])}</div>'
                        '<div class="cc-empty">Not stated in contract</div>'
                        "</div>"
                    )
                st.markdown(tile, unsafe_allow_html=True)

        st.markdown('<div class="cc-section-label">Clauses</div>', unsafe_allow_html=True)

        def _priority(ct):
            c = result["clauses"][ct]
            if c["flagged"]:
                return 0
            if c["found"]:
                return 1
            return 2

        for ct in sorted(CLAUSE_TYPES, key=_priority):
            clause = result["clauses"][ct]
            body = ""
            if clause["found"]:
                body += f'<div class="cc-quote">{esc(clause["quote"])}</div>'
                body += f'<div class="cc-summary">{esc(clause.get(summary_key))}</div>'
                if clause["flagged"] and clause.get(reason_key):
                    body += f'<div class="cc-flag-box">{esc(clause.get(reason_key))}</div>'
                    if clause.get("suggested_redline"):
                        body += (
                            f'<div class="cc-redline-box"><strong>Suggested redline:</strong> '
                            f'{esc(clause["suggested_redline"])}</div>'
                        )
                accent = STATUS_COLORS["critical"] if clause["flagged"] else STATUS_COLORS["good"]
                extra_class = ""
            else:
                body += f'<div class="cc-empty">{esc(clause.get(summary_key) or "This clause type was not found in the contract.")}</div>'
                accent = STATUS_COLORS["neutral"]
                extra_class = " cc-card--muted"

            card = (
                f'<div class="cc-card{extra_class}" style="border-left: 4px solid {accent};">'
                '<div class="cc-clause-header">'
                f'<div class="cc-clause-title">{esc(CLAUSE_LABELS[ct])}</div>'
                f"{clause_status_badge(clause)}"
                "</div>"
                f"{body}"
                "</div>"
            )
            st.markdown(card, unsafe_allow_html=True)

with tab_dashboard:
    runs = storage.load_all_runs()
    rows = dashboard.build_dashboard_rows(runs)

    counts = {k: 0 for k in KPI_ORDER}
    for row in rows:
        if row["bucket"] in counts:
            counts[row["bucket"]] += 1

    kpi_cols = st.columns(4)
    for col, bucket_key in zip(kpi_cols, KPI_ORDER):
        status, _ = BUCKET_STATUS[bucket_key]
        color = STATUS_COLORS[status]
        with col:
            st.markdown(
                f'<div class="cc-kpi-tile" style="border-top-color:{color};">'
                f'<div class="cc-kpi-value" style="color:{color};">{counts[bucket_key]}</div>'
                f'<div class="cc-kpi-label">{esc(KPI_LABELS[bucket_key])}</div>'
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="cc-section-label">Ask Your Portfolio</div>', unsafe_allow_html=True)
    query = st.text_input(
        "e.g. \"which contracts have a liability cap under $10,000?\"",
        label_visibility="collapsed",
        placeholder='Ask a question across all uploaded contracts, e.g. "which contracts have no limitation of liability?"',
    )
    if st.button("Search Portfolio", disabled=not query or not runs):
        with st.spinner("Checking contracts..."):
            matches = portfolio_filter.filter_portfolio(query, runs)
        hits = [m for m in matches if m["matched"]]
        if not hits:
            st.info("No contracts matched that query.")
        else:
            for m in hits:
                st.markdown(
                    f'<div class="cc-card"><strong>{esc(m["contract_name"])}</strong>'
                    f'<div class="cc-summary">{esc(m["reason"])}</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown('<div class="cc-section-label">Upcoming Deadlines</div>', unsafe_allow_html=True)

    if not rows:
        st.markdown(
            '<div class="cc-card"><span class="cc-empty">No contracts with a renewal date or '
            "termination deadline uploaded yet.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        table_rows = ""
        for row in rows:
            status_info = BUCKET_STATUS.get(row["bucket"])
            if status_info:
                status, label = status_info
                status_cell = badge_html(label, STATUS_COLORS[status])
            elif row["days_until"] is not None:
                status_cell = f'<span class="cc-empty">{row["days_until"]} days away</span>'
            else:
                status_cell = ""
            table_rows += (
                "<tr>"
                f'<td>{esc(row["contract"])}</td>'
                f'<td>{esc(DATE_LABELS.get(row["deadline_type"], row["deadline_type"]))}</td>'
                f'<td>{esc(row["date"])}</td>'
                f"<td>{status_cell}</td>"
                "</tr>"
            )
        table = (
            '<div class="cc-card"><table class="cc-dash">'
            "<thead><tr><th>Contract</th><th>Deadline Type</th><th>Date</th><th>Status</th></tr></thead>"
            f"<tbody>{table_rows}</tbody>"
            "</table></div>"
        )
        st.markdown(table, unsafe_allow_html=True)

        due_soon_rows = [r for r in rows if r["bucket"] is not None]
        if due_soon_rows:
            st.markdown('<div class="cc-section-label">Draft a Renewal Email</div>', unsafe_allow_html=True)
            options = {
                f'{r["contract"]} — {DATE_LABELS.get(r["deadline_type"], r["deadline_type"])} ({r["date"]})': r
                for r in due_soon_rows
            }
            choice = st.selectbox("Pick a deadline to draft for", list(options.keys()))
            if choice:
                r = options[choice]
                draft = renewal_email.draft_renewal_email(r["contract"], r["deadline_type"], r["date"], r["days_until"])
                st.text_input("Subject", value=draft["subject"])
                st.text_area("Body", value=draft["body"], height=200)
                mailto = f"mailto:?subject={quote(draft['subject'])}&body={quote(draft['body'])}"
                st.link_button("Open in Email App", mailto)
                st.caption(
                    "Opens a new message in your default email app with the subject/body filled in and the "
                    "recipient left blank — add who it's going to and send it yourself."
                )

    if runs:
        st.markdown('<div class="cc-section-label">Portfolio Heat-Map</div>', unsafe_allow_html=True)
        st.caption(
            " &nbsp; ".join(
                badge_html(label, STATUS_COLORS[color])
                for label, color in [("Flagged", "critical"), ("Standard", "good"), ("Not found", "neutral")]
            ),
            unsafe_allow_html=True,
        )
        header_cells = "".join(f"<th>{esc(HEATMAP_SHORT_LABELS[ct])}</th>" for ct in CLAUSE_TYPES)
        body_rows = ""
        for run in runs:
            clauses = run.get("result", {}).get("clauses", {})
            cells = ""
            for ct in CLAUSE_TYPES:
                c = clauses.get(ct, {"found": False, "flagged": False})
                if not c.get("found"):
                    color, label = STATUS_COLORS["neutral"], "—"
                elif c.get("flagged"):
                    color, label = STATUS_COLORS["critical"], "Flag"
                else:
                    color, label = STATUS_COLORS["good"], "OK"
                cells += (
                    '<td class="cc-heat-cell">'
                    f'<span class="cc-heat-chip" style="background:{color}22;color:{color};" '
                    f'title="{esc(CLAUSE_LABELS[ct])}">{label}</span></td>'
                )
            body_rows += f"<tr><td>{esc(run.get('contract_name'))}</td>{cells}</tr>"
        heat_table = (
            '<div class="cc-card"><table class="cc-heat">'
            f"<thead><tr><th>Contract</th>{header_cells}</tr></thead>"
            f"<tbody>{body_rows}</tbody>"
            "</table></div>"
        )
        st.markdown(heat_table, unsafe_allow_html=True)
