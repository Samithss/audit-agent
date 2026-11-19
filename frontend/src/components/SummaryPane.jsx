export default function SummaryPane({ summary }) {
  if (!summary.length) return null
  // Show the readable check name instead of the raw check_type code.
  const cols = Object.keys(summary[0]).filter((c) => c !== "check_type")
  cols.sort((a, b) => (a === "check" ? 0.5 : cols.indexOf(a)) - (b === "check" ? 0.5 : cols.indexOf(b)))
  return (
    <section className="pane">
      <div className="pane-head"><div><h2><span className="step">2</span>Run summary</h2><p className="pane-sub">Accounts per check and outcome.</p></div></div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>{cols.map((c) => <th key={c}>{c === "check" ? "what was checked" : c}</th>)}</tr>
          </thead>
          <tbody>
            {summary.map((row, i) => (
              <tr key={i}>{cols.map((c) => <td key={c}>{row[c]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
