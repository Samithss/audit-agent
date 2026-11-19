import { useMemo, useState } from "react"

export default function GapsPane({ gaps }) {
  const [checkType, setCheckType] = useState("")
  const [severity, setSeverity] = useState("")
  const [selected, setSelected] = useState(null)

  const checkTypes = useMemo(() => [...new Set(gaps.map((g) => g.check_type))].sort(), [gaps])
  const severities = useMemo(() => [...new Set(gaps.map((g) => g.severity))].sort(), [gaps])

  const filtered = gaps.filter(
    (g) => (!checkType || g.check_type === checkType) && (!severity || g.severity === severity)
  )

  return (
    <section className="pane">
      <h2>4. Gap table</h2>
      <div className="row">
        <select value={checkType} onChange={(e) => setCheckType(e.target.value)}>
          <option value="">All check types</option>
          {checkTypes.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          {severities.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <span className="muted">{filtered.length} of {gaps.length} gaps</span>
      </div>
      <div className="gap-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>account_id</th><th>check_type</th><th>gap_type</th><th>severity</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((g) => (
              <tr
                key={g.gap_item_id}
                className={selected?.gap_item_id === g.gap_item_id ? "selected" : ""}
                onClick={() => setSelected(g)}
              >
                <td>{g.account_id}</td>
                <td>{g.check_type}</td>
                <td>{g.gap_type}</td>
                <td><span className={`sev sev-${g.severity?.toLowerCase()}`}>{g.severity}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Evidence drawer</h3>
      {selected ? (
        <pre className="evidence">{JSON.stringify(selected, null, 2)}</pre>
      ) : (
        <p className="muted">Click a row above to inspect its evidence.</p>
      )}
    </section>
  )
}
