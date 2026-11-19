import { useEffect, useState } from "react"
import { api } from "../api"
import PeriodFields from "./PeriodFields"
import AccountsField from "./AccountsField"
import GuidelinePicker from "./GuidelinePicker"

export default function UploadPane({ running, onStarted, onError }) {
  const [file, setFile] = useState(null)
  const [text, setText] = useState("")
  const [accountsFile, setAccountsFile] = useState(null)
  const [periodFrom, setPeriodFrom] = useState("")
  const [periodTo, setPeriodTo] = useState("")
  const [guidelines, setGuidelines] = useState([])
  const [picked, setPicked] = useState([])

  useEffect(() => {
    api.listGuidelines().then(setGuidelines).catch((e) => onError(e.message))
  }, [])

  const hasText = text.trim().length > 0
  // Request source: a file OR pasted text, never both.
  const hasRequest = !!file || hasText
  // With no request text, the guidelines are the whole request, and the dates must be entered.
  const canRun = (hasRequest || picked.length > 0) && !!periodFrom === !!periodTo &&
    (hasRequest || (!!periodFrom && !!accountsFile))

  async function submit() {
    const fd = new FormData()
    if (accountsFile) fd.set("accounts_file", accountsFile)
    if (periodFrom) fd.set("period_from", periodFrom)
    if (periodTo) fd.set("period_to", periodTo)
    if (picked.length) fd.set("guideline_ids", picked.join(","))
    if (file) fd.set("file", file)
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

      <div className="field">
        <span>Request file</span>
        <input
          type="file"
          key={file ? "f" : "nof"}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={running || hasText}
        />
        <p className="muted small">
          PDF, Word (.docx/.doc), Excel, email (.eml), HTML, CSV or any text file.
          {hasText && " Clear the pasted text to upload a file."}
        </p>
        {file && (
          <button className="toggle" onClick={() => setFile(null)} disabled={running}>Remove file</button>
        )}
      </div>

      <p className="muted small" style={{ textAlign: "center", margin: "6px 0" }}>— or —</p>

      <textarea
        className="paste-box"
        placeholder={file ? "Remove the uploaded file to paste text instead" : "Paste the audit request email's text here..."}
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={running || !!file}
        rows={8}
      />

      <p className="muted" style={{ marginTop: 10 }}>
        The request's content decides which checks to run. Accounts come from the account list you attach, or,
        if you don't attach one, from the account ids named in the request itself (e.g. ACC100001).
      </p>
      <AccountsField file={accountsFile} setFile={setAccountsFile} disabled={running} />

      <GuidelinePicker guidelines={guidelines} picked={picked} setPicked={setPicked} disabled={running} />

      <PeriodFields
        periodFrom={periodFrom} setPeriodFrom={setPeriodFrom} periodTo={periodTo} setPeriodTo={setPeriodTo} />

      <button className="primary" onClick={submit} disabled={!canRun || running}>
        {running ? "Running..." : "Run the agent"}
      </button>
    </section>
  )
}
