import { useCallback, useEffect, useState } from "react"
import { Megaphone, RefreshCw } from "lucide-react"
import MainLayout from "../../layouts/MainLayout"
import { listStudentAnnouncements } from "../../services/api"

const AUDIENCE_LABEL = {
  all: "Everyone",
  students: "All students",
  programme: "Your programme",
  course: "Your course",
  batch: "Your class",
}

export default function StudentAnnouncements() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    setLoading(true); setError("")
    try { setRows(await listStudentAnnouncements() || []) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <MainLayout>
      <section className="space-y-6">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-blue-50 p-3 text-blue-700"><Megaphone size={22} /></span>
            <div><h1 className="text-2xl font-bold">Announcements</h1><p className="text-sm text-slate-500">Notices published to you by your lecturers and the institution.</p></div>
          </div>
          <button className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50" onClick={load} disabled={loading}><RefreshCw size={16} /> Refresh</button>
        </header>

        {error && <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700">{error}</div>}

        {loading ? <p className="text-sm text-slate-500">Loading announcements…</p>
          : rows.length === 0 ? (
            <section className="bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-sm">
              <Megaphone className="mx-auto text-slate-300" size={30} />
              <p className="mt-3 font-medium">No announcements yet</p>
              <p className="text-sm text-slate-500">When your lecturers or the institution publish a notice, it will appear here.</p>
            </section>
          ) : (
            <div className="space-y-3">
              {rows.map((r) => (
                <article key={r.id} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="font-semibold text-slate-900">{r.title}</h2>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{AUDIENCE_LABEL[r.audience] || r.audience}</span>
                  </div>
                  {r.body && <p className="mt-2 whitespace-pre-line text-sm text-slate-700">{r.body}</p>}
                  <p className="mt-3 text-xs text-slate-400">{r.course_code ? `${r.course_code} · ` : ""}{r.author} · {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</p>
                </article>
              ))}
            </div>
          )}
      </section>
    </MainLayout>
  )
}
