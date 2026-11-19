export default function PeriodFields({ periodFrom, setPeriodFrom, periodTo, setPeriodTo }) {
  return (
    <div className="row">
      <label className="field">
        <span>Period from (optional)</span>
        <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
      </label>
      <label className="field">
        <span>Period to (optional)</span>
        <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
      </label>
      <p className="muted small" style={{ flexBasis: "100%", margin: 0 }}>
        Leave the dates blank and the agent reads the audit period from the request. Enter them to override it.
      </p>
    </div>
  )
}
