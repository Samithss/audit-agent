import { api } from "../api"

export default function ScorecardPane({ requestId, score, letter }) {
  return (
    <section className="pane">
      <h2>5. Scorecard</h2>
      {score && !score.error ? (
        <div className="metrics">
          <div className="metric">
            <span className="metric-value">{(score.recall * 100).toFixed(1)}%</span>
            <span className="metric-label">Gap recall (target &ge; 95%)</span>
          </div>
          <div className="metric">
            <span className="metric-value">{(score.false_gap_rate * 100).toFixed(1)}%</span>
            <span className="metric-label">False gap rate (target &lt; 5%)</span>
          </div>
          <div className="metric">
            <span className="metric-value">{score.unsupported_claims}</span>
            <span className="metric-label">Unevidenced claims (target 0)</span>
          </div>
        </div>
      ) : score?.error ? (
        <p className="muted">Scoring unavailable: {score.error}</p>
      ) : null}

      <h2>Draft letter</h2>
      {letter.needs_human_review ? (
        <p className="badge warning">Needs human review: {letter.validation.reasons.join("; ")}</p>
      ) : (
        <p className="badge success">
          Validator passed -- every claim cites the summary, no softening language, DRAFT disclaimer present.
        </p>
      )}
      <div className="letter-text">
        {letter.text.split("\n\n").map((blk, i) =>
          blk.trim().startsWith("|")
            ? <pre key={i} className="letter-table">{blk}</pre>
            : <p key={i}>{blk}</p>
        )}
      </div>

      <h2>Downloads</h2>
      <div className="row">
        <a className="button" href={api.downloadUrl(requestId, "gap_report")} download>gap_report.xlsx</a>
        <a className="button" href={api.downloadUrl(requestId, "request_interpretation")} download>
          request_interpretation.md
        </a>
        <a className="button" href={api.downloadUrl(requestId, "letter")} download>response_letter_DRAFT.docx</a>
      </div>
    </section>
  )
}
