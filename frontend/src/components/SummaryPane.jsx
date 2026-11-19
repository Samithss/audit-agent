export default function SummaryPane({ summary }) {
  if (!summary.length) return null
  const cols = Object.keys(summary[0])
  return (
    <section className="pane">
      <h2>3. Run summary</h2>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
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
