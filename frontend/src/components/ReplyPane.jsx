import { useState } from "react"
import { api } from "../api"

// Manual-only, always: the letter is drafted, but nothing in this app ever
// sends it on its own. A human reviews (and can edit) the text, then has to
// explicitly click Send and confirm -- extra friction if the validator
// flagged needs_human_review, since that draft is more likely to be wrong.
export default function ReplyPane({ requestId, letter, replyTo, replied: repliedProp }) {
  const [draft, setDraft] = useState(letter.text)
  const [reviewed, setReviewed] = useState(false)
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(repliedProp)
  const [error, setError] = useState("")

  if (!replyTo) return null

  const needsExtraConfirm = letter.needs_human_review
  const canSend = !sending && !sent && (!needsExtraConfirm || reviewed)

  async function send() {
    if (!window.confirm(`Send this reply to ${replyTo}? This cannot be undone from here.`)) return
    setSending(true)
    setError("")
    try {
      await api.sendReply(requestId, draft)
      setSent(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="pane">
      <h2>Send reply</h2>
      <p className="muted">
        This was pulled from a real email -- replying is a manual, one-time action. Review (and edit if needed)
        before sending to <strong>{replyTo}</strong>.
      </p>

      {sent ? (
        <p className="badge success">Reply sent to {replyTo}.</p>
      ) : (
        <>
          <textarea
            className="paste-box"
            rows={10}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
          />
          {needsExtraConfirm && (
            <label className="row" style={{ marginTop: 10 }}>
              <input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />
              <span>I've reviewed this draft (flagged for human review) and confirm it's accurate before sending.</span>
            </label>
          )}
          <button className="primary" onClick={send} disabled={!canSend} style={{ marginTop: 10 }}>
            {sending ? "Sending..." : `Send reply to ${replyTo}`}
          </button>
          {error && <p className="error">{error}</p>}
        </>
      )}
    </section>
  )
}
