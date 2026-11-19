import { useEffect, useState } from "react"
import { api } from "../api"
import PeriodFields from "./PeriodFields"
import AccountsField from "./AccountsField"

function MessageRow({ msg, running, onStarted, onError }) {
  const [accountsFile, setAccountsFile] = useState(null)
  const [periodFrom, setPeriodFrom] = useState("")
  const [periodTo, setPeriodTo] = useState("")
  const [open, setOpen] = useState(false)
  const canRun = accountsFile && !!periodFrom === !!periodTo

  async function submit() {
    const fd = new FormData()
    if (accountsFile) fd.set("accounts_file", accountsFile)
    if (periodFrom) fd.set("period_from", periodFrom)
    if (periodTo) fd.set("period_to", periodTo)
    try {
      const { request_id } = await api.startInboxRun(msg.message_id, fd)
      onStarted(request_id)
    } catch (e) {
      onError(e.message)
    }
  }

  return (
    <div className="inbox-row">
      <div className="inbox-row-main" onClick={() => setOpen((v) => !v)}>
        <div>
          <strong>{msg.subject}</strong>
          <p className="muted small">{msg.from} -- {msg.date}</p>
          <p className="muted small">{msg.snippet}</p>
        </div>
        {msg.has_pdf && <span className="badge-pill">PDF attached</span>}
      </div>
      {open && (
        <div className="inbox-row-run">
          <AccountsField file={accountsFile} setFile={setAccountsFile} disabled={running} />
          <PeriodFields
        periodFrom={periodFrom} setPeriodFrom={setPeriodFrom} periodTo={periodTo} setPeriodTo={setPeriodTo} />
          <button className="primary" onClick={submit} disabled={!canRun || running}>
            {running ? "Running..." : "Run agent on this email"}
          </button>
        </div>
      )}
    </div>
  )
}

export default function InboxPane({ running, onStarted, onError }) {
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.inboxStatus().then(setStatus).catch((e) => onError(e.message))
  }, [])

  async function connect() {
    try {
      const { url } = await api.inboxAuthUrl()
      window.location.href = url
    } catch (e) {
      onError(e.message)
    }
  }

  async function refresh() {
    setLoading(true)
    try {
      setMessages(await api.inboxMessages())
    } catch (e) {
      onError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (!status) return <section className="pane"><p className="muted">Checking inbox connection...</p></section>

  if (!status.configured) {
    return (
      <section className="pane">
        <h2>Gmail inbox</h2>
        <p className="badge warning">
          Not configured -- set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the backend's .env (see README.md
          "Gmail inbox setup") to enable this.
        </p>
      </section>
    )
  }

  if (!status.connected) {
    return (
      <section className="pane">
        <h2>Gmail inbox</h2>
        <p className="muted">Connect a mailbox to pull in real audit-request emails.</p>
        <button className="primary" onClick={connect}>Connect Gmail</button>
      </section>
    )
  }

  return (
    <section className="pane">
      <h2>Gmail inbox</h2>
      <div className="row">
        <span className="badge success">Connected</span>
        <button onClick={refresh} disabled={loading}>{loading ? "Loading..." : "Refresh inbox"}</button>
      </div>
      {messages === null ? (
        <p className="muted">Click "Refresh inbox" to list candidate audit-request emails.</p>
      ) : messages.length === 0 ? (
        <p className="muted">No matching emails found.</p>
      ) : (
        <div className="inbox-list">
          {messages.map((m) => (
            <MessageRow key={m.message_id} msg={m} running={running} onStarted={onStarted} onError={onError} />
          ))}
        </div>
      )}
    </section>
  )
}
