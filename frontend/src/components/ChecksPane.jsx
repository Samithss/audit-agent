export default function ChecksPane({ decomposed }) {
  const { checks, unsupported } = decomposed
  return (
    <section className="pane">
      <h2>2. Checks extracted</h2>
      <div className="two-col">
        <div>
          <h3>Checks ({checks.length})</h3>
          {checks.map((c) => (
            <div className="check-card" key={c.check_id}>
              <strong>{c.check_id} -- {c.check_label || c.check_type}</strong>
              <p className="quote">&ldquo;{c.source_text}&rdquo;</p>
            </div>
          ))}
        </div>
        <div>
          <h3>Unsupported -- reported, not dropped ({unsupported.length})</h3>
          {unsupported.length === 0 ? (
            <p className="badge success">Every requirement in the request mapped to a known check.</p>
          ) : (
            unsupported.map((c, i) => (
              <p className="badge warning" key={i}>&ldquo;{c.source_text}&rdquo;</p>
            ))
          )}
        </div>
      </div>
    </section>
  )
}
