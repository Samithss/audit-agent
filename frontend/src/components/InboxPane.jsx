import { useEffect, useState } from "react"
import { api } from "../api"
import PeriodFields from "./PeriodFields"
import AccountsField from "./AccountsField"

const STATUS_CHIP = {
  NEW: { label: "New", cls: "chip-neutral" },
  PROCESSING: { label: "Processing...", cls: "chip-processing" },
  NEEDS_REVIEW: { label: "Needs review", cls: "chip-warning" },
  ERROR: { label: "Error", cls: "chip-error" },
  REPLIED: { label: "Replied", cls: "chip-success" },
}

function StatusChip({ status }) {
  const chip = STATUS_CHIP[status] || STATUS_CHIP.NEW
  return <span className={`chip ${chip.cls}`}>{chip.label}</span>
}

function MessageRow({ msg, running, onStarted, onView, onError }) {
  const [accountsFile, setAccountsFile] = useState(null)
  const [periodFrom, setPeriodFrom] = useState("")
  const [periodTo, setPeriodTo] = useState("")
  const [open, setOpen] = useState(false)
  // No account list needed if the email body itself names real account ids --
  // the backend falls back to scanning the text for them. Just keep the period
  // fields paired (both or neither); let the server reject it if there's
  // genuinely nothing to test against.
  const canRun = !!periodFrom === !!periodTo
  const alreadyRan = ["NEEDS_REVIEW", "ERROR", "REPLIED"].includes(msg.status)

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
    <div className={`inbox-row ${open ? "open" : ""}`}>
      <div className="inbox-row-main" onClick={() => setOpen((v) => !v)}>
        <div>
          <span className="inbox-subject">{msg.subject}</span>
          <p className="muted small">{msg.from} -- {msg.date}</p>
          <p className="muted small">{msg.snippet}</p>
          {msg.is_audit_request !== null && msg.is_audit_request !== undefined && (
            <p className="muted small">{Math.round(msg.confidence * 100)}% likely an audit request</p>
          )}
        </div>
        <div className="inbox-row-badges">
          {msg.has_pdf && <span className="badge-pill">PDF attached</span>}
          <StatusChip status={msg.status} />
        </div>
      </div>
      {open && (
        <div className="inbox-row-run">
          {alreadyRan && msg.request_id && (
            <button onClick={() => onView(msg.request_id)} style={{ marginBottom: 10 }}>
              {msg.status === "ERROR" ? "View error log" : "View result"}
            </button>
          )}
          <p className="muted small">
            Optional -- leave blank if the email itself names the account ids (e.g. ACC100001); only attach a
            list to test a different set.
          </p>
          <AccountsField file={accountsFile} setFile={setAccountsFile} disabled={running} />
          <PeriodFields
        periodFrom={periodFrom} setPeriodFrom={setPeriodFrom} periodTo={periodTo} setPeriodTo={setPeriodTo} />
          <button className="primary" onClick={submit} disabled={!canRun || running}>
            {running ? "Running..." : alreadyRan ? "Run again" : "Run agent on this email"}
          </button>
        </div>
      )}
    </div>
  )
}

const FILTERS = [
  { key: "ALL", label: "All" },
  { key: "NEW", label: "New" },
  { key: "NEEDS_REVIEW", label: "Needs review" },
  { key: "REPLIED", label: "Replied" },
]

export default function InboxPane({ running, onStarted, onView, onError }) {
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState(null)
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState("ALL")

  // Opening the tab reads the saved list from the database -- no Gmail call.
  useEffect(() => {
    api.inboxStatus().then((st) => {
      setStatus(st)
      if (st.connected) load(false)
    }).catch((e) => onError(e.message))
  }, [])

  async function connect() {
    try {
      const { url } = await api.inboxAuthUrl()
      window.location.href = url
    } catch (e) {
      onError(e.message)
    }
  }

  // sync=false: saved list only. sync=true: also fetch mail not seen before.
  async function load(sync) {
    setLoading(true)
    try {
      setMessages(await api.inboxMessages(sync))
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

  const shown = (messages || []).filter((m) => filter === "ALL" || m.status === filter)

  return (
    <section className="pane">
      <div className="pane-head">
        <div>
          <h2>Gmail inbox</h2>
          <p className="pane-sub">
            Saved list -- only new mail is fetched when you check. Mail you sent is never listed. A new email that
            names account ids starts processing by itself.
          </p>
        </div>
        <button className="primary" onClick={() => load(true)} disabled={loading}>
          {loading ? "Checking..." : "Check for new mail"}
        </button>
      </div>

      <div className="inbox-toolbar">
        <div className="filter-chips">
          {FILTERS.map((f) => (
            <button key={f.key} className={`filter-chip ${filter === f.key ? "active" : ""}`} onClick={() => setFilter(f.key)}>
              {f.label}{messages ? ` (${f.key === "ALL" ? messages.length : messages.filter((m) => m.status === f.key).length})` : ""}
            </button>
          ))}
        </div>
      </div>

      {messages === null ? (
        <p className="muted">Loading saved list...</p>
      ) : shown.length === 0 ? (
        <p className="muted">
          {messages.length === 0 ? 'Nothing saved yet -- click "Check for new mail".' : "No emails in this view."}
        </p>
      ) : (
        <div className="inbox-list">
          {shown.map((m) => (
            <MessageRow key={m.message_id} msg={m} running={running} onStarted={onStarted} onView={onView} onError={onError} />
          ))}
        </div>
      )}
    </section>
  )
}
