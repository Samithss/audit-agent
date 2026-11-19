import { useEffect, useState } from "react"
import { api } from "./api"
import Tabs from "./components/Tabs"
import RequestPicker from "./components/RequestPicker"
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
  { id: "sample", label: "Sample requests" },
  { id: "upload", label: "Upload your own" },
  { id: "inbox", label: "Gmail inbox" },
]

export default function App() {
  const [mode, setMode] = useState("sample")
  const [requests, setRequests] = useState([])
  const [lenders, setLenders] = useState([])
  const [selected, setSelected] = useState("")
  const [text, setText] = useState("")
  const [activeRequestId, setActiveRequestId] = useState(null)
  const [run, setRun] = useState({ status: "idle", log: [], error: null })
  const [result, setResult] = useState(null)
  const [gaps, setGaps] = useState([])
  const [loadError, setLoadError] = useState("")
  const [inboxBanner, setInboxBanner] = useState(null)

  useEffect(() => {
    api.listRequests().then((rs) => {
      setRequests(rs)
      if (rs.length) setSelected(rs[0].request_id)
    }).catch((e) => setLoadError(e.message))
    api.listLenders().then(setLenders).catch((e) => setLoadError(e.message))

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

  // sample mode: selecting a request shows its text and whatever status it already has
  useEffect(() => {
    if (mode !== "sample" || !selected) return
    setActiveRequestId(selected)
    setResult(null)
    setGaps([])
    api.getText(selected).then((r) => setText(r.text)).catch(() => setText(""))
    api.getStatus(selected).then((s) => {
      setRun(s)
      if (s.status === "done") loadResult(selected)
    })
  }, [mode, selected])

  async function loadResult(id) {
    try {
      const [res, g] = await Promise.all([api.getResult(id), api.getGaps(id)])
      setResult(res)
      setGaps(g)
    } catch (e) {
      setLoadError(e.message)
    }
  }

  async function onRunSample() {
    setLoadError("")
    setResult(null)
    try {
      await api.startRun(selected)
      setRun({ status: "running", log: [], error: null })
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
    <div className="app">
      <header className="app-header">
        <h1>Audit evidence pack agent</h1>
        <p className="muted">CO-04 -- CreditNirvana Agentathon</p>
      </header>

      {loadError && <p className="error">{loadError}</p>}
      {inboxBanner && (
        <p className={`badge ${inboxBanner.kind === "success" ? "success" : "warning"}`}>{inboxBanner.text}</p>
      )}

      <Tabs tabs={TABS} active={mode} onChange={setMode} />

      {mode === "sample" && (
        <RequestPicker
          requests={requests}
          selected={selected}
          onSelect={setSelected}
          text={text}
          running={running}
          onRun={onRunSample}
        />
      )}
      {mode === "upload" && (
        <UploadPane lenders={lenders} running={running} onStarted={onRunStarted} onError={setLoadError} />
      )}
      {mode === "inbox" && (
        <InboxPane lenders={lenders} running={running} onStarted={onRunStarted} onError={setLoadError} />
      )}

      <RunLog log={run.log} status={run.status} error={run.error} />

      {result ? (
        <>
          <ChecksPane decomposed={result.decomposed} />
          <SummaryPane summary={result.summary} />
          <GapsPane gaps={gaps} />
          <ScorecardPane requestId={activeRequestId} score={result.score} letter={result.letter} />
          <ReplyPane requestId={activeRequestId} letter={result.letter} replyTo={result.reply_to} replied={result.replied} />
        </>
      ) : (
        mode === "sample" && !running && activeRequestId && (
          <p className="muted center">Click &ldquo;Run the agent&rdquo; above to process this request.</p>
        )
      )}
    </div>
  )
}
