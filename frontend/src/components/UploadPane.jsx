import { useState } from "react"
import { api } from "../api"
import LenderPeriodFields from "./LenderPeriodFields"

export default function UploadPane({ lenders, running, onStarted, onError }) {
  const [inputMode, setInputMode] = useState("pdf") // "pdf" | "text"
  const [file, setFile] = useState(null)
  const [text, setText] = useState("")
  const [lenderId, setLenderId] = useState("")
  const [periodFrom, setPeriodFrom] = useState("")
  const [periodTo, setPeriodTo] = useState("")

  const canRun = lenderId && periodFrom && periodTo && (inputMode === "pdf" ? file : text.trim())

  async function submit() {
    const fd = new FormData()
    fd.set("lender_id", lenderId)
    fd.set("period_from", periodFrom)
    fd.set("period_to", periodTo)
    if (inputMode === "pdf") fd.set("file", file)
    else fd.set("text", text)
    try {
      const { request_id } = await api.startCustomRun(fd)
      onStarted(request_id)
    } catch (e) {
      onError(e.message)
    }
  }

  return (
    <section className="pane">
      <h2>Upload your own request</h2>
      <div className="row">
        <button className={inputMode === "pdf" ? "toggle active" : "toggle"} onClick={() => setInputMode("pdf")}>
          PDF file
        </button>
        <button className={inputMode === "text" ? "toggle active" : "toggle"} onClick={() => setInputMode("text")}>
          Paste email text
        </button>
      </div>

      {inputMode === "pdf" ? (
        <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} disabled={running} />
      ) : (
        <textarea
          className="paste-box"
          placeholder="Paste the audit request email's text here..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={running}
          rows={8}
        />
      )}

      <p className="muted" style={{ marginTop: 10 }}>
        The uploaded letter's content decides which checks to run; "Test against" picks which lender's sampled
        accounts to run them on (the dataset only has real account data for these 3 lenders).
      </p>
      <LenderPeriodFields lenders={lenders} lenderId={lenderId} setLenderId={setLenderId}
        periodFrom={periodFrom} setPeriodFrom={setPeriodFrom} periodTo={periodTo} setPeriodTo={setPeriodTo} />

      <button className="primary" onClick={submit} disabled={!canRun || running}>
        {running ? "Running..." : "Run the agent"}
      </button>
    </section>
  )
}
