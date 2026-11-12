import { useCallback, useEffect, useState } from "react"
import { Megaphone, Plus, Trash2, Pencil, RefreshCw } from "lucide-react"
import MainLayout from "../layouts/MainLayout"
import { useAuth } from "../context/AuthContext"
import {
  listAnnouncements, createAnnouncement, updateAnnouncement, deleteAnnouncement,
  getMyCourses, listCourses,
} from "../services/api"

const AUDIENCES = [
  { value: "all", label: "Everyone" },
  { value: "lecturers", label: "All lecturers" },
  { value: "students", label: "All students" },
  { value: "course", label: "A course" },
]

const blank = { title: "", body: "", audience: "all", course_id: "" }

export default function Announcements() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [courses, setCourses] = useState([])
  const [form, setForm] = useState(blank)
  const [editId, setEditId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  const load = useCallback(async () => {
    setLoading(true); setError("")
    try {
      const data = await listAnnouncements()
      setRows(data || [])
      // Both administrators and lecturers can target a course, so both need the
      // course list for the audience picker.
      try {
        setCourses((user?.role === "faculty" ? await getMyCourses() : await listCourses()) || [])
      } catch { setCourses([]) }
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [user?.role])

  useEffect(() => { load() }, [load])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(""); setNotice("")
    const payload = {
      title: form.title, body: form.body || null, audience: form.audience,
      course_id: form.audience === "course" && form.course_id ? Number(form.course_id) : null,
    }
    try {
      if (editId) { await updateAnnouncement(editId, payload); setNotice("Announcement updated.") }
      else { await createAnnouncement(payload); setNotice("Announcement published.") }
      setForm(blank); setEditId(null); await load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const startEdit = (row) => {
    setEditId(row.id)
    setForm({ title: row.title || "", body: row.body || "", audience: row.audience || "all", course_id: row.course_id ? String(row.course_id) : "" })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const remove = async (row) => {
    if (!window.confirm(`Delete announcement "${row.title}"?`)) return
    setError("")
    try { await deleteAnnouncement(row.id); setNotice("Announcement deleted."); await load() }
    catch (err) { setError(err.message) }
  }

  const canManage = (row) => user?.role === "admin" || row.created_by === user?.id
  const input = "w-full border border-slate-300 rounded-lg px-3 py-2"

  return (
    <MainLayout>
      <section className="space-y-6">
        <header className="flex items-center gap-3">
          <span className="rounded-xl bg-blue-50 p-3 text-blue-700"><Megaphone size={22} /></span>
          <div><h1 className="text-2xl font-bold">Announcements</h1><p className="text-sm text-slate-500">Publish notices to students and lecturers.</p></div>
        </header>

        {notice && <div className="rounded-lg bg-green-100 p-3 text-sm text-green-700">{notice}</div>}
        {error && <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700">{error}</div>}

        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between"><h2 className="font-semibold">{editId ? "Edit announcement" : "New announcement"}</h2>{editId && <button className="text-sm text-blue-700 underline" onClick={() => { setEditId(null); setForm(blank) }}>Cancel edit</button>}</div>
          <form className="grid gap-3 mt-3" onSubmit={submit}>
            <input className={input} placeholder="Title" value={form.title} onChange={(e) => setForm(v => ({ ...v, title: e.target.value }))} required />
            <textarea className={input} rows={4} placeholder="Message" value={form.body} onChange={(e) => setForm(v => ({ ...v, body: e.target.value }))} />
            <div className="flex flex-wrap gap-3">
              <select className={input + " max-w-xs"} value={form.audience} onChange={(e) => setForm(v => ({ ...v, audience: e.target.value }))}>
                {AUDIENCES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
              {form.audience === "course" && (
                <select className={input + " max-w-xs"} value={form.course_id} onChange={(e) => setForm(v => ({ ...v, course_id: e.target.value }))} required>
                  <option value="">Select course</option>
                  {courses.map(c => <option key={c.id} value={c.id}>{c.code} — {c.title}</option>)}
                </select>
              )}
            </div>
            <div><button className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700" disabled={busy}>{editId ? "Save changes" : <><Plus size={16} /> Publish</>}</button></div>
          </form>
        </section>

        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3"><h2 className="font-semibold">Published announcements</h2><button className="p-2 rounded-lg hover:bg-slate-100" onClick={load} aria-label="Refresh"><RefreshCw size={17} /></button></div>
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : rows.length === 0 ? <p className="text-sm text-slate-500">No announcements yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-slate-500 border-b"><tr><th className="py-3 pr-4">Title</th><th className="pr-4">Audience</th><th className="pr-4">Created</th><th>Actions</th></tr></thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.id} className="border-b last:border-0">
                      <td className="py-3 pr-4"><b>{r.title}</b><small className="block text-slate-500">{r.body || ""}</small></td>
                      <td className="pr-4">{r.audience}</td>
                      <td className="pr-4">{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                      <td>{canManage(r) ? <div className="flex gap-2"><button title="Edit" onClick={() => startEdit(r)} className="p-1.5 rounded hover:bg-slate-100"><Pencil size={15} /></button><button title="Delete" onClick={() => remove(r)} className="p-1.5 rounded hover:bg-slate-100 text-red-600"><Trash2 size={15} /></button></div> : <span className="text-slate-400">—</span>}</td>
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
