const BASE = "/api"

async function json(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  listRequests: () => fetch(`${BASE}/requests`).then(json),
  getText: (id) => fetch(`${BASE}/requests/${id}/text`).then(json),
  startRun: (id) => fetch(`${BASE}/requests/${id}/run`, { method: "POST" }).then(json),
  getStatus: (id) => fetch(`${BASE}/requests/${id}/status`).then(json),
  getResult: (id) => fetch(`${BASE}/requests/${id}/result`).then(json),
  getGaps: (id, { checkType, severity } = {}) => {
    const params = new URLSearchParams()
    if (checkType) params.set("check_type", checkType)
    if (severity) params.set("severity", severity)
    const qs = params.toString()
    return fetch(`${BASE}/requests/${id}/gaps${qs ? `?${qs}` : ""}`).then(json)
  },
  downloadUrl: (id, kind) => `${BASE}/requests/${id}/download/${kind}`,
}
