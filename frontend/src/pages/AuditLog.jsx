import { useEffect, useState } from "react"
import { History, RefreshCw } from "lucide-react"
import MainLayout from "../layouts/MainLayout"
import { getAuditLogs } from "../services/api"

export default function AuditLog() {
  const [rows, setRows] = useState([])
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = async () => {
    setLoading(true); setError("")
    try { setRows(await getAuditLogs(500) || []) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const filtered = rows.filter(r => JSON.stringify(r).toLowerCase().includes(query.toLowerCase()))

  return (
    <MainLayout>
      <section className="space-y-6">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-blue-50 p-3 text-blue-700"><History size={22} /></span>
            <div><h1 className="text-2xl font-bold">Audit log</h1><p className="text-sm text-slate-500">Recent account, course, attendance and payment actions.</p></div>
          </div>
          <button className="p-2 rounded-lg hover:bg-slate-100" onClick={load} aria-label="Refresh"><RefreshCw size={17} /></button>
        </header>

        {error && <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700">{error}</div>}

        <input className="w-full max-w-md border border-slate-300 rounded-lg px-3 py-2" placeholder="Search audit entries…" value={query} onChange={e => setQuery(e.target.value)} />

        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : filtered.length === 0 ? <p className="text-sm text-slate-500">No audit entries found.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-slate-500 border-b"><tr><th className="py-3 pr-4">When</th><th className="pr-4">Actor</th><th className="pr-4">Action</th><th className="pr-4">Entity</th><th>Detail</th></tr></thead>
                <tbody>
                  {filtered.map(r => (
                    <tr key={r.id} className="border-b last:border-0">
                      <td className="py-3 pr-4 whitespace-nowrap">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                      <td className="pr-4">{r.actor_name || "—"}</td>
                      <td className="pr-4">{r.action}</td>
                      <td className="pr-4">{r.entity}{r.entity_id ? ` #${r.entity_id}` : ""}</td>
                      <td className="text-slate-600">{r.detail || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    </MainLayout>
  )
}
