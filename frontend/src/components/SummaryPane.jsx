export default function SummaryPane({ summary }) {
  if (!summary.length) return null
  // Show the readable check name instead of the raw check_type code.
  const cols = Object.keys(summary[0]).filter((c) => c !== "check_type")
  cols.sort((a, b) => (a === "check" ? 0.5 : cols.indexOf(a)) - (b === "check" ? 0.5 : cols.indexOf(b)))
  return (
    <section className="pane">
      <h2>3. Run summary</h2>
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
