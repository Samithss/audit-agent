"""
Step 9/10 -- FastAPI backend for the React frontend (replaces app.py / Streamlit).

Three ways to feed the pipeline, all converging on the same background-job
machinery (decompose -> run_checks -> pack -> letter), keyed by request_id:

  1. Sample requests       -- the 3 canned REQ-01/02/03 demo requests.
       GET  /api/requests
       GET  /api/requests/{id}/text
       POST /api/requests/{id}/run

  2. Upload your own        -- a PDF file or pasted text, plus which lender's
     sample to test against (the uploaded letter's content decides WHAT to
     check; the synthetic dataset only has real account data for 3 lenders,
     so that still has to be picked explicitly).
       GET  /api/lenders
       POST /api/custom/run

  3. Gmail inbox             -- a real mailbox, connected once via OAuth.
       GET  /api/inbox/status
       GET  /api/inbox/auth-url
       GET  /api/inbox/oauth/callback
       GET  /api/inbox/messages
       POST /api/inbox/messages/{message_id}/run

Shared, once a job is started under some request_id:
  GET /api/requests/{id}/status             -- poll: status + step log
  GET /api/requests/{id}/result              -- full bundle once status == "done"
  GET /api/requests/{id}/gaps                -- gap_items.csv, optionally filtered
  GET /api/requests/{id}/download/{kind}     -- gap_report.xlsx / request_interpretation.md / letter docx

A run is keyed by request_id, not a fresh job id -- out/<REQ>/ is already the
one-slot-per-request-id layout run_checks.py/pack.py/letter.py use, so
re-running a request simply overwrites its slot. Custom/Gmail runs get a
generated request_id (CUSTOM-xxxxxxxx / GMAIL-<message_id>) so they land in
their own out/ slot too, never colliding with the sample requests.
"""
import json
import threading
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import pandas as pd

from agent import gmail_client
from agent.config import DATA_DIR, FRONTEND_URL, OUT_DIR
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

# Which lenders have real sampled-account data to test against -- independent
# of where the request TEXT comes from (sample picker / upload / Gmail).
LENDER_SAMPLES = {
    "L001": "audit_requests/REQ-01_annexure_A_sample.csv",
    "L002": "audit_requests/REQ-03_annexure_A_sample.csv",
    "L003": "audit_requests/REQ-02_annexure_A_sample.csv",
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


def _execute(request_id: str, text: str, lender_id: str, period: dict, sample_file: str, source: str):
    """The one pipeline every entry point (sample picker / upload / Gmail)
    ultimately calls, just with a different source for `text`."""
    try:
        _append_log(request_id, "Decomposing the request...")
        decomposed = decompose(request_text=text, request_id=request_id, lender_id=lender_id,
                                period=period, sample_file=sample_file, source=source)
        decomposed_path = OUT_DIR / request_id / "checks.json"
        decomposed_path.parent.mkdir(parents=True, exist_ok=True)
        decomposed_path.write_text(json.dumps(decomposed, indent=2))
        _append_log(request_id, f"Extracted {len(decomposed['checks'])} checks, "
                                 f"{len(decomposed['unsupported'])} unsupported")

        _append_log(request_id, "Running checks against the sample...")
        vdf = run(decomposed_path, tools=Tools(), verbose=False)
        _append_log(request_id, f"Tested {vdf.account_id.nunique()} accounts")

        _append_log(request_id, "Building the evidence pack...")
        pack_paths = build_pack(request_id, decomposed_path)

        _append_log(request_id, "Drafting the response letter...")
        letter_result = draft_and_validate(request_id, decomposed_path)
        letter_path = save_letter_docx(request_id, letter_result["text"])

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


def _start(request_id: str, background_tasks: BackgroundTasks, **kw):
    job = _job(request_id)
    if job["status"] == "running":
        raise HTTPException(409, "a run for this request is already in progress")
    _set(request_id, status="running", log=[], error=None)
    background_tasks.add_task(_execute, request_id, **kw)


# ---------------------------------------------------------------- 1. sample requests

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
def start_sample_run(request_id: str, background_tasks: BackgroundTasks):
    job = SAMPLE_REQUESTS.get(request_id)
    if not job:
        raise HTTPException(404, "unknown request_id")
    text = _extract_text(job["path"], job["kind"])
    _start(request_id, background_tasks, text=text, lender_id=job["lender_id"], period=job["period"],
           sample_file=job["sample_file"], source=job["source"])
    return {"request_id": request_id, "status": "running"}


# ---------------------------------------------------------------- 2. upload your own

@app.get("/api/lenders")
def list_lenders():
    return [{"lender_id": lid, "sample_file": sf} for lid, sf in LENDER_SAMPLES.items()]


@app.post("/api/custom/run", status_code=202)
async def start_custom_run(
    background_tasks: BackgroundTasks,
    lender_id: str = Form(...),
    period_from: str = Form(...),
    period_to: str = Form(...),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    if lender_id not in LENDER_SAMPLES:
        raise HTTPException(400, f"unknown lender_id -- must be one of {list(LENDER_SAMPLES)}")
    if not file and not (text and text.strip()):
        raise HTTPException(400, "provide either a PDF file or pasted text")

    if file:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "only .pdf uploads are supported (use the text box for plain text)")
        import io
        import pdfplumber
        body = await file.read()
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            request_text_ = "\n".join(p.extract_text() or "" for p in pdf.pages)
        source = f"upload:{file.filename}"
    else:
        request_text_ = text
        source = "upload:pasted-text"

    request_id = f"CUSTOM-{uuid.uuid4().hex[:8]}"
    _start(request_id, background_tasks, text=request_text_, lender_id=lender_id,
           period={"from": period_from, "to": period_to}, sample_file=LENDER_SAMPLES[lender_id], source=source)
    return {"request_id": request_id, "status": "running"}


# ---------------------------------------------------------------- 3. Gmail inbox

@app.get("/api/inbox/status")
def inbox_status():
    if not gmail_client.is_configured():
        return {"configured": False, "connected": False}
    return {"configured": True, "connected": gmail_client.is_connected()}


@app.get("/api/inbox/auth-url")
def inbox_auth_url():
    if not gmail_client.is_configured():
        raise HTTPException(409, "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are not set -- see README.md")
    return {"url": gmail_client.build_auth_url()}


@app.get("/api/inbox/oauth/callback")
def inbox_oauth_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/?inbox_error={error}")
    try:
        gmail_client.exchange_code(code)
    except Exception as e:
        return RedirectResponse(f"{FRONTEND_URL}/?inbox_error={e}")
    return RedirectResponse(f"{FRONTEND_URL}/?inbox=connected")


@app.get("/api/inbox/messages")
def inbox_messages():
    if not gmail_client.is_connected():
        raise HTTPException(409, "Gmail is not connected -- call /api/inbox/auth-url first")
    return gmail_client.list_candidate_messages()


@app.post("/api/inbox/messages/{message_id}/run", status_code=202)
def start_inbox_run(message_id: str, background_tasks: BackgroundTasks,
                     lender_id: str = Form(...), period_from: str = Form(...), period_to: str = Form(...)):
    if lender_id not in LENDER_SAMPLES:
        raise HTTPException(400, f"unknown lender_id -- must be one of {list(LENDER_SAMPLES)}")
    text = gmail_client.get_message_text(message_id)
    request_id = f"GMAIL-{message_id}"
    _start(request_id, background_tasks, text=text, lender_id=lender_id,
           period={"from": period_from, "to": period_to}, sample_file=LENDER_SAMPLES[lender_id],
           source=f"gmail:{message_id}")
    return {"request_id": request_id, "status": "running"}


# ---------------------------------------------------------------- shared: status/result/gaps/downloads

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
