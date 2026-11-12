import { useCallback, useEffect, useMemo, useState } from "react"
import MainLayout from "../layouts/MainLayout"
import { Link } from "react-router-dom"
import {
  BookOpen, CalendarDays, Check, ClipboardList, Copy, Download, Layers, Plus, RefreshCw,
  Search, ShieldCheck, Trash2, Upload, Users, X, ArrowLeft, ArrowRight, QrCode, Pencil,
} from "lucide-react"
import "./AcademicHub.css"
import { useRealtime } from "../hooks/useRealtime"
import {
  adminList, createCourse, createTimetable, deleteCourse, deleteTimetable, fetchAttendancePhoto,
  createMyCourseSchedule, enrolByRegistrationCode, previewCourseByRegistrationCode,
  getAdminAttendanceRecords, getAttendanceRegister, getAttendanceSummary, getClassList, getMyCourses, getStudentCourses,
  listCourses, listEnrolments, listTimetable, publishTimetable, reviewEnrolment,
  rotateCourseCode, updateCourse, updateTimetable, withdrawCourse, listAttendanceSessions,
  listMaterials, createMaterial, deleteMaterial, updateMaterial, listAssessments, createAssessment, deleteAssessment,
  updateAssessment, enterMarks, releaseAssessment, getAssessmentResults,
  updateMyCourseSchedule, deleteMyCourseSchedule, changeBatch, getMyResults,
  listBatches, createBatch, updateBatch, deleteBatch, getMyAcademicDirectory,
} from "../services/api"

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
const PERIODS = ["P1", "P2", "P3", "P4", "P5", "P6"]

const blankCourse = {
  title: "", code: "", lecturer_id: "", department: "", department_id: "", programme_id: "", programme_name: "",
  level: "100", semester: "First Semester", academic_year: "", credit_hours: 3,
  description: "", registration_open: true, enrolment_requires_approval: false, is_published: true,
  batch_names: "",
}

const blankSlot = {
  course_id: "", batch_id: "", day_of_week: 0, period: "P1", class_type: "theory",
  room_no: "", venue_id: "", start_time: "", end_time: "", is_published: true,
}

function useFeedback() {
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [retry, setRetry] = useState(null)
  const run = async (fn, success) => {
    setError(""); setNotice(""); setRetry(null)
    try { const r = await fn(); if (success) setNotice(success); return r }
    catch (e) { setError(e.message); return null }
  }
  return { error, notice, setError, setNotice, retry, setRetry, run }
}

// ───────────────────────────── Admin: courses + timetable ────────────────────
function AdminWorkspace({ fb }) {
  const [courses, setCourses] = useState([])
  const [slots, setSlots] = useState([])
  const [lecturers, setLecturers] = useState([])
  const [enrolments, setEnrolments] = useState([])
  const [summary, setSummary] = useState([])
  const [attendanceRows, setAttendanceRows] = useState([])
  const [evidencePhoto, setEvidencePhoto] = useState(null)
  const [loading, setLoading] = useState(true)
  const [courseForm, setCourseForm] = useState(blankCourse)
  const [slotForm, setSlotForm] = useState(blankSlot)
  const [slotFilter, setSlotFilter] = useState({ day_of_week: "", course_id: "" })
  const [editSlot, setEditSlot] = useState(null)
  const [editCourse, setEditCourse] = useState(null)
  const [batchModal, setBatchModal] = useState(null)   // { course, batches }
  const [batchForm, setBatchForm] = useState({ name: "", capacity: "", is_active: true })
  const [editBatchId, setEditBatchId] = useState(null)
  const [courseQuery, setCourseQuery] = useState("")

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [c, t, e] = await Promise.all([listCourses(), listTimetable(), listEnrolments()])
      setCourses(c); setSlots(t); setEnrolments(e)
      setLecturers(await adminList("faculty"))
      try { setSummary(await getAttendanceSummary()) } catch { setSummary([]) }
      try { setAttendanceRows(await getAdminAttendanceRecords()) } catch { setAttendanceRows([]) }
    } catch (e) { fb.setError(e.message); fb.setRetry(() => load) } finally { setLoading(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { load() }, [load])
  useRealtime((event) => {
    if (["courses", "timetable", "enrolments", "attendance"].includes(event.type)) load()
  })

  const createCourseSubmit = async (e) => {
    e.preventDefault()
    const payload = { ...courseForm }
    payload.lecturer_id = Number(courseForm.lecturer_id)
    ;["department_id", "programme_id"].forEach((k) => { payload[k] = payload[k] ? Number(payload[k]) : null })
    payload.credit_hours = Number(courseForm.credit_hours)
    payload.batch_names = (courseForm.batch_names || "").split(",").map((s) => s.trim()).filter(Boolean)
    if (editCourse) {
      const rest = { ...payload }
      delete rest.code
      delete rest.batch_names
      const updated = await fb.run(() => updateCourse(editCourse.id, rest), "Course updated.")
      if (updated !== null) { setEditCourse(null); setCourseForm(blankCourse); load() }
      return
    }
    const created = await fb.run(() => createCourse(payload), "Course created. It is now available on the timetable.")
    if (created) { setCourseForm(blankCourse); load() }
  }

  const startEditCourse = (course) => {
    setEditCourse(course)
    setCourseForm({
      title: course.title || "", code: course.code || "", lecturer_id: course.lecturer_id || "",
      department: course.department || "", department_id: course.department_id || "",
      programme_id: course.programme_id || "", programme_name: course.programme_name || "",
      level: course.level || "100", semester: course.semester || "First Semester",
      academic_year: course.academic_year || "", credit_hours: course.credit_hours ?? 3,
      description: course.description || "", registration_open: !!course.registration_open,
      enrolment_requires_approval: !!course.enrolment_requires_approval,
      is_published: !!course.is_published, batch_names: "",
    })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const cancelEditCourse = () => { setEditCourse(null); setCourseForm(blankCourse) }

  const openBatches = async (course) => {
    try {
      const batches = await listBatches(course.id)
      setBatchModal({ course, batches })
      setBatchForm({ name: "", capacity: "", is_active: true })
      setEditBatchId(null)
    } catch (e) { fb.setError(e.message) }
  }

  const addBatch = async (e) => {
    e.preventDefault()
    const payload = { name: batchForm.name, capacity: batchForm.capacity === "" ? null : Number(batchForm.capacity), is_active: batchForm.is_active }
    if (editBatchId) {
      const ok = await fb.run(() => updateBatch(editBatchId, payload), "Batch updated.")
      if (ok !== null) { setBatchForm({ name: "", capacity: "", is_active: true }); setEditBatchId(null); openBatches(batchModal.course) }
      return
    }
    const created = await fb.run(() => createBatch(batchModal.course.id, payload), "Batch created.")
    if (created) { setBatchForm({ name: "", capacity: "", is_active: true }); openBatches(batchModal.course) }
  }

  const startEditBatch = (batch) => {
    setEditBatchId(batch.id)
    setBatchForm({ name: batch.name || "", capacity: batch.capacity ?? "", is_active: !!batch.is_active })
  }

  const cancelEditBatch = () => { setEditBatchId(null); setBatchForm({ name: "", capacity: "", is_active: true }) }

  const removeBatch = async (batch) => {
    if (!window.confirm(`Delete batch "${batch.name}"?`)) return
    const ok = await fb.run(() => deleteBatch(batch.id), "Batch deleted.")
    if (ok !== null) openBatches(batchModal.course)
  }

  const toggleBatchActive = async (batch) => {
    const ok = await fb.run(() => updateBatch(batch.id, { is_active: !batch.is_active }), "Batch updated.")
    if (ok !== null) openBatches(batchModal.course)
  }

  const toggleCourse = async (course, field) => {
    await fb.run(() => updateCourse(course.id, { [field]: !course[field] }), "Course updated.")
    load()
  }

  const removeCourse = async (course) => {
    if (!window.confirm(`Delete ${course.code} — ${course.title}? Courses with enrolments or attendance cannot be deleted.`)) return
    await fb.run(() => deleteCourse(course.id), "Course deleted.")
    load()
  }

  const copyCode = async (code) => {
    try { await navigator.clipboard.writeText(code); fb.setNotice("Registration code copied.") }
    catch { fb.setError("Could not access the clipboard.") }
  }

  const rotate = async (course) => {
    if (!window.confirm(`Generate a new registration code for ${course.code}? The current code stops working immediately.`)) return
    await fb.run(() => rotateCourseCode(course.id), "New registration code generated.")
    load()
  }

  const submitSlot = async (e) => {
    e.preventDefault()
    const payload = {
      course_id: Number(slotForm.course_id),
      batch_id: slotForm.batch_id ? Number(slotForm.batch_id) : null,
      day_of_week: Number(slotForm.day_of_week),
      period: slotForm.period,
      class_type: slotForm.class_type,
      room_no: slotForm.room_no || null,
      venue_id: slotForm.venue_id ? Number(slotForm.venue_id) : null,
      start_time: slotForm.start_time || null,
      end_time: slotForm.end_time || null,
      is_published: slotForm.is_published,
    }
    if (editSlot) {
      const ok = await fb.run(() => updateTimetable(editSlot.id, payload), "Timetable entry updated.")
      if (ok !== null) { setEditSlot(null); setSlotForm(blankSlot); load() }
    } else {
      const created = await fb.run(() => createTimetable(payload), "Timetable entry added.")
      if (created) { setSlotForm({ ...blankSlot }); load() }
    }
  }

  const editSlotRow = (slot) => {
    setEditSlot(slot)
    setSlotForm({
      course_id: slot.course_id, batch_id: slot.batch_id || "", day_of_week: slot.day_of_week, period: slot.period,
      class_type: slot.class_type || "theory", room_no: slot.room_no || "",
      venue_id: slot.venue_id || "", start_time: slot.start_time, end_time: slot.end_time,
      is_published: slot.is_published,
    })
  }

  const removeSlot = async (slot) => {
    if (!window.confirm("Remove this timetable entry?")) return
    await fb.run(() => deleteTimetable(slot.id), "Timetable entry removed.")
    load()
  }

  const viewAttendanceEvidence = async (id) => {
    try { setEvidencePhoto(await fetchAttendancePhoto(id)) }
    catch (e) { fb.setError(e.message) }
  }

  const publish = async (publish) => {
    await fb.run(() => publishTimetable({ publish }), publish ? "Timetable published to students and lecturers." : "Timetable unpublished.")
    load()
  }

  const review = async (id, status) => { await fb.run(() => reviewEnrolment(id, status), `Enrolment ${status}.`); load() }

  const filteredSlots = useMemo(() => slots.filter((s) =>
    (slotFilter.day_of_week === "" || s.day_of_week === Number(slotFilter.day_of_week)) &&
    (slotFilter.course_id === "" || s.course_id === Number(slotFilter.course_id))
  ), [slots, slotFilter])

  const pending = enrolments.filter((e) => e.status === "pending")

  return (
    <>
      <section className="academic-panel">
        <div className="panel-title"><div><h2>{editCourse ? `Edit ${editCourse.code}` : "Create a course"}</h2><p>{editCourse ? "Update the course details. The course code cannot be changed after creation." : "One canonical record — reused by the timetable, enrolments and attendance."}</p></div><Plus /></div>
        <form className="course-form" onSubmit={createCourseSubmit}>
          <input placeholder="Course title" value={courseForm.title} onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })} required />
          <input placeholder="Course code (e.g. IT301)" value={courseForm.code} onChange={(e) => setCourseForm({ ...courseForm, code: e.target.value })} required disabled={!!editCourse} title={editCourse ? "Course code cannot be changed" : undefined} />
          <select value={courseForm.lecturer_id} onChange={(e) => setCourseForm({ ...courseForm, lecturer_id: e.target.value })} required>
            <option value="">Assign lecturer</option>
            {lecturers.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
          <input placeholder="Eligible programme" value={courseForm.programme_name||""} onChange={(e) => setCourseForm({ ...courseForm, programme_name: e.target.value })} required />
          <input placeholder="Department (optional)" value={courseForm.department||""} onChange={(e) => setCourseForm({ ...courseForm, department: e.target.value })} />
          <select value={courseForm.level} onChange={(e) => setCourseForm({ ...courseForm, level: e.target.value })}>
            {["100", "200", "300", "400", "500", "600"].map((l) => <option key={l} value={l}>Level {l}</option>)}
          </select>
          <select value={courseForm.semester} onChange={(e) => setCourseForm({ ...courseForm, semester: e.target.value })}>
            {["First Semester", "Second Semester"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input placeholder="Academic year (e.g. 2025/2026)" value={courseForm.academic_year} onChange={(e) => setCourseForm({ ...courseForm, academic_year: e.target.value })} />
          <input type="number" min="0" max="30" placeholder="Credit hours" value={courseForm.credit_hours} onChange={(e) => setCourseForm({ ...courseForm, credit_hours: e.target.value })} />
          {!editCourse && <input className="wide" placeholder="Batches (comma separated, e.g. Batch A, Batch B)" value={courseForm.batch_names} onChange={(e) => setCourseForm({ ...courseForm, batch_names: e.target.value })} />}
          <input className="wide" placeholder="Course description (optional)" value={courseForm.description} onChange={(e) => setCourseForm({ ...courseForm, description: e.target.value })} />
          <label><input type="checkbox" checked={courseForm.registration_open} onChange={(e) => setCourseForm({ ...courseForm, registration_open: e.target.checked })} /> Registration open</label>
          <label><input type="checkbox" checked={courseForm.enrolment_requires_approval} onChange={(e) => setCourseForm({ ...courseForm, enrolment_requires_approval: e.target.checked })} /> Lecturer approval required</label>
          <label><input type="checkbox" checked={courseForm.is_published} onChange={(e) => setCourseForm({ ...courseForm, is_published: e.target.checked })} /> Visible to students</label>
          <button className="primary-btn">{editCourse ? "Save changes" : <><Plus size={16} /> Create course</>}</button>
          {editCourse && <button type="button" className="refresh-btn" onClick={cancelEditCourse}>Cancel edit</button>}
        </form>
      </section>

      <section className="academic-panel">
        <div className="panel-title">
          <div><h2>Platform courses</h2><p>{courses.length} course(s) across registered lecturers</p></div>
          <Layers />
        </div>
        <div className="toolbar"><label className="search-box"><Search size={17} /><input placeholder="Search by title, code or lecturer" value={courseQuery} onChange={(e) => setCourseQuery(e.target.value)} /></label></div>
        <div className="course-grid">
          {courses.filter((c) => `${c.title} ${c.code} ${c.lecturer_name || ""} ${c.programme_name || ""}`.toLowerCase().includes(courseQuery.toLowerCase())).map((c) => (
            <article className="course-card" key={c.id}>
              <div className="course-top">
                <span className="course-mark">{c.code.slice(0, 2)}</span>
                <span className={c.is_published ? "pill-open" : "pill-closed"}>{c.is_published ? "Published" : "Draft"}</span>
              </div>
              <h3>{c.title}</h3>
              <p className="course-code">{c.code} · Level {c.level || "—"} · {c.semester || "—"}</p>
              <p className="course-desc">{c.description || "No description provided."}</p>
              <div className="course-meta">
                <span><Users size={15} /> {c.lecturer_name || "No lecturer"}</span>
                <span><Layers size={15} /> {c.credit_hours ?? "—"} credits · {c.programme_name || "No programme"}</span>
                <span><CalendarDays size={15} /> {c.academic_year || "Academic year not set"}</span>
              </div>
              <div className="course-actions">
                <button onClick={() => startEditCourse(c)}><Pencil size={15} /> Edit</button>
                <button onClick={() => openBatches(c)}><Layers size={15} /> Batches</button>
                <button onClick={() => copyCode(c.registration_code)}><Copy size={15} /> Code</button>
                <button onClick={() => rotate(c)}><RefreshCw size={15} /> Rotate</button>
                <button onClick={() => toggleCourse(c, "registration_open")}>{c.registration_open ? "Close registration" : "Open registration"}</button>
                <button onClick={() => toggleCourse(c, "is_published")}>{c.is_published ? "Unpublish" : "Publish"}</button>
                <button className="danger-link" onClick={() => removeCourse(c)}><Trash2 size={15} /> Delete</button>
                <span className="code-small">Expires: {c.registration_code_expires_at ? new Date(c.registration_code_expires_at).toLocaleDateString() : "—"}</span>
              </div>
            </article>
          ))}
          {!courses.length && <div className="empty-state">{loading ? "Loading courses…" : "No courses yet. Create the first course above."}</div>}
        </div>
      </section>

      <section className="academic-panel">
        <div className="panel-title"><div><h2>Timetable</h2><p>Each entry selects an existing course and references it by id.</p></div><CalendarDays /></div>
        <form className="course-form" onSubmit={submitSlot}>
          <select value={slotForm.course_id} onChange={(e) => setSlotForm({ ...slotForm, course_id: e.target.value, batch_id: "" })} required>
            <option value="">Select course</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title}</option>)}
          </select>
          <select value={slotForm.batch_id} onChange={(e) => setSlotForm({ ...slotForm, batch_id: e.target.value })} title="Class batch (cohort)">
            <option value="">Whole course / no batch</option>
            {(courses.find((c) => String(c.id) === String(slotForm.course_id))?.batches || []).map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
          <select value={slotForm.day_of_week} onChange={(e) => setSlotForm({ ...slotForm, day_of_week: e.target.value })}>
            {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <select value={slotForm.period} onChange={(e) => setSlotForm({ ...slotForm, period: e.target.value })}>
            {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <input placeholder="Room (optional)" value={slotForm.room_no} onChange={(e) => setSlotForm({ ...slotForm, room_no: e.target.value })} />
          <select value={slotForm.class_type} onChange={(e) => setSlotForm({ ...slotForm, class_type: e.target.value })}>
            <option value="theory">Theory</option><option value="lab">Lab</option><option value="tutorial">Tutorial</option>
          </select>
          <input placeholder="Start HH:MM (optional)" value={slotForm.start_time} onChange={(e) => setSlotForm({ ...slotForm, start_time: e.target.value })} />
          <input placeholder="End HH:MM (optional)" value={slotForm.end_time} onChange={(e) => setSlotForm({ ...slotForm, end_time: e.target.value })} />
          <label><input type="checkbox" checked={slotForm.is_published} onChange={(e) => setSlotForm({ ...slotForm, is_published: e.target.checked })} /> Published</label>
          <button className="primary-btn">{editSlot ? "Save entry" : <><Plus size={16} /> Add entry</>}</button>
          {editSlot && <button type="button" className="refresh-btn" onClick={() => { setEditSlot(null); setSlotForm(blankSlot) }}>Cancel edit</button>}
        </form>
        <div className="toolbar">
          <select value={slotFilter.day_of_week} onChange={(e) => setSlotFilter({ ...slotFilter, day_of_week: e.target.value })}>
            <option value="">All days</option>{DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <select value={slotFilter.course_id} onChange={(e) => setSlotFilter({ ...slotFilter, course_id: e.target.value })}>
            <option value="">All courses</option>{courses.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
          </select>
          <button className="primary-btn" onClick={() => publish(true)}><Upload size={15} /> Publish all</button>
          <button className="refresh-btn" onClick={() => publish(false)}>Unpublish all</button>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Day</th><th>Period</th><th>Course</th><th>Lecturer</th><th>Venue</th><th>Time</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {filteredSlots.map((s) => (
                <tr key={s.id}>
                  <td>{s.day_name}</td><td>{s.period}</td>
                  <td>{s.course_code}<small>{s.course_title}</small></td>
                  <td>{s.faculty_name || "—"}</td><td>{s.venue_name || s.room_no || "—"}</td>
                  <td>{s.start_time}–{s.end_time}</td>
                  <td><span className={s.is_published ? "status-approved" : "status-pending"}>{s.is_published ? "published" : "draft"}</span></td>
                  <td><div className="row-actions"><button title="Edit" onClick={() => editSlotRow(s)}><RefreshCw size={15} /></button><button title="Delete" onClick={() => removeSlot(s)}><Trash2 size={15} /></button></div></td>
                </tr>
              ))}
              {!filteredSlots.length && <tr><td colSpan="8">No timetable entries match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="academic-panel">
        <div className="panel-title"><div><h2>Enrolment management</h2><p>{pending.length} pending request(s) · {enrolments.length} record(s)</p></div><ShieldCheck /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Student</th><th>Index number</th><th>Course</th><th>Requested</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {enrolments.map((e) => (
                <tr key={e.id}>
                  <td><Link className="text-blue-700 underline font-semibold" to={`/profiles/${e.student_id}`}>{e.student_name}</Link><small>{e.email}</small></td>
                  <td>{e.index_number || "—"}</td>
                  <td>{e.course}<small>{e.course_code}</small></td>
                  <td>{new Date(e.requested_at).toLocaleString()}</td>
                  <td><span className={`status-${e.status}`}>{e.status}</span></td>
                  <td>{e.status === "pending"
                    ? <div className="row-actions"><button title="Approve" onClick={() => review(e.id, "approved")}><Check size={16} /></button><button title="Reject" onClick={() => review(e.id, "rejected")}><X size={16} /></button></div>
                    : "—"}</td>
                </tr>
              ))}
              {!enrolments.length && <tr><td colSpan="6">No enrolment records yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="academic-panel">
        <div className="panel-title"><div><h2>Attendance summary by course</h2><p>Aggregated from verified QR attendance records.</p></div><ClipboardList /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Course</th><th>Title</th><th>Records</th><th>Present</th><th>Rate</th></tr></thead>
            <tbody>
              {summary.map((s) => (
                <tr key={s.course_id}>
                  <td>{s.code}</td><td>{s.title}</td>
                  <td>{s.records}</td><td>{s.present}</td>
                  <td>{s.rate != null ? `${s.rate}%` : "—"}</td>
                </tr>
              ))}
              {!summary.length && <tr><td colSpan="5">No attendance has been recorded yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <section className="academic-panel">
        <div className="panel-title"><div><h2>Platform attendance evidence</h2><p>Latest attendance records across all registered institutions ({attendanceRows.length} shown, maximum 1,000).</p></div><ClipboardList /></div>
        <div className="table-wrap"><table><thead><tr><th>Student</th><th>Course</th><th>Lecturer</th><th>Date / time</th><th>Status</th><th>GPS evidence</th><th>Selfie</th></tr></thead><tbody>
          {attendanceRows.map(r=><tr key={r.id}><td><Link className="text-blue-700 underline" to={`/profiles/${r.student_id}`}>{r.student_name}</Link><small>{r.index_number||""}</small></td><td>{r.course_code||"—"}<small>{r.course_title||""}</small></td><td><Link className="text-blue-700 underline" to={`/profiles/${r.lecturer_id}`}>{r.lecturer_name}</Link></td><td>{r.date}<small>{r.marked_at?new Date(r.marked_at).toLocaleTimeString():"—"}</small></td><td>{r.status}</td><td>{r.distance_meters==null?"—":`${Math.round(r.distance_meters)} m / ${Math.round(r.radius_meters||0)} m radius · ±${Math.round(r.gps_accuracy||0)} m accuracy`}</td><td>{r.has_photo?<button className="text-blue-700 underline" onClick={()=>viewAttendanceEvidence(r.id)}>View selfie</button>:"—"}</td></tr>)}
          {!attendanceRows.length&&<tr><td colSpan="7">No attendance evidence recorded yet.</td></tr>}
        </tbody></table></div>
      </section>
      {evidencePhoto&&<div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4" onClick={()=>{URL.revokeObjectURL(evidencePhoto);setEvidencePhoto(null)}}><div className="max-w-lg w-full rounded-2xl bg-white p-4" onClick={e=>e.stopPropagation()}><div className="mb-3 flex justify-between"><strong>Attendance selfie evidence</strong><button onClick={()=>{URL.revokeObjectURL(evidencePhoto);setEvidencePhoto(null)}} className="text-blue-700">Close</button></div><img src={evidencePhoto} alt="Private attendance selfie evidence" className="w-full max-h-[70vh] object-contain rounded-xl"/></div></div>}
      {batchModal && <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4" onClick={()=>setBatchModal(null)}><div className="max-w-2xl w-full rounded-2xl bg-white p-5" onClick={e=>e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between"><div><h2 className="text-lg font-bold">Batches · {batchModal.course.code}</h2><p className="text-sm text-slate-500">Teaching groups students choose when registering.</p></div><button className="text-blue-700" onClick={()=>setBatchModal(null)}>Close</button></div>
        <form className="course-form" onSubmit={addBatch}>
          <input placeholder="Batch name (e.g. Batch 2)" value={batchForm.name} onChange={e=>setBatchForm(v=>({...v,name:e.target.value}))} required/>
          <input type="number" min="1" placeholder="Capacity (blank = unlimited)" value={batchForm.capacity} onChange={e=>setBatchForm(v=>({...v,capacity:e.target.value}))}/>
          <label><input type="checkbox" checked={batchForm.is_active} onChange={e=>setBatchForm(v=>({...v,is_active:e.target.checked}))}/> Active</label>
          <button className="primary-btn">{editBatchId ? <><Pencil size={15}/> Save changes</> : <><Plus size={15}/> Add batch</>}</button>
          {editBatchId && <button type="button" className="refresh-btn" onClick={cancelEditBatch}>Cancel edit</button>}
        </form>
        <div className="table-wrap mt-4"><table><thead><tr><th>Name</th><th>Enrolled</th><th>Capacity</th><th>Status</th><th>Actions</th></tr></thead><tbody>
          {(batchModal.batches||[]).map(b=><tr key={b.id}><td>{b.name}</td><td>{b.enrolled_count??0}</td><td>{b.capacity??"Unlimited"}</td><td><span className={b.is_active?"status-approved":"status-rejected"}>{b.is_active?"active":"inactive"}</span></td><td><div className="row-actions"><button title="Edit batch" onClick={()=>startEditBatch(b)}><Pencil size={15}/></button><button title={b.is_active?"Deactivate":"Activate"} onClick={()=>toggleBatchActive(b)}>{b.is_active?"Deactivate":"Activate"}</button><button title="Delete batch" onClick={()=>removeBatch(b)}><Trash2 size={15}/></button></div></td></tr>)}
          {!(batchModal.batches||[]).length && <tr><td colSpan="5">This course has no batches. Add one above.</td></tr>}
        </tbody></table></div>
      </div></div>}
    </>
  )
}

// ───────────────────────────── Lecturer workspace ────────────────────────────
function LecturerWorkspace({ fb }) {
  const [courses, setCourses] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detailTab, setDetailTab] = useState("overview")
  const [courseStudents, setCourseStudents] = useState([])
  const [courseEnrolments, setCourseEnrolments] = useState([])
  const [courseRegister, setCourseRegister] = useState([])
  const [courseSessions, setCourseSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [courseFilter, setCourseFilter] = useState("all")
  const [query, setQuery] = useState("")
  const [showCreate, setShowCreate] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)
  const [editScheduleId, setEditScheduleId] = useState(null)
  const [materials, setMaterials] = useState([])
  const [materialForm, setMaterialForm] = useState({ title: "", description: "", url: "", material_type: "link" })
  const [editMaterialId, setEditMaterialId] = useState(null)
  const [assessments, setAssessments] = useState([])
  const [assessmentForm, setAssessmentForm] = useState({ title: "", component: "continuous", max_score: 100, weight: "" })
  const [editAssessmentId, setEditAssessmentId] = useState(null)
  const [marksModal, setMarksModal] = useState(null)   // { assessment, rows:[{student_id,name,index_number,score}], busy }
  const [marksBusy, setMarksBusy] = useState(false)
  const [directory, setDirectory] = useState({ faculties: [], departments: [], programmes: [] })
  const [courseForm, setCourseForm] = useState({ title: "", code: "", programme_id: "", programme_name: "", department: "", department_id: "", level: "100", semester: "First Semester", academic_year: "", credit_hours: 3 })
  const [editCourseOpen, setEditCourseOpen] = useState(false)
  const [editCourseForm, setEditCourseForm] = useState({ title: "", programme_name: "", department: "", level: "100", semester: "First Semester", academic_year: "", credit_hours: 3, description: "", registration_open: true, enrolment_requires_approval: true, is_published: true })
  const [scheduleForm, setScheduleForm] = useState({ course_id: "", day_of_week: "0", start_time: "09:00", end_time: "11:00", building: "", room_no: "", class_type: "theory" })

  const loadCourses = useCallback(async () => {
    setLoading(true)
    try { setCourses(await getMyCourses() || []) }
    catch (e) { fb.setError(e.message || "Could not load your courses."); fb.setRetry(() => loadCourses) }
    finally { setLoading(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { loadCourses(); getMyAcademicDirectory().then(setDirectory).catch(e => fb.setError(e.message || "Academic programmes could not be loaded.")) }, [loadCourses])
  useRealtime((event) => {
    if (["enrolments", "courses", "timetable", "attendance", "materials"].includes(event.type)) {
      loadCourses()
      if (selectedId) loadCourseDetail(selectedId)
    }
  })

  const selectedCourse = courses.find(c => String(c.id) === String(selectedId)) || null
  const loadCourseDetail = async (courseId) => {
    setDetailLoading(true)
    try {
      const [lists, requests, attendance, sessions, mats, assess] = await Promise.all([
        getClassList(courseId),
        listEnrolments({ course_id: courseId }),
        getAttendanceRegister({ course_id: courseId }),
        listAttendanceSessions({ course_id: courseId }),
        listMaterials(courseId),
        listAssessments({ course_id: courseId }),
      ])
      setCourseStudents(lists?.[0]?.students || [])
      setCourseEnrolments(requests || [])
      setCourseRegister(attendance || [])
      setCourseSessions(sessions || [])
      setMaterials(mats || [])
      setAssessments(assess || [])
    } catch (e) { fb.setError(e.message || "Could not load this course workspace."); fb.setRetry(() => () => loadCourseDetail(courseId)) }
    finally { setDetailLoading(false) }
  }

  const openCourse = async (course) => {
    setSelectedId(course.id)
    setDetailTab("overview")
    setScheduleForm(v => ({ ...v, course_id: String(course.id) }))
    await loadCourseDetail(course.id)
  }
  const returnToCourses = () => { setSelectedId(null); setDetailTab("overview"); fb.setError(""); fb.setNotice("") }

  const createLecturerCourse = async (e) => {
    e.preventDefault()
    const selectedProgramme = directory.programmes.find(p => String(p.id) === String(courseForm.programme_id))
    const selectedDepartment = directory.departments.find(d => d.id === selectedProgramme?.department_id)
    if (!selectedProgramme) { fb.setError("Select a programme from the academic directory."); return }
    const payload = { ...courseForm, programme_id: Number(selectedProgramme.id), department_id: selectedDepartment?.id || null,
      programme_name: selectedProgramme.name, department: selectedDepartment?.name || "",
      credit_hours: Number(courseForm.credit_hours), registration_open: true,
      enrolment_requires_approval: true, is_published: true, batch_names: [] }
    const created = await fb.run(() => createCourse(payload), "Course created. Open its card to manage students and attendance.")
    if (created) { setCourseForm({ title: "", code: "", programme_id: "", programme_name: "", department: "", department_id: "", level: "100", semester: "First Semester", academic_year: "", credit_hours: 3 }); setShowCreate(false); loadCourses() }
  }

  const startEditCourse = (course) => {
    setEditCourseForm({
      title: course.title || "", programme_id: String(course.programme_id || ""), programme_name: course.programme_name || "", department: course.department || "",
      level: String(course.level || "100"), semester: course.semester || "First Semester",
      academic_year: course.academic_year || "", credit_hours: course.credit_hours ?? 3,
      description: course.description || "", registration_open: !!course.registration_open,
      enrolment_requires_approval: !!course.enrolment_requires_approval, is_published: !!course.is_published,
    })
    setEditCourseOpen(true)
  }

  const saveCourseEdits = async (e) => {
    e.preventDefault()
    const selectedProgramme = directory.programmes.find(p => String(p.id) === String(editCourseForm.programme_id))
    const selectedDepartment = directory.departments.find(d => d.id === selectedProgramme?.department_id)
    if (!selectedProgramme) { fb.setError("Select a programme from the academic directory."); return }
    const payload = { ...editCourseForm, programme_id: Number(selectedProgramme.id), department_id: selectedDepartment?.id || null,
      programme_name: selectedProgramme.name, department: selectedDepartment?.name || "",
      credit_hours: Number(editCourseForm.credit_hours), level: String(editCourseForm.level) }
    const updated = await fb.run(() => updateCourse(selectedId, payload), "Course details updated.")
    if (updated !== null) { setEditCourseOpen(false); await loadCourses(); loadCourseDetail(selectedId) }
  }

  const removeCourse = async (course) => {
    if (!window.confirm(`Delete ${course.code} ${course.title}? This cannot be undone. Courses with enrolment or attendance history cannot be deleted.`)) return
    const ok = await fb.run(() => deleteCourse(course.id), "Course deleted.")
    if (ok !== null) { setSelectedId(null); setEditCourseOpen(false); loadCourses() }
  }

  const createSchedule = async (e) => {
    e.preventDefault()
    const payload = { ...scheduleForm, day_of_week: Number(scheduleForm.day_of_week), course_id: Number(selectedId), class_type: scheduleForm.class_type }
    if (editScheduleId) {
      const updated = await fb.run(() => updateMyCourseSchedule(editScheduleId, payload), "Class schedule updated.")
      if (updated !== null) { setEditScheduleId(null); setShowSchedule(false); loadCourses(); loadCourseDetail(selectedId) }
      return
    }
    const created = await fb.run(() => createMyCourseSchedule(payload.course_id, payload), "Class schedule saved for this course.")
    if (created) { setShowSchedule(false); loadCourses(); loadCourseDetail(selectedId) }
  }

  const startEditSchedule = (slot) => {
    setEditScheduleId(slot.id)
    setShowSchedule(true)
    setScheduleForm({
      course_id: String(slot.course_id || selectedId), day_of_week: String(slot.day_of_week ?? 0),
      start_time: slot.start_time || "09:00", end_time: slot.end_time || "11:00",
      building: slot.venue_name ? String(slot.venue_name).split(" — ")[0] : "",
      room_no: slot.room_no || "", class_type: slot.class_type || "theory",
    })
  }

  const removeSchedule = async (slot) => {
    if (!window.confirm("Remove this class schedule? Students will no longer see this slot.")) return
    const ok = await fb.run(() => deleteMyCourseSchedule(slot.id), "Class schedule removed.")
    if (ok !== null) { loadCourses(); loadCourseDetail(selectedId) }
  }

  const addMaterial = async (e) => {
    e.preventDefault()
    const payload = { course_id: Number(selectedId), title: materialForm.title, description: materialForm.description || null, url: materialForm.url || null, material_type: materialForm.material_type }
    if (editMaterialId) {
      const rest = { title: materialForm.title, description: materialForm.description || null, url: materialForm.url || null, material_type: materialForm.material_type }
      const updated = await fb.run(() => updateMaterial(editMaterialId, rest), "Learning material updated.")
      if (updated !== null) { setMaterialForm({ title: "", description: "", url: "", material_type: "link" }); setEditMaterialId(null); loadCourseDetail(selectedId) }
      return
    }
    const created = await fb.run(() => createMaterial(payload), "Learning material added.")
    if (created) { setMaterialForm({ title: "", description: "", url: "", material_type: "link" }); loadCourseDetail(selectedId) }
  }

  const startEditMaterial = (material) => {
    setEditMaterialId(material.id)
    setMaterialForm({ title: material.title || "", description: material.description || "", url: material.url || "", material_type: material.material_type || "link" })
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const removeMaterial = async (material) => {
    if (!window.confirm(`Remove material "${material.title}"?`)) return
    const ok = await fb.run(() => deleteMaterial(material.id), "Material removed.")
    if (ok !== null) loadCourseDetail(selectedId)
  }

  const addAssessment = async (e) => {
    e.preventDefault()
    const payload = { course_id: Number(selectedId), title: assessmentForm.title, component: assessmentForm.component, max_score: Number(assessmentForm.max_score) || 100, weight: assessmentForm.weight === "" ? null : Number(assessmentForm.weight) }
    if (editAssessmentId) {
      const updated = await fb.run(() => updateAssessment(editAssessmentId, payload), "Assessment updated.")
      if (updated !== null) { setEditAssessmentId(null); setAssessmentForm({ title: "", component: "continuous", max_score: 100, weight: "" }); loadCourseDetail(selectedId) }
      return
    }
    const created = await fb.run(() => createAssessment(payload), "Assessment created.")
    if (created) { setAssessmentForm({ title: "", component: "continuous", max_score: 100, weight: "" }); loadCourseDetail(selectedId) }
  }

  const startEditAssessment = (assessment) => {
    setEditAssessmentId(assessment.id)
    setAssessmentForm({ title: assessment.title || "", component: assessment.component || "continuous", max_score: assessment.max_score ?? 100, weight: assessment.weight ?? "" })
  }

  const cancelEditAssessment = () => { setEditAssessmentId(null); setAssessmentForm({ title: "", component: "continuous", max_score: 100, weight: "" }) }

  const removeAssessment = async (assessment) => {
    if (!window.confirm(`Delete assessment "${assessment.title}" and any marks entered for it?`)) return
    const ok = await fb.run(() => deleteAssessment(assessment.id), "Assessment deleted.")
    if (ok !== null) loadCourseDetail(selectedId)
  }

  const toggleRelease = async (assessment) => {
    const next = !assessment.is_released
    if (next && !window.confirm(`Release "${assessment.title}" results to students?`)) return
    const ok = await fb.run(() => releaseAssessment(assessment.id, next), next ? "Results released to students." : "Results withdrawn from students.")
    if (ok !== null) loadCourseDetail(selectedId)
  }

  const openMarks = async (assessment) => {
    setMarksBusy(true)
    try {
      const data = await getAssessmentResults(assessment.id)
      const existing = {}
      ;(data?.results || []).forEach(r => { existing[r.student_id] = r.score ?? "" })
      const rows = courseStudents.map(s => ({ student_id: s.id, name: s.name, index_number: s.index_number, score: existing[s.id] ?? "" }))
      setMarksModal({ assessment, rows })
    } catch (e) { fb.setError(e.message) } finally { setMarksBusy(false) }
  }

  const saveMarks = async () => {
    if (!marksModal) return
    setMarksBusy(true); fb.setError("")
    try {
      const marks = marksModal.rows.map(r => ({ student_id: r.student_id, score: r.score === "" ? null : Number(r.score) }))
      await enterMarks(marksModal.assessment.id, marks)
      fb.setNotice(`Marks saved for ${marksModal.assessment.title}.`)
      setMarksModal(null); loadCourseDetail(selectedId)
    } catch (e) { fb.setError(e.message) } finally { setMarksBusy(false) }
  }

  const review = async (id, status) => {
    const ok = await fb.run(() => reviewEnrolment(id, status), `Enrolment ${status}.`)
    if (ok !== null) loadCourseDetail(selectedId)
  }
  const copyCode = async (code) => { try { await navigator.clipboard.writeText(code); fb.setNotice("Registration code copied.") } catch { fb.setError("Clipboard unavailable.") } }
  const rotate = async (course) => {
    if (!window.confirm(`Rotate the registration code for ${course.code}?`)) return
    const ok = await fb.run(() => rotateCourseCode(course.id), "New registration code generated.")
    if (ok !== null) loadCourses()
  }
  const exportRegister = () => {
    const cols = ["student_name", "index_number", "email", "course_code", "date", "period", "status", "marked_by", "timestamp"]
    const rows = courseRegister.map(r => cols.map(k => `"${String(r[k] ?? "").replaceAll('"', '""')}"`).join(","))
    const csv = [cols.join(","), ...rows].join("\n")
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }))
    const a = document.createElement("a"); a.href = url; a.download = `${selectedCourse?.code || "course"}-attendance.csv`; a.click(); URL.revokeObjectURL(url)
  }

  const classState = (course) => {
    const now = new Date(); const today = (now.getDay() + 6) % 7; const hhmm = now.toTimeString().slice(0, 5)
    const todays = (course.schedules || []).filter(s => Number(s.day_of_week) === today)
    if (todays.some(s => s.start_time <= hhmm && s.end_time >= hhmm)) return "live"
    if (todays.some(s => s.start_time > hhmm)) return "upcoming"
    if (todays.length && todays.every(s => s.end_time < hhmm)) return "completed"
    return "all"
  }
  const filteredCourses = courses.filter(c => {
    const q = `${c.title} ${c.code} ${c.programme_name || ""}`.toLowerCase().includes(query.toLowerCase())
    const state = classState(c)
    return q && (courseFilter === "all" || state === courseFilter)
  })
  const tabs = [
    ["overview", "Overview"], ["students", `Students (${courseStudents.length})`],
    ["requests", `Enrolment requests (${courseEnrolments.filter(e => e.status === "pending").length})`],
    ["attendance", `Attendance (${courseRegister.length})`], ["sessions", `Sessions (${courseSessions.length})`],
    ["materials", `Materials (${materials.length})`], ["assessments", `Assessments (${assessments.length})`],
  ]

  if (selectedCourse) return <>
    <div className="course-detail-heading">
      <button className="refresh-btn" onClick={returnToCourses}><ArrowLeft size={16}/> Back to My Courses</button>
      <div className="course-detail-title"><span className="course-mark">{selectedCourse.code?.slice(0,2)}</span><div><h2>{selectedCourse.title}</h2><p>{selectedCourse.code} · Level {selectedCourse.level || "—"} · {selectedCourse.credit_hours ?? "—"} credits</p></div></div>
      <div className="course-actions"><button onClick={() => copyCode(selectedCourse.registration_code)}><Copy size={15}/> Copy registration code</button><button onClick={() => rotate(selectedCourse)}><RefreshCw size={15}/> Rotate code</button><button className="danger-link" onClick={() => removeCourse(selectedCourse)}><Trash2 size={15}/> Delete course</button></div>
    </div>
    <nav className="course-detail-tabs" aria-label="Course sections">{tabs.map(([id, label]) => <button key={id} className={detailTab === id ? "active" : ""} onClick={() => setDetailTab(id)}>{label}</button>)}</nav>
    {detailLoading ? <div className="academic-panel">Loading this course workspace…</div> : <>
      {detailTab === "overview" && <>
        <section className="academic-panel"><div className="panel-title"><div><h2>Course overview</h2><p>Only information belonging to {selectedCourse.code} is shown here.</p></div><button className="primary-btn" onClick={() => startEditCourse(selectedCourse)}><Pencil size={15}/> Edit course details</button></div>
          {editCourseOpen && <form className="course-form mb-5" onSubmit={saveCourseEdits}>
            <input placeholder="Course title" value={editCourseForm.title} onChange={e=>setEditCourseForm(v=>({...v,title:e.target.value}))} required/>
            <select value={editCourseForm.programme_id} onChange={e=>setEditCourseForm(v=>({...v,programme_id:e.target.value}))} required><option value="">Select eligible programme</option>{directory.programmes.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
            
            <select value={editCourseForm.level} onChange={e=>setEditCourseForm(v=>({...v,level:e.target.value}))}>{[100,200,300,400,500,600,700].map(l=><option key={l} value={l}>Level {l}</option>)}</select>
            <select value={editCourseForm.semester} onChange={e=>setEditCourseForm(v=>({...v,semester:e.target.value}))}><option>First Semester</option><option>Second Semester</option></select>
            <input placeholder="Academic year" value={editCourseForm.academic_year} onChange={e=>setEditCourseForm(v=>({...v,academic_year:e.target.value}))} required/>
            <input type="number" min="0" max="30" placeholder="Credit hours" value={editCourseForm.credit_hours} onChange={e=>setEditCourseForm(v=>({...v,credit_hours:e.target.value}))}/>
            <input className="wide" placeholder="Course description (optional)" value={editCourseForm.description} onChange={e=>setEditCourseForm(v=>({...v,description:e.target.value}))}/>
            <label><input type="checkbox" checked={editCourseForm.registration_open} onChange={e=>setEditCourseForm(v=>({...v,registration_open:e.target.checked}))}/> Registration open</label>
            <label><input type="checkbox" checked={editCourseForm.enrolment_requires_approval} onChange={e=>setEditCourseForm(v=>({...v,enrolment_requires_approval:e.target.checked}))}/> Lecturer approval required</label>
            <label><input type="checkbox" checked={editCourseForm.is_published} onChange={e=>setEditCourseForm(v=>({...v,is_published:e.target.checked}))}/> Visible to students</label>
            <button className="primary-btn"><Pencil size={15}/> Save course details</button>
            <button type="button" className="refresh-btn" onClick={()=>setEditCourseOpen(false)}>Cancel</button>
          </form>}
          <div className="course-detail-stats"><div><strong>{selectedCourse.enrolled_count || 0}</strong><span>Approved students</span></div><div><strong>{selectedCourse.pending_count || 0}</strong><span>Pending requests</span></div><div><strong>{courseRegister.length}</strong><span>Attendance records</span></div><div><strong>{courseSessions.length}</strong><span>Attendance sessions</span></div></div>
          <p className="course-detail-description">{selectedCourse.description || "No course description has been added."}</p>
          <div className="panel-title mt-5"><div><h2>Class schedule</h2><p>Scheduled classes are informational and do not restrict when you can open attendance.</p></div><button className="primary-btn" onClick={() => { setEditScheduleId(null); setShowSchedule(v => !v) }}><Plus size={15}/> Add schedule</button></div>
          {(selectedCourse.schedules || []).length ? <div className="table-wrap"><table><thead><tr><th>Day</th><th>Time</th><th>Venue</th><th>Type</th><th>Actions</th></tr></thead><tbody>{selectedCourse.schedules.map(s=><tr key={s.id}><td>{s.day_name || DAYS[s.day_of_week]}</td><td>{s.start_time}–{s.end_time}</td><td>{s.venue_name || s.room_no || "—"}</td><td>{s.class_type || "Lecture"}</td><td><div className="row-actions"><button title="Edit schedule" onClick={()=>startEditSchedule(s)}><Pencil size={15}/></button><button title="Remove schedule" onClick={()=>removeSchedule(s)}><Trash2 size={15}/></button></div></td></tr>)}</tbody></table></div> : <div className="empty-state">No schedule has been added for this course.</div>}
          {showSchedule && <form className="course-form mt-4" onSubmit={createSchedule}><select value={scheduleForm.day_of_week} onChange={e=>setScheduleForm(v=>({...v,day_of_week:e.target.value}))}>{DAYS.map((d,i)=><option key={d} value={i}>{d}</option>)}</select><input type="time" value={scheduleForm.start_time} onChange={e=>setScheduleForm(v=>({...v,start_time:e.target.value}))} required/><input type="time" value={scheduleForm.end_time} onChange={e=>setScheduleForm(v=>({...v,end_time:e.target.value}))} required/><input placeholder="Building" value={scheduleForm.building} onChange={e=>setScheduleForm(v=>({...v,building:e.target.value}))} required/><input placeholder="Room" value={scheduleForm.room_no} onChange={e=>setScheduleForm(v=>({...v,room_no:e.target.value}))} required/><select value={scheduleForm.class_type} onChange={e=>setScheduleForm(v=>({...v,class_type:e.target.value}))}><option value="theory">Lecture</option><option value="lab">Laboratory</option><option value="seminar">Seminar</option></select><button className="primary-btn"><CalendarDays size={15}/> {editScheduleId ? "Update schedule" : "Save schedule"}</button>{editScheduleId && <button type="button" className="refresh-btn" onClick={()=>{setEditScheduleId(null); setShowSchedule(false)}}>Cancel edit</button>}</form>}
          <div className="course-actions mt-4"><Link className="primary-btn" to={`/faculty/attendance?course_id=${selectedCourse.id}`}>Open attendance controls <QrCode size={15}/></Link></div>
        </section>
      </>}
      {detailTab === "students" && <section className="academic-panel"><div className="panel-title"><div><h2>Students in {selectedCourse.code}</h2><p>Only approved students enrolled in this course.</p></div><Users/></div><div className="table-wrap"><table><thead><tr><th>Student</th><th>Index number</th><th>Programme</th><th>Level</th><th>Batch</th></tr></thead><tbody>{courseStudents.map(s=><tr key={s.id}><td><Link className="text-blue-700 underline font-semibold" to={`/profiles/${s.id}`}>{s.name}</Link><small>{s.email}</small></td><td>{s.index_number || "—"}</td><td>{s.programme || "—"}</td><td>{s.level || "—"}</td><td>{s.batch_name || "—"}</td></tr>)}{!courseStudents.length && <tr><td colSpan="5">No approved students are enrolled in this course.</td></tr>}</tbody></table></div></section>}
      {detailTab === "requests" && <section className="academic-panel"><div className="panel-title"><div><h2>Enrolment requests</h2><p>Requests for {selectedCourse.code} only.</p></div><ShieldCheck/></div><div className="table-wrap"><table><thead><tr><th>Student</th><th>Index number</th><th>Requested</th><th>Status</th><th>Action</th></tr></thead><tbody>{courseEnrolments.map(e=><tr key={e.id}><td><Link className="text-blue-700 underline font-semibold" to={`/profiles/${e.student_id}`}>{e.student_name}</Link><small>{e.email}</small></td><td>{e.index_number || "—"}</td><td>{e.requested_at ? new Date(e.requested_at).toLocaleString() : "—"}</td><td><span className={`status-${e.status}`}>{e.status}</span></td><td>{e.status === "pending" ? <div className="row-actions"><button title="Approve" onClick={()=>review(e.id,"approved")}><Check size={16}/></button><button title="Reject" onClick={()=>review(e.id,"rejected")}><X size={16}/></button></div> : "—"}</td></tr>)}{!courseEnrolments.length && <tr><td colSpan="5">No enrolment requests for this course.</td></tr>}</tbody></table></div></section>}
      {detailTab === "attendance" && <section className="academic-panel"><div className="panel-title"><div><h2>{selectedCourse.code} attendance register</h2><p>Attendance records belonging to this course only.</p></div><button className="refresh-btn" onClick={exportRegister}><Download size={15}/> Export CSV</button></div><div className="table-wrap"><table><thead><tr><th>Student</th><th>Index number</th><th>Date</th><th>Period</th><th>Status</th><th>Recorded by</th></tr></thead><tbody>{courseRegister.map(r=><tr key={r.id}><td><Link className="text-blue-700 underline" to={`/profiles/${r.student_id}`}>{r.student_name}</Link><small>{r.email}</small></td><td>{r.index_number || "—"}</td><td>{r.date}</td><td>{r.period || "—"}</td><td><span className={`status-${r.status}`}>{r.status}</span></td><td>{r.marked_by || "—"}</td></tr>)}{!courseRegister.length && <tr><td colSpan="6">No attendance records for this course yet.</td></tr>}</tbody></table></div></section>}
      {detailTab === "sessions" && <section className="academic-panel"><div className="panel-title"><div><h2>Attendance sessions</h2><p>Live and previous sessions opened for {selectedCourse.code}.</p></div><QrCode/></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Period</th><th>Opened</th><th>Expires</th><th>Status</th></tr></thead><tbody>{courseSessions.map(s=><tr key={s.id}><td>{s.date}</td><td>{s.period || "—"}</td><td>{s.opened_at ? new Date(s.opened_at).toLocaleString() : "—"}</td><td>{s.expires_at ? new Date(s.expires_at).toLocaleString() : "—"}</td><td><span className={s.is_open ? "status-approved" : "status-rejected"}>{s.is_open ? "Open" : "Closed"}</span></td></tr>)}{!courseSessions.length && <tr><td colSpan="5">No attendance sessions have been opened for this course.</td></tr>}</tbody></table></div></section>}
      {detailTab === "materials" && <section className="academic-panel"><div className="panel-title"><div><h2>Learning materials</h2><p>Links and notes shared with students enrolled in {selectedCourse.code}.</p></div><BookOpen/></div>
        <form className="course-form" onSubmit={addMaterial}>
          <input placeholder="Material title" value={materialForm.title} onChange={e=>setMaterialForm(v=>({...v,title:e.target.value}))} required/>
          <select value={materialForm.material_type} onChange={e=>setMaterialForm(v=>({...v,material_type:e.target.value}))}><option value="link">Link</option><option value="note">Note</option><option value="file">File reference</option></select>
          <input className="wide" placeholder="URL (optional)" value={materialForm.url} onChange={e=>setMaterialForm(v=>({...v,url:e.target.value}))}/>
          <input className="wide" placeholder="Description (optional)" value={materialForm.description} onChange={e=>setMaterialForm(v=>({...v,description:e.target.value}))}/>
          <button className="primary-btn">{editMaterialId ? <><Pencil size={15}/> Save changes</> : <><Plus size={15}/> Add material</>}</button>
          {editMaterialId && <button type="button" className="refresh-btn" onClick={()=>{setEditMaterialId(null); setMaterialForm({ title: "", description: "", url: "", material_type: "link" })}}>Cancel edit</button>}
        </form>
        <div className="table-wrap"><table><thead><tr><th>Title</th><th>Type</th><th>Link</th><th>Added</th><th>Actions</th></tr></thead><tbody>
          {materials.map(m=><tr key={m.id}><td>{m.title}<small>{m.description||""}</small></td><td>{m.material_type||"link"}</td><td>{m.url?<a className="text-blue-700 underline" href={m.url} target="_blank" rel="noreferrer">Open</a>:"—"}</td><td>{m.created_at?new Date(m.created_at).toLocaleDateString():"—"}</td><td><div className="row-actions"><button title="Edit material" onClick={()=>startEditMaterial(m)}><Pencil size={15}/></button><button title="Remove material" onClick={()=>removeMaterial(m)}><Trash2 size={15}/></button></div></td></tr>)}
          {!materials.length && <tr><td colSpan="5">No learning materials have been added for this course.</td></tr>}
        </tbody></table></div>
      </section>}
      {detailTab === "assessments" && <section className="academic-panel"><div className="panel-title"><div><h2>Assessments</h2><p>Continuous-assessment components for {selectedCourse.code}. Enter marks, then release them to students.</p></div><ClipboardList/></div>
        <form className="course-form" onSubmit={addAssessment}>
          <input placeholder="Assessment title (e.g. Assignment 1)" value={assessmentForm.title} onChange={e=>setAssessmentForm(v=>({...v,title:e.target.value}))} required/>
          <select value={assessmentForm.component} onChange={e=>setAssessmentForm(v=>({...v,component:e.target.value}))}>{["assignment","quiz","test","mid_sem","practical","project","final_exam","continuous"].map(c=><option key={c} value={c}>{c.replaceAll("_"," ")}</option>)}</select>
          <input type="number" min="1" max="1000" placeholder="Max score" value={assessmentForm.max_score} onChange={e=>setAssessmentForm(v=>({...v,max_score:e.target.value}))}/>
          <input type="number" min="0" max="100" placeholder="Weight % (optional)" value={assessmentForm.weight} onChange={e=>setAssessmentForm(v=>({...v,weight:e.target.value}))}/>
          <button className="primary-btn" disabled={marksBusy}>{editAssessmentId ? <><Pencil size={15}/> Save changes</> : <><Plus size={15}/> Create assessment</>}</button>
          {editAssessmentId && <button type="button" className="refresh-btn" onClick={cancelEditAssessment}>Cancel edit</button>}
        </form>
        <div className="table-wrap"><table><thead><tr><th>Title</th><th>Component</th><th>Max score</th><th>Weight</th><th>Marks entered</th><th>Released</th><th>Actions</th></tr></thead><tbody>
          {assessments.map(a=><tr key={a.id}><td>{a.title}</td><td>{(a.component||"").replaceAll("_"," ")}</td><td>{a.max_score}</td><td>{a.weight??"—"}</td><td>{a.marks_entered??0}</td><td><span className={a.is_released?"status-approved":"status-pending"}>{a.is_released?"released":"draft"}</span></td><td><div className="row-actions"><button title="Enter marks" disabled={marksBusy} onClick={()=>openMarks(a)}><ClipboardList size={15}/></button><button title={a.is_released?"Withdraw results":"Release results"} onClick={()=>toggleRelease(a)}>{a.is_released?<X size={15}/>:<Upload size={15}/>}</button><button title="Edit assessment" onClick={()=>startEditAssessment(a)}><Pencil size={15}/></button><button title="Delete assessment" onClick={()=>removeAssessment(a)}><Trash2 size={15}/></button></div></td></tr>)}
          {!assessments.length && <tr><td colSpan="7">No assessments have been created for this course.</td></tr>}
        </tbody></table></div>
        <p className="text-sm text-slate-500 mt-3">Use the marks button to record scores for enrolled students, then release the results when they are ready to be seen.</p>
      </section>}
      {marksModal && <div className="fixed inset-0 z-[60] grid place-items-center bg-black/60 p-4" onClick={()=>setMarksModal(null)}><div className="max-w-2xl w-full rounded-2xl bg-white p-5 max-h-[85vh] overflow-y-auto" onClick={e=>e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between"><div><h2 className="text-lg font-bold">Marks · {marksModal.assessment.title}</h2><p className="text-sm text-slate-500">Score out of {marksModal.assessment.max_score}. Leave blank to clear a mark.</p></div><button className="text-blue-700" onClick={()=>setMarksModal(null)}>Close</button></div>
        {marksModal.rows.length ? <div className="table-wrap"><table><thead><tr><th>Student</th><th>Index number</th><th>Score</th></tr></thead><tbody>{marksModal.rows.map((r,idx)=><tr key={r.student_id}><td><Link className="text-blue-700 underline" to={`/profiles/${r.student_id}`}>{r.name}</Link></td><td>{r.index_number||"—"}</td><td><input className="w-28 border rounded-lg p-1.5" type="number" min="0" max={marksModal.assessment.max_score} step="0.5" value={r.score} onChange={e=>setMarksModal(m=>({...m,rows:m.rows.map((row,i)=>i===idx?{...row,score:e.target.value}:row)}))}/></td></tr>)}</tbody></table></div> : <p className="text-sm text-slate-500">No approved students are enrolled in this course yet.</p>}
        <div className="mt-4 flex justify-end gap-3"><button className="refresh-btn" onClick={()=>setMarksModal(null)}>Cancel</button><button className="primary-btn" disabled={marksBusy||!marksModal.rows.length} onClick={saveMarks}>{marksBusy?"Saving…":"Save marks"}</button></div>
      </div></div>}

    </>}
  </>

  return <>
    <div className="panel-title lecturer-course-list-head"><div><h2>My Courses</h2><p>Open a course to manage its students, enrolment requests, attendance and reports.</p></div><button className="primary-btn" onClick={() => setShowCreate(v => !v)}><Plus size={16}/> Create course</button></div>
    {showCreate && <section className="academic-panel"><div className="panel-title"><div><h2>Create a course</h2><p>Set up a course under your lecturer account.</p></div><button className="refresh-btn" onClick={()=>setShowCreate(false)}>Close</button></div><form className="course-form" onSubmit={createLecturerCourse}><input placeholder="Course title" value={courseForm.title} onChange={e=>setCourseForm(v=>({...v,title:e.target.value}))} required/><input placeholder="Course code (e.g. CSC 301)" value={courseForm.code} onChange={e=>setCourseForm(v=>({...v,code:e.target.value}))} required/><select value={courseForm.programme_id} onChange={e=>setCourseForm(v=>({...v,programme_id:e.target.value}))} required><option value="">Select eligible programme</option>{directory.programmes.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><select value={courseForm.level} onChange={e=>setCourseForm(v=>({...v,level:e.target.value}))}>{[100,200,300,400,500,600,700].map(l=><option key={l} value={l}>Level {l}</option>)}</select><select value={courseForm.semester} onChange={e=>setCourseForm(v=>({...v,semester:e.target.value}))}><option>First Semester</option><option>Second Semester</option></select><input placeholder="Academic year (e.g. 2026/2027)" value={courseForm.academic_year} onChange={e=>setCourseForm(v=>({...v,academic_year:e.target.value}))} required/><input type="number" min="0" max="30" value={courseForm.credit_hours} onChange={e=>setCourseForm(v=>({...v,credit_hours:e.target.value}))} placeholder="Credit hours"/><button className="primary-btn"><Plus size={15}/> Create course</button></form></section>}
    <div className="toolbar"><label className="search-box"><Search size={17}/><input placeholder="Search your courses" value={query} onChange={e=>setQuery(e.target.value)}/></label><select value={courseFilter} onChange={e=>setCourseFilter(e.target.value)}><option value="all">All courses</option><option value="live">Live today</option><option value="upcoming">Upcoming today</option><option value="completed">Completed today</option></select><button className="refresh-btn" onClick={loadCourses} disabled={loading}><RefreshCw size={15}/> Refresh</button></div>
    {loading ? <div className="academic-panel">Loading your courses…</div> : <div className="course-grid">{filteredCourses.map(c=>{const state=classState(c);return <button type="button" className="course-card lecturer-course-card" key={c.id} onClick={()=>openCourse(c)}><div className="course-top"><span className="course-mark">{c.code?.slice(0,2)}</span><span className={`course-state ${state}`}>{state === "all" ? "No class today" : state === "live" ? "Live" : state === "upcoming" ? "Upcoming" : "Completed"}</span></div><h3>{c.title}</h3><p className="course-code">{c.code} · Level {c.level || "—"}</p><div className="course-meta"><span><Users size={15}/> {c.enrolled_count || 0} students · {c.pending_count || 0} pending</span></div><div className="course-schedule-summary">{c.schedules?.length ? c.schedules.map(slot=><small key={slot.id}>{slot.day_name || DAYS[slot.day_of_week]} · {slot.start_time}–{slot.end_time} · {slot.venue_name || slot.room_no}</small>) : <small>No class schedule added yet.</small>}</div><span className="course-open-link">Open course <ArrowRight size={15}/></span></button>})}{!filteredCourses.length && <div className="empty-state">{courses.length ? "No courses match this filter." : "You have not created any courses yet. Create your first course to get started."}</div>}</div>}
  </>
}

// ───────────────────────────── Student workspace ─────────────────────────────
function StudentWorkspace({ fb }) {
  const [myCourses, setMyCourses] = useState([])
  const [joinCode, setJoinCode] = useState("")
  const [joining, setJoining] = useState(false)
  const [coursePreview, setCoursePreview] = useState(null)
  const [joinBatch, setJoinBatch] = useState("")
  const [enrolments, setEnrolments] = useState([])
  const [results, setResults] = useState([])
  const [batchDraft, setBatchDraft] = useState({})

  const load = useCallback(async () => {
    try {
      const [mc, e, res] = await Promise.all([getStudentCourses(), listEnrolments(), getMyResults().catch(() => [])])
      setMyCourses(mc); setEnrolments(e); setResults(res || [])
    } catch (e) { fb.setError(e.message); fb.setRetry(() => load) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { load() }, [load])
  useRealtime((event) => {
    if (["courses", "enrolments", "timetable", "materials", "results"].includes(event.type)) load()
  })

  const findCourse = async (e) => {
    e.preventDefault(); if (!joinCode.trim()) return
    setJoining(true); setCoursePreview(null)
    const result = await fb.run(() => previewCourseByRegistrationCode(joinCode.trim()), "Course found. Review the details before registering.")
    if (result) { setCoursePreview(result); setJoinBatch("") }
    setJoining(false)
  }

  const joinCourse = async () => {
    setJoining(true)
    if (coursePreview?.batches?.length && !joinBatch) { fb.setError("Select a class batch before registering."); setJoining(false); return }
    const result = await fb.run(() => enrolByRegistrationCode(joinCode.trim(), joinBatch ? Number(joinBatch) : null), "Course enrolment request submitted.")
    if (result) { setJoinCode(""); setCoursePreview(null); setJoinBatch(""); load() }
    setJoining(false)
  }

  const withdraw = async (enrolment) => {
    if (!window.confirm(`Withdraw from ${enrolment.course_code}? You can re-register later if the window is open.`)) return
    await fb.run(() => withdrawCourse(enrolment.id), `Withdrawn from ${enrolment.course_code}.`)
    load()
  }

  const changeBatchFor = async (course) => {
    const target = batchDraft[course.enrolment_id]
    if (!target) { fb.setError("Choose a batch to switch to."); return }
    const ok = await fb.run(() => changeBatch(course.enrolment_id, Number(target)), `Batch changed for ${course.code}.`)
    if (ok !== null) { setBatchDraft(v => ({ ...v, [course.enrolment_id]: "" })); load() }
  }


  return (
    <>
      <section className="academic-panel">
        <div className="panel-title"><div><h2>Join a course</h2><p>Enter the registration code given to you by your lecturer.</p></div><BookOpen /></div>
        <form className="course-form" onSubmit={findCourse}>
          <input className="wide" value={joinCode} onChange={e=>{setJoinCode(e.target.value);setCoursePreview(null);}} placeholder="Enter course registration code" required />
          <button className="primary-btn" disabled={joining}>{joining ? "Checking code…" : "Find course"}<Search size={15}/></button>
        </form>
        {coursePreview && <article className="course-card mt-4"><div className="course-top"><span className="course-mark">{coursePreview.code?.slice(0,2)}</span><span className="pill-open">Registration open</span></div><h3>{coursePreview.title}</h3><p className="course-code">{coursePreview.code} · Level {coursePreview.level||"—"} · {coursePreview.semester||"—"}</p><div className="course-meta"><span><Users size={15}/> {coursePreview.lecturer_id ? <Link className="text-blue-700 underline" to={`/profiles/${coursePreview.lecturer_id}`}>{coursePreview.lecturer_name||"Lecturer"}</Link> : (coursePreview.lecturer_name||"Lecturer")}</span><span><Layers size={15}/> {coursePreview.programme_name||"Eligible programme"}</span></div>{coursePreview.batches?.length>0 && <label className="block text-sm font-medium mt-3">Choose class batch<select className="block w-full mt-1 border rounded-lg p-2" value={joinBatch} onChange={e=>setJoinBatch(e.target.value)}><option value="">Select batch</option>{coursePreview.batches.map(b=><option key={b.id} value={b.id}>{b.name}{b.capacity?` · ${b.enrolled_count}/${b.capacity}`:""}</option>)}</select></label>}<p className="text-sm text-slate-500">{coursePreview.enrolment_requires_approval?"Your lecturer must approve this request before the course becomes available for attendance.":"Your enrolment will be activated immediately."}</p><button type="button" className="primary-btn" onClick={joinCourse} disabled={joining}>{joining?"Submitting…":"Register for this course"}<Plus size={15}/></button></article>}
        <p className="text-sm text-slate-500 mt-2">The code is checked against the course, institution, programme, level and registration window. Only approved enrolments can mark attendance.</p>
      </section>

      <section className="academic-panel">
        <div className="panel-title"><div><h2>My courses</h2><p>{myCourses.length} registered course(s)</p></div><ClipboardList /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Course</th><th>Code</th><th>Schedule & venue</th><th>Batch</th><th>Credits</th><th>Action</th></tr></thead>
            <tbody>
              {myCourses.map((c) => (
                <tr key={c.enrolment_id || c.id}>
                  <td>{c.title}<small className="block">Lecturer: {c.lecturer_id ? <Link className="text-blue-700 underline" to={`/profiles/${c.lecturer_id}`}>{c.lecturer_name||"View profile"}</Link> : (c.lecturer_name||"—")}</small></td><td>{c.code}</td><td>{c.schedules?.length ? c.schedules.map(s=><small key={s.id} className="block">{s.day_name} · {s.start_time}–{s.end_time} · {s.venue_name || s.room_no}</small>) : "Not scheduled yet"}</td><td>{c.batch_name || "—"}{c.enrolment_status==="approved" && (c.batches?.length||0) > 1 && <div className="mt-1 flex items-center gap-1"><select className="border rounded p-1 text-xs" value={batchDraft[c.enrolment_id]||""} onChange={e=>setBatchDraft(v=>({...v,[c.enrolment_id]:e.target.value}))}><option value="">Change batch…</option>{c.batches.filter(b=>b.id!==c.batch_id).map(b=><option key={b.id} value={b.id}>{b.name}{b.capacity?` · ${b.enrolled_count}/${b.capacity}`:""}</option>)}</select><button className="text-xs text-blue-700 underline" onClick={()=>changeBatchFor(c)}>Save</button></div>}</td><td>{c.credit_hours ?? "—"}</td>
                  <td><div className="row-actions"><button title="Withdraw" onClick={() => withdraw({ id: c.enrolment_id, course_code: c.code })}><Trash2 size={15} /></button></div></td>
                </tr>
              ))}
              {!myCourses.length && <tr><td colSpan="6">You have not registered for any courses yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>





      <section className="academic-panel">
        <div className="panel-title"><div><h2>My enrolments</h2><p>{enrolments.length} record(s)</p></div><ShieldCheck /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Course</th><th>Code</th><th>Batch</th><th>Requested</th><th>Status</th></tr></thead>
            <tbody>
              {enrolments.map((e) => (
                <tr key={e.id}><td>{e.course}</td><td>{e.course_code}</td><td>{e.batch_name || "—"}</td>
                  <td>{new Date(e.requested_at).toLocaleString()}</td>
                  <td><span className={`status-${e.status}`}>{e.status}</span></td></tr>
              ))}
              {!enrolments.length && <tr><td colSpan="5">You have not registered for any courses yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="academic-panel">
        <div className="panel-title"><div><h2>My results</h2><p>Released assessment marks for your approved courses.</p></div><ClipboardList /></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Course</th><th>Assessment</th><th>Component</th><th>Score</th><th>Grade</th><th>Remark</th></tr></thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={`${r.course_id}-${i}`}><td>{r.course_code||"—"}<small className="block">{r.course_title||""}</small></td><td>{r.assessment}</td><td>{(r.component||"").replaceAll("_"," ")}</td><td>{r.score ?? "—"} / {r.max_score}</td><td>{r.grade || "—"}</td><td>{r.remark || "—"}</td></tr>
              ))}
              {!results.length && <tr><td colSpan="6">No released results yet. Your lecturer will release marks when they are ready.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>


    </>
  )
}

const HEADINGS = {
  admin: { title: "Platform course oversight", blurb: "Review courses, enrolments and attendance activity across lecturers and institutions." },
  lecturer: { title: "My courses", blurb: "Create courses, schedule classes, manage enrolments and review attendance evidence." },
  student: { title: "My courses", blurb: "Join a course using your lecturer’s code and review your attendance-ready enrolments." },
}

export default function AcademicHub({ mode }) {
  const fb = useFeedback()
  const heading = HEADINGS[mode] || HEADINGS.student
  const { status } = useRealtime()

  return (
    <MainLayout><main className="academic-page">
      <header className="academic-heading">
        <div>
          <span className="eyebrow">SMART CAMPUS / ACADEMICS</span>
          <h1>{heading.title}</h1>
          <p>{heading.blurb}</p>
        </div>
        <span className={`sc-live ${status}`}><span className="sc-live-dot" /> {status === "live" ? "Live" : status === "offline" ? "Offline" : "Connecting"}</span>
      </header>
      {fb.error && <div className="academic-alert error" role="alert"><span>{fb.error}</span>{fb.retry && <button type="button" className="refresh-btn ml-3" onClick={() => fb.retry?.()}><RefreshCw size={14}/> Try again</button>}</div>}
      {fb.notice && <div className="academic-alert success">{fb.notice}</div>}

      {mode === "admin" && <AdminWorkspace fb={fb} />}
      {mode === "lecturer" && <LecturerWorkspace fb={fb} />}
      {mode === "student" && <StudentWorkspace fb={fb} />}
    </main></MainLayout>
  )
}
