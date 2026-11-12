import { useCallback, useEffect, useMemo, useState } from "react"
import { Users, UserRoundCog, BookOpen, CalendarDays, ClipboardList, Search, LoaderCircle, Plus, Pencil, Trash2, X } from "lucide-react"
import MainLayout from "../../layouts/MainLayout"
import { Link } from "react-router-dom"
import { adminList, adminCreate, adminUpdate, adminDelete, fetchRegistrationSelfie } from "../../services/api"

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
const PERIODS = ["P1", "P2", "P3", "P4", "P5", "P6"]

// Field types: text | email | password | textarea | select | checkbox | date
// `options` may be an array of {value,label} or the name of a lookup list ("faculty" | "students")
const CONFIG = {
  students: {
    title: "Student management", resource: "students", icon: Users, noun: "student",
    listResource: "students",
    columns: ["name", "index_number", "email", "institution_name", "programme_name", "level", "is_approved"],
    format: { level: (v) => (v ? `Level ${v}` : "—"), programme_name: (v) => v || "—" },
    fields: [
      { name: "name", label: "Full name", required: true },
      { name: "index_number", label: "Student index number", required: true },
      { name: "email", label: "Email", type: "email", required: true },
      { name: "password", label: "Password", type: "password", requiredOnCreate: true, hint: "Leave blank to keep the current password" },
      { name: "institution_name", label: "Institution", required: true },
      { name: "faculty_name", label: "Faculty / School" },
      { name: "department", label: "Department" },
      { name: "programme_name", label: "Programme" },
      { name: "academic_year", label: "Academic year" },
      { name: "level", label: "Level", type: "select", number: true, default: 100,
        options: [100, 200, 300, 400, 500, 600, 700].map((n) => ({ value: n, label: `Level ${n}` })) },
      { name: "interests", label: "Interests", type: "textarea" },
      { name: "is_approved", label: "Approved (can log in)", type: "checkbox", default: true },
    ],
  },
  faculty: {
    title: "Lecturer management", resource: "faculty", icon: UserRoundCog, noun: "faculty member",
    columns: ["name", "email", "staff_id", "institution_name", "department"],
    fields: [
      { name: "name", label: "Full name", required: true },
      { name: "email", label: "Email", type: "email", required: true },
      { name: "password", label: "Password", type: "password", requiredOnCreate: true, hint: "Leave blank to keep the current password" },
      { name: "staff_id", label: "Staff ID", required: true },
      { name: "phone", label: "Phone" },
      { name: "institution_name", label: "Institution", required: true },
      { name: "faculty_name", label: "Faculty / School" },
      { name: "department", label: "Department" },
      { name: "programme_name", label: "Programme / Subject area" },
      { name: "designation", label: "Designation" },
      { name: "is_approved", label: "Approved / Active", type: "checkbox", default: true },
    ],
  },
  courses: {
    title: "Learning resources catalogue", resource: "resources", icon: BookOpen, noun: "resource",
    columns: ["title", "category", "skill_tag", "duration", "platform"],
    fields: [
      { name: "title", label: "Title", required: true },
      { name: "category", label: "Category", required: true },
      { name: "skill_tag", label: "Skill tags (space separated)", required: true },
      { name: "duration", label: "Duration", required: true },
      { name: "platform", label: "Platform" },
      { name: "description", label: "Description", type: "textarea" },
    ],
  },
  grading: {
    title: "Grading bands", resource: "grading-bands", icon: ClipboardList, noun: "grading band",
    columns: ["name", "min_score", "max_score", "grade_point", "remark"],
    fields: [
      { name: "name", label: "Grade (e.g. A)", required: true },
      { name: "min_score", label: "Minimum score (%)", type: "number", required: true, default: 0 },
      { name: "max_score", label: "Maximum score (%)", type: "number", required: true, default: 100 },
      { name: "grade_point", label: "Grade point", type: "number" },
      { name: "remark", label: "Remark (e.g. Excellent)" },
    ],
  },
}

const today = () => new Date().toISOString().slice(0, 10)

function blankForm(fields) {
  const f = {}
  fields.forEach((x) => { f[x.name] = x.default ?? (x.type === "checkbox" ? false : "") })
  if (fields.some((x) => x.type === "date")) fields.filter((x) => x.type === "date").forEach((x) => { f[x.name] = today() })
  return f
}

export default function AdminResources({ type }) {
  const cfg = CONFIG[type]
  const [rows, setRows] = useState([])
  const [lookups, setLookups] = useState({})
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [modal, setModal] = useState(null) // { mode: "create"|"edit", id?, form }
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState("")
  const [evidencePhoto, setEvidencePhoto] = useState(null)
  const [evidenceBusy, setEvidenceBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError("")
    try {
      const [data, ...extra] = await Promise.all([
        adminList(cfg.listResource || cfg.resource),
        ...(cfg.lookups || []).map((l) => adminList(l)),
      ])
      setRows(data)
      const lk = {}
      ;(cfg.lookups || []).forEach((l, i) => { lk[l] = extra[i] })
      setLookups(lk)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [cfg])

  useEffect(() => { setQuery(""); setNotice(""); setModal(null); load() }, [load])

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q))
  }, [rows, query])

  const optionsFor = (field) =>
    Array.isArray(field.options) ? field.options
      : (lookups[field.options] || []).map((x) => ({ value: x.id, label: x.email ? `${x.name} (${x.email})` : x.name }))

  const openCreate = () => { setFormError(""); setModal({ mode: "create", form: blankForm(cfg.fields) }) }
  const openEdit = (row) => {
    setFormError("")
    const form = blankForm(cfg.fields)
    cfg.fields.forEach((f) => { if (f.type !== "password" && row[f.name] !== undefined && row[f.name] !== null) form[f.name] = row[f.name] })
    setModal({ mode: "edit", id: row.id, form })
  }

  const buildPayload = (mode, form) => {
    const body = {}
    cfg.fields.forEach((f) => {
      if (mode === "edit" && f.createOnly) return
      let v = form[f.name]
      if (f.type === "password" && !v) return
      if (f.number && v !== "") v = Number(v)
      body[f.name] = v
    })
    return body
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true); setFormError("")
    try {
      const body = buildPayload(modal.mode, modal.form)
      if (modal.mode === "create") await adminCreate(cfg.resource, body)
      else await adminUpdate(cfg.resource, modal.id, body)
      setModal(null)
      setNotice(`${cfg.noun[0].toUpperCase()}${cfg.noun.slice(1)} ${modal.mode === "create" ? "created" : "updated"}.`)
      await load()
    } catch (err) { setFormError(err.message) } finally { setSaving(false) }
  }

  const viewRegistrationSelfie = async (row) => {
    setEvidenceBusy(true); setError("")
    try { setEvidencePhoto(await fetchRegistrationSelfie(row.id)) }
    catch (e) { setError(e.message) }
    finally { setEvidenceBusy(false) }
  }

  const remove = async (row) => {
    if (!window.confirm(`Delete this ${cfg.noun}? This cannot be undone.`)) return
    setNotice(""); setError("")
    try {
      await adminDelete(cfg.resource, row.id)
    } catch (err) {
      if ((/Deleting will also delete|attendance record|course enrolment/i.test(err.message)) && window.confirm(`${err.message}\n\nPermanently delete this record and its linked history? This cannot be undone.`)) {
        try { await adminDelete(cfg.resource, row.id, "?force=true") } catch (e2) { setError(e2.message); return }
      } else { setError(err.message); return }
    }
    setNotice(`${cfg.noun[0].toUpperCase()}${cfg.noun.slice(1)} deleted.`)
    await load()
  }

  if (!cfg) return null
  const Icon = cfg.icon
  const input = "w-full border rounded-lg bg-white px-3 py-2"
  const visibleFields = modal ? cfg.fields.filter((f) => !(modal.mode === "edit" && f.createOnly)) : []

  return (
    <MainLayout>
      <section className="space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-blue-50 p-3 text-blue-700"><Icon size={24} /></div>
            <div>
              <p className="text-sm text-slate-500">Smart Campus administration</p>
              <h1 className="text-2xl font-bold">{cfg.title}</h1>
            </div>
          </div>
          {!cfg.readOnly && <button onClick={openCreate} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
            <Plus size={18} /> Add {cfg.noun}
          </button>}
        </div>

        {notice && <div className="rounded-lg bg-green-100 p-3 text-sm text-green-700">{notice}</div>}
        {error && <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700 flex items-center justify-between gap-3"><span>{error}</span><button type="button" onClick={load} className="font-semibold underline">Try again</button></div>}

        <div className="relative max-w-md">
          <Search className="absolute left-3 top-3 text-slate-400" size={17} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search records..." className="w-full border bg-white py-2.5 pl-10 pr-3" />
        </div>

        <div className="overflow-x-auto rounded-2xl bg-white p-4">
          {loading ? (
            <div className="flex items-center gap-2 p-6 text-slate-500"><LoaderCircle className="animate-spin" /> Loading records...</div>
          ) : filtered.length === 0 ? (
            <p className="p-6 text-slate-500">No records found.</p>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  {cfg.columns.map((c) => {
                    const label = cfg.fields.find((f) => f.name === c)?.label || c.replaceAll("_", " ")
                    return <th key={c} className="border-b px-3 py-3 text-slate-500">{label}</th>
                  })}
                  <th className="border-b px-3 py-3 text-right text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id} className="border-b last:border-0">
                    {cfg.columns.map((c) => {
                      const v = row[c]
                      const shown = cfg.format?.[c] ? cfg.format[c](v) : typeof v === "boolean" ? (v ? "Yes" : "No") : v ?? "—"
                      return <td key={c} className="px-3 py-3">{c === "name" && (type === "students" || type === "faculty") ? <Link className="text-blue-700 hover:underline font-medium" to={`/profiles/${row.id}`}>{shown}</Link> : shown}</td>
                    })}
                    <td className="whitespace-nowrap px-3 py-3 text-right">
                      {(type === "students" || type === "faculty") && row.has_registration_selfie && <button onClick={() => viewRegistrationSelfie(row)} disabled={evidenceBusy} title="View registration selfie" className="mr-2 rounded p-1.5 text-emerald-700 hover:bg-emerald-50">{evidenceBusy ? "…" : "Selfie"}</button>}
                      {!cfg.readOnly && <button onClick={() => openEdit(row)} title="Edit" className="mr-2 rounded p-1.5 text-blue-600 hover:bg-blue-50"><Pencil size={16} /></button>}
                      <button onClick={() => remove(row)} title="Delete record" className="rounded p-1.5 text-red-600 hover:bg-red-50"><Trash2 size={16} /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {evidencePhoto && <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" onClick={() => { URL.revokeObjectURL(evidencePhoto); setEvidencePhoto(null) }}><div className="w-full max-w-lg rounded-2xl bg-white p-4" onClick={e => e.stopPropagation()}><div className="mb-3 flex items-center justify-between"><strong>Registration selfie evidence</strong><button onClick={() => { URL.revokeObjectURL(evidencePhoto); setEvidencePhoto(null) }} className="text-blue-700">Close</button></div><img src={evidencePhoto} alt="Private registration selfie" className="max-h-[70vh] w-full rounded-xl object-contain"/></div></div>}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={save} className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold capitalize">{modal.mode} {cfg.noun}</h2>
              <button type="button" onClick={() => setModal(null)} className="rounded p-1 hover:bg-gray-100"><X size={18} /></button>
            </div>
            {formError && <div className="rounded-lg bg-red-100 p-3 text-sm text-red-700">{formError}</div>}
            {visibleFields.map((f) => {
              const value = modal.form[f.name]
              const set = (v) => setModal({ ...modal, form: { ...modal.form, [f.name]: v } })
              const required = f.required || (f.requiredOnCreate && modal.mode === "create")
              return (
                <label key={f.name} className="block text-sm">
                  {f.type === "checkbox" ? (
                    <span className="flex items-center gap-2">
                      <input type="checkbox" checked={!!value} onChange={(e) => set(e.target.checked)} /> {f.label}
                    </span>
                  ) : (
                    <>
                      <span className="mb-1 block text-slate-600">{f.label}{required && " *"}</span>
                      {f.type === "select" ? (
                        <select className={input} value={value} onChange={(e) => set(e.target.value)} required={required}>
                          <option value="">— select —</option>
                          {optionsFor(f).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      ) : f.type === "textarea" ? (
                        <textarea className={input} rows={3} value={value} onChange={(e) => set(e.target.value)} required={required} />
                      ) : (
                        <input className={input} type={f.type || "text"} value={value} onChange={(e) => set(e.target.value)}
                          required={required} minLength={f.type === "password" ? 6 : undefined}
                          autoComplete={f.type === "password" ? "new-password" : undefined} />
                      )}
                      {f.hint && modal.mode === "edit" && f.type === "password" && <span className="text-xs text-slate-400">{f.hint}</span>}
                      {f.hint && f.type !== "password" && <span className="text-xs text-slate-400">{f.hint}</span>}
                    </>
                  )}
                </label>
              )
            })}
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setModal(null)} className="rounded-lg border px-4 py-2 hover:bg-gray-50">Cancel</button>
              <button disabled={saving} className="rounded-lg bg-blue-600 px-5 py-2 text-white hover:bg-blue-700 disabled:opacity-60">
                {saving ? "Saving..." : modal.mode === "create" ? "Create" : "Save changes"}
              </button>
            </div>
          </form>
        </div>
      )}
    </MainLayout>
  )
}
