export default function LenderPeriodFields({ lenders, lenderId, setLenderId, periodFrom, setPeriodFrom, periodTo, setPeriodTo }) {
  return (
    <div className="row">
      <label className="field">
        <span>Test against</span>
        <select value={lenderId} onChange={(e) => setLenderId(e.target.value)}>
          <option value="">Pick a lender's sample...</option>
          {lenders.map((l) => (
            <option key={l.lender_id} value={l.lender_id}>{l.lender_id}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Period from</span>
        <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
      </label>
      <label className="field">
        <span>Period to</span>
        <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
      </label>
    </div>
  )
}
