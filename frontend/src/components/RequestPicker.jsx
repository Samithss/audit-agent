export default function RequestPicker({ requests, selected, onSelect, text, running, onRun }) {
  return (
    <section className="pane">
      <h2>1. Drop the request</h2>
      <div className="row">
        <select value={selected} onChange={(e) => onSelect(e.target.value)} disabled={running}>
          {requests.map((r) => (
            <option key={r.request_id} value={r.request_id}>{r.label}</option>
          ))}
        </select>
        <button className="primary" onClick={onRun} disabled={running}>
          {running ? "Running..." : "Run the agent"}
        </button>
      </div>
      {text && (
        <details>
          <summary>Raw request text</summary>
          <pre className="raw-text">{text}</pre>
        </details>
      )}
    </section>
  )
}
