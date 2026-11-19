const SOURCE_LABEL = {
  RBI_VERIFIED: "RBI text",
  LENDER_POLICY: "Lender policy",
  UNVERIFIED: "Source not confirmed",
}

export default function GuidelinePicker({ guidelines, picked, setPicked, disabled }) {
  const cats = [...new Set(guidelines.map((g) => g.category))]
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id])
  const setCat = (cat, on) => {
    const ids = guidelines.filter((g) => g.category === cat && g.testable === "Y").map((g) => g.guideline_id)
    setPicked(on ? [...new Set([...picked, ...ids])] : picked.filter((x) => !ids.includes(x)))
  }

  return (
    <div className="field" style={{ marginTop: 10 }}>
      <span>Guidelines to check ({picked.length} selected)</span>
      <p className="muted small">
        These are added to whatever the request itself asks for. A guideline the request already covers
        (same check and channel) is not run twice. With no request at all, these guidelines are the request
        (enter the dates and attach an account list).
      </p>
      {cats.map((cat) => {
        const items = guidelines.filter((g) => g.category === cat)
        const ok = items.filter((g) => g.testable === "Y")
        const all = ok.length > 0 && ok.every((g) => picked.includes(g.guideline_id))
        return (
          <details key={cat} open className="guide-group">
            <summary>
              <strong>{cat}</strong>
              {ok.length > 0 && (
                <label style={{ marginLeft: 10 }} onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={all} disabled={disabled}
                         onChange={(e) => setCat(cat, e.target.checked)} /> select all
                </label>
              )}
            </summary>
            {items.map((g) => (
              <label key={g.guideline_id} style={{ display: "block", margin: "4px 0 4px 18px", opacity: g.testable === "Y" ? 1 : 0.55 }}>
                <input type="checkbox" disabled={disabled || g.testable !== "Y"}
                       checked={picked.includes(g.guideline_id)} onChange={() => toggle(g.guideline_id)} />{" "}
                {g.title}{" "}
                <span className="muted small">
                  [{SOURCE_LABEL[g.source_type] || g.source_type}] {g.source_ref}
                  {g.testable !== "Y" && <> — not testable yet: needs {g.needs}</>}
                </span>
              </label>
            ))}
          </details>
        )
      })}
    </div>
  )
}
