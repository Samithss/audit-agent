export default function AccountsField({ file, setFile, disabled }) {
  return (
    <div className="field" style={{ marginTop: 10 }}>
      <span>Account list (Annexure A)</span>
      <input
        type="file"
        key={file ? "f" : "nof"}
        accept=".csv,.xlsx"
        disabled={disabled}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <p className="muted small">
        CSV or Excel with an <code>account_id</code> column. Exactly these accounts are tested.
        {file && <> Using <strong>{file.name}</strong>.</>}
      </p>
      {file && <button className="toggle" onClick={() => setFile(null)} disabled={disabled}>Remove account list</button>}
    </div>
  )
}
