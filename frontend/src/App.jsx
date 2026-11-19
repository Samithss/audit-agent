import { useEffect, useState } from "react"
import { api } from "./api"
import RequestPicker from "./components/RequestPicker"
import RunLog from "./components/RunLog"
import ChecksPane from "./components/ChecksPane"
import SummaryPane from "./components/SummaryPane"
import GapsPane from "./components/GapsPane"
import ScorecardPane from "./components/ScorecardPane"
import "./App.css"

export default function App() {
  const [requests, setRequests] = useState([])
  const [selected, setSelected] = useState("")
  const [text, setText] = useState("")
  const [run, setRun] = useState({ status: "idle", log: [], error: null })
  const [result, setResult] = useState(null)
  const [gaps, setGaps] = useState([])
  const [loadError, setLoadError] = useState("")

  useEffect(() => {
    api.listRequests().then((rs) => {
      setRequests(rs)
      if (rs.length) setSelected(rs[0].request_id)
    }).catch((e) => setLoadError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    setResult(null)
    setGaps([])
    api.getText(selected).then((r) => setText(r.text)).catch(() => setText(""))
    api.getStatus(selected).then((s) => {
      setRun(s)
      if (s.status === "done") loadResult(selected)
    })
  }, [selected])

  async function loadResult(id) {
    try {
      const [res, g] = await Promise.all([api.getResult(id), api.getGaps(id)])
      setResult(res)
      setGaps(g)
    } catch (e) {
      setLoadError(e.message)
    }
  }

  async function onRun() {
    setLoadError("")
    setResult(null)
    try {
      await api.startRun(selected)
      setRun({ status: "running", log: [], error: null })
    } catch (e) {
      setLoadError(e.message)
    }
  }

  useEffect(() => {
    if (run.status !== "running") return
    const t = setInterval(async () => {
      const s = await api.getStatus(selected)
      setRun(s)
      if (s.status === "done") {
        clearInterval(t)
        loadResult(selected)
      } else if (s.status === "error") {
        clearInterval(t)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [run.status, selected])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Audit evidence pack agent</h1>
        <p className="muted">CO-04 -- CreditNirvana Agentathon</p>
      </header>

      {loadError && <p className="error">{loadError}</p>}

      <RequestPicker
        requests={requests}
        selected={selected}
        onSelect={setSelected}
        text={text}
        running={run.status === "running"}
        onRun={onRun}
      />

      <RunLog log={run.log} status={run.status} error={run.error} />

      {result ? (
        <>
          <ChecksPane decomposed={result.decomposed} />
          <SummaryPane summary={result.summary} />
          <GapsPane gaps={gaps} />
          <ScorecardPane requestId={selected} score={result.score} letter={result.letter} />
        </>
      ) : (
        run.status !== "running" && <p className="muted center">Click &ldquo;Run the agent&rdquo; above to process this request.</p>
      )}
    </div>
  )
}
