"""
Step 8 -- Streamlit demo. Five panes: drop the request, checks extracted, live
run, gap table (with an evidence drawer), scorecard. Everything expensive
(decompose, run_checks, letter) is cached in st.session_state so clicking around
the UI doesn't re-trigger an LLM call.

    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from agent.config import DATA_DIR, OUT_DIR
from agent.decompose import decompose
from agent.letter import draft_and_validate, save_letter_docx
from agent.pack import build_pack
from agent.run_checks import run
from agent.tools import Tools

st.set_page_config(page_title="Audit evidence pack agent", layout="wide")
st.title("Audit evidence pack agent")

SAMPLE_REQUESTS = {
    "REQ-01 -- plain email (L001)": dict(
        request_id="REQ-01", lender_id="L001", period={"from": "2026-01-01", "to": "2026-03-31"},
        sample_file="audit_requests/REQ-01_annexure_A_sample.csv", source="audit_requests/REQ-01_email.txt",
        path=DATA_DIR / "audit_requests/REQ-01_email.txt", kind="txt"),
    "REQ-02 -- PDF letter (L003)": dict(
        request_id="REQ-02", lender_id="L003", period={"from": "2026-01-01", "to": "2026-06-30"},
        sample_file="audit_requests/REQ-02_annexure_A_sample.csv", source="audit_requests/REQ-02_letter.pdf",
        path=DATA_DIR / "audit_requests/REQ-02_letter.pdf", kind="pdf"),
    "REQ-03 -- vague email (L002)": dict(
        request_id="REQ-03", lender_id="L002", period={"from": "2026-04-01", "to": "2026-06-30"},
        sample_file="audit_requests/REQ-03_annexure_A_sample.csv", source="audit_requests/REQ-03_email.txt",
        path=DATA_DIR / "audit_requests/REQ-03_email.txt", kind="txt"),
}


def extract_text(path: Path, kind: str) -> str:
    if kind == "pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(p.extract_text() for p in pdf.pages)
    return path.read_text()


# ---------------------------------------------------------------- Pane 1: drop the request
st.header("1. Drop the request")
choice = st.selectbox("Pick a request", list(SAMPLE_REQUESTS.keys()))
job = SAMPLE_REQUESTS[choice]
text = extract_text(job["path"], job["kind"])
with st.expander("Raw request text"):
    st.text(text)

run_clicked = st.button("Run the agent", type="primary")

if run_clicked:
    with st.status("Running...", expanded=True) as status:
        status.write("Decomposing the request...")
        decomposed = decompose(request_text=text, request_id=job["request_id"], lender_id=job["lender_id"],
                                period=job["period"], sample_file=job["sample_file"], source=job["source"])
        decomposed_path = OUT_DIR / job["request_id"] / "checks.json"
        decomposed_path.parent.mkdir(parents=True, exist_ok=True)
        decomposed_path.write_text(json.dumps(decomposed, indent=2))
        status.write(f"Extracted {len(decomposed['checks'])} checks, "
                     f"{len(decomposed['unsupported'])} unsupported")

        status.write("Running checks against the sample...")
        vdf = run(decomposed_path, tools=Tools(), verbose=False)
        status.write(f"Tested {vdf.account_id.nunique()} accounts")

        status.write("Building the evidence pack...")
        pack_paths = build_pack(job["request_id"], decomposed_path)

        status.write("Drafting the response letter...")
        letter_result = draft_and_validate(job["request_id"], decomposed_path)
        letter_path = save_letter_docx(job["request_id"], letter_result["text"])

        status.update(label="Done", state="complete")

    st.session_state["result"] = dict(
        request_id=job["request_id"], decomposed=decomposed,
        pack_paths=pack_paths, letter=letter_result, letter_path=str(letter_path),
    )

result = st.session_state.get("result")
if not result or result["request_id"] != job["request_id"]:
    st.info("Click 'Run the agent' above to process this request.")
    st.stop()

decomposed = result["decomposed"]
rid = result["request_id"]
od = OUT_DIR / rid

# ---------------------------------------------------------------- Pane 2: checks extracted
st.header("2. Checks extracted")
c1, c2 = st.columns(2)
with c1:
    st.subheader(f"Checks ({len(decomposed['checks'])})")
    for c in decomposed["checks"]:
        st.markdown(f"**{c['check_id']} -- {c['check_type']}**")
        st.caption(f'"{c["source_text"]}"')
with c2:
    st.subheader(f"Unsupported -- reported, not dropped ({len(decomposed['unsupported'])})")
    if not decomposed["unsupported"]:
        st.success("Every requirement in the request mapped to a known check.")
    for c in decomposed["unsupported"]:
        st.warning(f'"{c["source_text"]}"')

# ---------------------------------------------------------------- Pane 3: run summary
st.header("3. Run summary")
summary = pd.read_csv(od / "summary.csv")
st.dataframe(summary, use_container_width=True)

# ---------------------------------------------------------------- Pane 4: gap table + evidence drawer
st.header("4. Gap table")
gaps = pd.read_csv(od / "gap_items.csv")
fc1, fc2 = st.columns(2)
check_filter = fc1.multiselect("Check type", sorted(gaps.check_type.unique()))
severity_filter = fc2.multiselect("Severity", sorted(gaps.severity.unique()))
filtered = gaps
if check_filter:
    filtered = filtered[filtered.check_type.isin(check_filter)]
if severity_filter:
    filtered = filtered[filtered.severity.isin(severity_filter)]
st.dataframe(filtered, use_container_width=True, height=250)

st.subheader("Evidence drawer")
if len(filtered):
    idx = st.selectbox("Inspect a gap", filtered.index,
                        format_func=lambda i: f"{filtered.loc[i, 'account_id']} -- {filtered.loc[i, 'gap_type']}")
    row = filtered.loc[idx]
    st.json({
        "account_id": row.account_id, "check_type": row.check_type, "gap_type": row.gap_type,
        "severity": row.severity, "record_ids": row.record_ids, "detail": row.detail,
    })
else:
    st.caption("No gaps match the current filter.")

# ---------------------------------------------------------------- Pane 5: scorecard + letter + downloads
st.header("5. Scorecard")
gt_path = DATA_DIR / "ground_truth" / "ground_truth_account_check.csv"
if gt_path.exists():
    try:
        from eval.score import score as run_score
        overall, per_check, _ = run_score(verbose=False)
        this_req = per_check.loc[rid] if rid in per_check.index.get_level_values(0) else None
        m1, m2, m3 = st.columns(3)
        m1.metric("Gap recall (all runs in out/)", f"{overall.recall:.1%}", help="target >= 95%")
        m2.metric("False gap rate", f"{overall.false_gap_rate:.1%}", help="target < 5%")
        m3.metric("Unevidenced claims", int(overall.unsupported_claims), help="target 0")
        if this_req is not None:
            st.caption(f"Per-check breakdown for {rid}:")
            st.dataframe(this_req.reset_index(), use_container_width=True)
    except Exception as e:
        st.caption(f"Scoring unavailable: {e}")

st.header("Draft letter")
if result["letter"]["needs_human_review"]:
    st.error("Needs human review: " + "; ".join(result["letter"]["validation"]["reasons"]))
else:
    st.success("Validator passed -- every claim cites the summary, no softening language, DRAFT disclaimer present.")
st.text(result["letter"]["text"])

st.header("Downloads")
d1, d2, d3 = st.columns(3)
with open(result["pack_paths"]["gap_report"], "rb") as f:
    d1.download_button("gap_report.xlsx", f, file_name=f"{rid}_gap_report.xlsx")
with open(result["pack_paths"]["request_interpretation"], "rb") as f:
    d2.download_button("request_interpretation.md", f, file_name=f"{rid}_request_interpretation.md")
with open(result["letter_path"], "rb") as f:
    d3.download_button("response_letter_DRAFT.docx", f, file_name=f"{rid}_response_letter_DRAFT.docx")
