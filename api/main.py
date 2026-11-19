"""
Step 9 -- FastAPI backend for the React frontend (replaces app.py / Streamlit).

Same five-pane flow as app.py, as HTTP:
  GET  /api/requests                       -- sample request catalogue
  GET  /api/requests/{request_id}/text      -- raw request text (email/pdf extracted)
  POST /api/requests/{request_id}/run       -- kick off decompose -> run_checks -> pack -> letter
                                                in the background, returns immediately
  GET  /api/requests/{request_id}/status    -- poll: status + step log
  GET  /api/requests/{request_id}/result    -- full bundle once status == "done"
  GET  /api/requests/{request_id}/gaps      -- gap_items.csv, optionally filtered
  GET  /api/requests/{request_id}/download/{kind} -- gap_report.xlsx / request_interpretation.md / letter docx

A run is keyed by request_id, not a fresh job id -- out/<REQ>/ is already the
one-slot-per-request-id layout run_checks.py/pack.py/letter.py use, so re-running
a request simply overwrites its slot, matching the existing CLI/Streamlit behaviour.
"""
import asyncio
import json
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd

from agent.config import DATA_DIR, OUT_DIR
from agent.decompose import decompose
from agent.letter import draft_and_validate, save_letter_docx
from agent.pack import build_pack
from agent.run_checks import run
from agent.tools import Tools

app = FastAPI(title="Audit evidence pack agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_REQUESTS = {
    "REQ-01": dict(
        request_id="REQ-01", lender_id="L001", period={"from": "2026-01-01", "to": "2026-03-31"},
        sample_file="audit_requests/REQ-01_annexure_A_sample.csv", source="audit_requests/REQ-01_email.txt",
        label="REQ-01 -- plain email (L001)", path=DATA_DIR / "audit_requests/REQ-01_email.txt", kind="txt"),
    "REQ-02": dict(
        request_id="REQ-02", lender_id="L003", period={"from": "2026-01-01", "to": "2026-06-30"},
        sample_file="audit_requests/REQ-02_annexure_A_sample.csv", source="audit_requests/REQ-02_letter.pdf",
        label="REQ-02 -- PDF letter (L003)", path=DATA_DIR / "audit_requests/REQ-02_letter.pdf", kind="pdf"),
    "REQ-03": dict(
        request_id="REQ-03", lender_id="L002", period={"from": "2026-04-01", "to": "2026-06-30"},
        sample_file="audit_requests/REQ-03_annexure_A_sample.csv", source="audit_requests/REQ-03_email.txt",
        label="REQ-03 -- vague email (L002)", path=DATA_DIR / "audit_requests/REQ-03_email.txt", kind="txt"),
}

# in-memory job state, keyed by request_id -- one audit-agent process, matches
# the single out/<REQ>/ slot each request already uses. Guarded by a lock since
# the background run and status polling happen from different threads/tasks.
_lock = threading.Lock()
_jobs = {}  # request_id -> {"status": "idle"|"running"|"done"|"error", "log": [...], "error": str|None}


def _extract_text(path: Path, kind: str) -> str:
    if kind == "pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(p.extract_text() for p in pdf.pages)
    return path.read_text()


def _job(request_id: str) -> dict:
    with _lock:
        return _jobs.setdefault(request_id, {"status": "idle", "log": [], "error": None})


def _set(request_id: str, **kw):
    with _lock:
        _jobs[request_id].update(kw)


def _append_log(request_id: str, msg: str):
    with _lock:
        _jobs[request_id]["log"].append(msg)


def _execute(request_id: str):
    job = SAMPLE_REQUESTS[request_id]
    try:
        _append_log(request_id, "Decomposing the request...")
        text = _extract_text(job["path"], job["kind"])
        decomposed = decompose(request_text=text, request_id=job["request_id"], lender_id=job["lender_id"],
                                period=job["period"], sample_file=job["sample_file"], source=job["source"])
        decomposed_path = OUT_DIR / job["request_id"] / "checks.json"
        decomposed_path.parent.mkdir(parents=True, exist_ok=True)
        decomposed_path.write_text(json.dumps(decomposed, indent=2))
        _append_log(request_id, f"Extracted {len(decomposed['checks'])} checks, "
                                 f"{len(decomposed['unsupported'])} unsupported")

        _append_log(request_id, "Running checks against the sample...")
        vdf = run(decomposed_path, tools=Tools(), verbose=False)
        _append_log(request_id, f"Tested {vdf.account_id.nunique()} accounts")

        _append_log(request_id, "Building the evidence pack...")
        pack_paths = build_pack(job["request_id"], decomposed_path)

        _append_log(request_id, "Drafting the response letter...")
        letter_result = draft_and_validate(job["request_id"], decomposed_path)
        letter_path = save_letter_docx(job["request_id"], letter_result["text"])

        with _lock:
            _jobs[request_id]["result"] = dict(
                request_id=request_id, decomposed=decomposed, pack_paths=pack_paths,
                letter=letter_result, letter_path=str(letter_path),
            )
        _append_log(request_id, "Done")
        _set(request_id, status="done")
    except Exception as e:
        _set(request_id, status="error", error=str(e))
        _append_log(request_id, f"Error: {e}")


@app.get("/api/requests")
def list_requests():
    return [{"request_id": r["request_id"], "label": r["label"], "lender_id": r["lender_id"],
              "period": r["period"]} for r in SAMPLE_REQUESTS.values()]


@app.get("/api/requests/{request_id}/text")
def request_text(request_id: str):
    job = SAMPLE_REQUESTS.get(request_id)
    if not job:
        raise HTTPException(404, "unknown request_id")
    return {"text": _extract_text(job["path"], job["kind"])}


@app.post("/api/requests/{request_id}/run", status_code=202)
def start_run(request_id: str, background_tasks: BackgroundTasks):
    if request_id not in SAMPLE_REQUESTS:
        raise HTTPException(404, "unknown request_id")
    job = _job(request_id)
    if job["status"] == "running":
        raise HTTPException(409, "a run for this request is already in progress")
    _set(request_id, status="running", log=[], error=None)
    background_tasks.add_task(_execute, request_id)
    return {"request_id": request_id, "status": "running"}


@app.get("/api/requests/{request_id}/status")
def run_status(request_id: str):
    job = _job(request_id)
    return {"status": job["status"], "log": job["log"], "error": job["error"]}


@app.get("/api/requests/{request_id}/result")
def run_result(request_id: str):
    job = _job(request_id)
    if job["status"] != "done":
        raise HTTPException(409, f"run is not done (status={job['status']})")
    result = job["result"]
    od = OUT_DIR / request_id
    summary = pd.read_csv(od / "summary.csv").to_dict("records")

    score = None
    gt_path = DATA_DIR / "ground_truth" / "ground_truth_account_check.csv"
    if gt_path.exists():
        try:
            from eval.score import score as run_score
            overall, per_check, _ = run_score(verbose=False)
            score = {"recall": float(overall.recall), "false_gap_rate": float(overall.false_gap_rate),
                     "unsupported_claims": int(overall.unsupported_claims)}
            if request_id in per_check.index.get_level_values(0):
                score["per_check"] = per_check.loc[request_id].reset_index().to_dict("records")
        except Exception as e:
            score = {"error": str(e)}

    return {
        "request_id": request_id,
        "decomposed": {"checks": result["decomposed"]["checks"], "unsupported": result["decomposed"]["unsupported"]},
        "summary": summary,
        "letter": {"text": result["letter"]["text"], "needs_human_review": result["letter"]["needs_human_review"],
                   "validation": result["letter"]["validation"]},
        "score": score,
    }


@app.get("/api/requests/{request_id}/gaps")
def gaps(request_id: str, check_type: str | None = None, severity: str | None = None):
    od = OUT_DIR / request_id
    path = od / "gap_items.csv"
    if not path.exists():
        raise HTTPException(409, "no run output yet for this request")
    df = pd.read_csv(path, dtype=str)
    if check_type:
        df = df[df.check_type == check_type]
    if severity:
        df = df[df.severity == severity]
    return df.to_dict("records")


_DOWNLOAD_FILES = {
    "gap_report": ("gap_report.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "request_interpretation": ("request_interpretation.md", "text/markdown"),
    "letter": ("response_letter_DRAFT.docx",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


@app.get("/api/requests/{request_id}/download/{kind}")
def download(request_id: str, kind: str):
    if kind not in _DOWNLOAD_FILES:
        raise HTTPException(404, "unknown download kind")
    filename, media_type = _DOWNLOAD_FILES[kind]
    path = OUT_DIR / request_id / filename
    if not path.exists():
        raise HTTPException(409, "no run output yet for this request")
    return FileResponse(path, media_type=media_type, filename=f"{request_id}_{filename}")
