export default function RunLog({ log, status, error }) {
  if (!log.length) return null
  return (
    <section className="pane run-log">
      <h3>
        {status === "running" && <span className="spinner" />}
        {status === "running" ? "Running..." : status === "done" ? "Done" : status === "error" ? "Failed" : ""}
      </h3>
      <ul>
        {log.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      {error && <p className="error">Error: {error}</p>}
    </section>
  )
}
