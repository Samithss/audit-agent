import { useEffect, useState } from "react"
import { api } from "./api"
import Tabs from "./components/Tabs"
import Overview from "./components/Overview"
import UploadPane from "./components/UploadPane"
import InboxPane from "./components/InboxPane"
import RunLog from "./components/RunLog"
import ChecksPane from "./components/ChecksPane"
import SummaryPane from "./components/SummaryPane"
import GapsPane from "./components/GapsPane"
import ScorecardPane from "./components/ScorecardPane"
import ReplyPane from "./components/ReplyPane"
import "./App.css"

const TABS = [
  { id: "upload", label: "Upload your own" },
  { id: "inbox", label: "Gmail inbox" },
]

export default function App() {
  const [mode, setMode] = useState("upload")
  const [activeRequestId, setActiveRequestId] = useState(null)
  const [run, setRun] = useState({ status: "idle", log: [], error: null })
  const [result, setResult] = useState(null)
  const [gaps, setGaps] = useState([])
  const [loadError, setLoadError] = useState("")
  const [inboxBanner, setInboxBanner] = useState(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get("inbox") === "connected") {
      setInboxBanner({ kind: "success", text: "Gmail connected." })
      setMode("inbox")
    } else if (params.get("inbox_error")) {
      setInboxBanner({ kind: "error", text: `Gmail connection failed: ${params.get("inbox_error")}` })
      setMode("inbox")
    }
    if (params.has("inbox") || params.has("inbox_error")) {
      window.history.replaceState({}, "", window.location.pathname)
    }
  }, [])

  async function loadResult(id) {
    try {
      const [res, g] = await Promise.all([api.getResult(id), api.getGaps(id)])
      setResult(res)
      setGaps(g)
    } catch (e) {
      setLoadError(e.message)
    }
  }

  function onRunStarted(requestId) {
    setLoadError("")
    setResult(null)
    setGaps([])
    setActiveRequestId(requestId)
    setRun({ status: "running", log: [], error: null })
  }

  // Jump straight to an already-finished (or still-running) Gmail run instead
  // of starting a new one -- used when clicking a NEEDS_REVIEW/REPLIED/ERROR
  // row in the inbox list.
  async function onViewExisting(requestId) {
    setLoadError("")
    setResult(null)
    setGaps([])
    setActiveRequestId(requestId)
    try {
      const s = await api.getStatus(requestId)
      setRun(s)
      // Try the result regardless of the in-process status: after an API
      // restart the job is "idle" in memory, but /result rebuilds it from
      // disk + audit.run_results. Only a still-running job has nothing yet.
      if (s.status !== "running") loadResult(requestId)
    } catch (e) {
      setLoadError(e.message)
    }
  }

  useEffect(() => {
    if (run.status !== "running" || !activeRequestId) return
    const t = setInterval(async () => {
      const s = await api.getStatus(activeRequestId)
      setRun(s)
      if (s.status === "done") {
        clearInterval(t)
        loadResult(activeRequestId)
      } else if (s.status === "error") {
        clearInterval(t)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [run.status, activeRequestId])

  const running = run.status === "running"

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <div className="brand-mark">A</div>
            <div>
              <h1>Audit evidence pack agent</h1>
              <p>Turn an audit request into a tested, evidenced response</p>
            </div>
          </div>
          <Tabs tabs={TABS} active={mode} onChange={setMode} />
        </div>
      </header>

      <div className="app">
        {loadError && <p className="error">{loadError}</p>}
        {inboxBanner && (
          <p className={`badge ${inboxBanner.kind === "success" ? "success" : "warning"}`}>{inboxBanner.text}</p>
        )}

        {mode === "upload" && (
          <UploadPane running={running} onStarted={onRunStarted} onError={setLoadError} />
        )}
        {mode === "inbox" && (
          <InboxPane running={running} onStarted={onRunStarted} onView={onViewExisting} onError={setLoadError} />
        )}

        <RunLog log={run.log} status={run.status} error={run.error} />

        {result && (
          <>
            <Overview requestId={activeRequestId} summary={result.summary} checks={result.decomposed.checks} />
            <ChecksPane decomposed={result.decomposed} />
            <SummaryPane summary={result.summary} />
            <GapsPane requestId={activeRequestId} gaps={gaps} />
            <ScorecardPane score={result.score} letter={result.letter} />
            <ReplyPane key={activeRequestId} requestId={activeRequestId} letter={result.letter}
                       replyTo={result.reply_to} replied={result.replied} />
          </>
        )}
      </div>
    </>
  )
}
