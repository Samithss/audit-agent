// Renders a drafted letter the way it will arrive: paragraphs as text, and the
// pipe-table as a real <table>. Same parse as agent/letter.py iter_blocks.
export function parseLetter(text) {
  const blocks = []
  let para = [], table = []
  const flushPara = () => { if (para.join("\n").trim()) blocks.push({ kind: "para", text: para.join("\n").trim() }); para = [] }
  const flushTable = () => {
    const rows = table
      .filter((l) => !/^[|\-\s:]+$/.test(l))
      .map((l) => l.replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
    if (rows.length) blocks.push({ kind: "table", rows })
    table = []
  }
  for (const raw of (text || "").replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim()
    if (line.startsWith("|")) { flushPara(); table.push(line) }
    else if (!line) { flushTable(); flushPara() }
    else { flushTable(); para.push(raw) }
  }
  flushTable(); flushPara()
  return blocks
}

export default function LetterView({ text }) {
  return (
    <div className="letter">
      {parseLetter(text).map((b, i) =>
        b.kind === "table" ? (
          <table key={i}>
            <thead><tr>{b.rows[0].map((c, j) => <th key={j}>{c}</th>)}</tr></thead>
            <tbody>
              {b.rows.slice(1).map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}
            </tbody>
          </table>
        ) : (
          <p key={i}>{b.text.split("\n").map((l, j, a) => <span key={j}>{l}{j < a.length - 1 && <br />}</span>)}</p>
        )
      )}
    </div>
  )
}
