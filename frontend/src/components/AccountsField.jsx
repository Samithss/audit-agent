export default function AccountsField({ file, setFile, disabled }) {
  return (
    <div className="field" style={{ marginTop: 10 }}>
      <span>Account list (Annexure A) -- optional</span>
      <input
        type="file"
        accept=".csv,.xlsx"
        disabled={disabled}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <p className="muted small">
        CSV or Excel with an <code>account_id</code> column. If you don't attach one, the agent tests the sampled
        accounts of the lender picked below. If you do, those exact accounts are tested and the lender is detected
        automatically.
        {file && <> Using <strong>{file.name}</strong>.</>}
      </p>
    </div>
  )
}
