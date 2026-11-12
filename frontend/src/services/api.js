import { getToken } from "../utils/session"

export const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "")

function authHeaders() {
  const token = getToken()
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

function tokenExpired(token) {
  try {
    const encoded = token?.split(".")[1]
    if (!encoded) return true
    const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")))
    return !payload.exp || Number(payload.exp) * 1000 <= Date.now()
  } catch {
    return true
  }
}

export async function apiFetch(path, options = {}) {
  const activeToken = getToken()
  if (path !== "/login" && activeToken && tokenExpired(activeToken)) {
    window.dispatchEvent(new CustomEvent("smart-campus:unauthorized"))
    throw new Error("Your session has expired. Please sign in again.")
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  })
  const raw = await res.text()
  let data = {}
  try { data = raw ? JSON.parse(raw) : {} } catch { data = { detail: raw || res.statusText } }
  if (res.status === 401 && path !== "/login") {
    window.dispatchEvent(new CustomEvent("smart-campus:unauthorized"))
  }
  if (!res.ok) {
    const detail = data.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join("; ")
      : typeof detail === "string" ? detail : data.message || `Request failed (${res.status})`
    const error = new Error(message)
    error.status = res.status
    throw error
  }
  return data
}

// ─── Auth ────────────────────────────────────────────────
export const loginUser     = (email, password, role) =>
  apiFetch("/login", { method: "POST", body: JSON.stringify({ email, password, selected_role: role }) })

export const signupStudent = (payload) =>
  apiFetch("/student/signup", { method: "POST", body: JSON.stringify(payload) })

export const getAcademicDirectory = (admin = false, institutionName = "") => apiFetch(admin ? "/admin/academic-directory" : `/public/academic-directory${institutionName ? `?institution_name=${encodeURIComponent(institutionName)}` : ""}`)
export const getMyAcademicDirectory = () => apiFetch("/academic/academic-directory")
export const adminDeleteFaculty = (id) => apiFetch(`/admin/academic/faculties/${id}`, { method: "DELETE" })
export const adminDeleteDepartment = (id) => apiFetch(`/admin/academic/departments/${id}`, { method: "DELETE" })
export const adminDeleteProgramme = (id) => apiFetch(`/admin/academic/programmes/${id}`, { method: "DELETE" })
export const previewAcademicDirectoryReset = (institutionName) => apiFetch(`/admin/academic-directory/reset-preview?institution_name=${encodeURIComponent(institutionName)}`)
export const resetAcademicDirectory = (institutionName, confirmation) => apiFetch("/admin/academic-directory/reset", { method: "POST", body: JSON.stringify({ institution_name: institutionName, confirmation }) })
export const getInstitutions = () => apiFetch("/public/institutions")
export const createFaculty = (body) => apiFetch("/academic/faculties", { method: "POST", body: JSON.stringify(body) })
export const updateFaculty = (id, body) => apiFetch(`/academic/faculties/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteFaculty = (id) => apiFetch(`/academic/faculties/${id}`, { method: "DELETE" })
export const createDepartment = (body) => apiFetch("/academic/departments", { method: "POST", body: JSON.stringify(body) })
export const updateDepartment = (id, body) => apiFetch(`/academic/departments/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteDepartment = (id) => apiFetch(`/academic/departments/${id}`, { method: "DELETE" })
export const createProgramme = (body) => apiFetch("/academic/programmes", { method: "POST", body: JSON.stringify(body) })
export const updateProgramme = (id, body) => apiFetch(`/academic/programmes/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteProgramme = (id) => apiFetch(`/academic/programmes/${id}`, { method: "DELETE" })

// ─── Realtime (Server-Sent Events) ───────────────────────
export const eventStreamUrl = (token = getToken()) => token
  ? `${BASE_URL}/events?token=${encodeURIComponent(token)}`
  : null

// ─── Notifications ───────────────────────────────────────
export const getNotifications = () => apiFetch("/notifications")
export const markNotificationRead = (id) => apiFetch(`/notifications/${id}/read`, { method: "POST" })
export const markAllNotificationsRead = () => apiFetch("/notifications/read-all", { method: "POST" })

// ─── Admin: students & faculty ───────────────────────────
export const getPendingStudents = () => apiFetch("/admin/pending-students")
export const approveStudent     = (id) => apiFetch(`/admin/approve/${id}`, { method: "POST" })
export const rejectStudent      = (id) => apiFetch(`/admin/reject/${id}`, { method: "POST" })
export const getAdminStats      = () => apiFetch("/admin/stats")
export const getAuditLogs       = (limit = 200) => apiFetch(`/admin/audit-logs?limit=${limit}`)
export const getAttendanceSummary = () => apiFetch("/admin/attendance-summary")
export const getAdminAttendanceRecords = () => apiFetch("/admin/attendance/records")
export const getSettings        = () => apiFetch("/admin/settings")
export const saveSettings       = (body) => apiFetch("/admin/settings", { method: "PUT", body: JSON.stringify(body) })

// ─── Courses ─────────────────────────────────────────────
export const listCourses    = (q = "") => apiFetch(`/academic/courses${q ? `?q=${encodeURIComponent(q)}` : ""}`)
export const getCourse      = (id) => apiFetch(`/academic/courses/${id}`)
export const createCourse   = (body) => apiFetch("/academic/courses", { method: "POST", body: JSON.stringify(body) })
export const updateCourse   = (id, body) => apiFetch(`/academic/courses/${id}`, { method: "PATCH", body: JSON.stringify(body) })
export const deleteCourse   = (id) => apiFetch(`/academic/courses/${id}`, { method: "DELETE" })
export const rotateCourseCode = (id, expires_in_hours = 168) =>
  apiFetch(`/academic/courses/${id}/registration-code`, { method: "POST", body: JSON.stringify({ expires_in_hours }) })

// ─── Enrolment ───────────────────────────────────────────
export const enrolInCourse  = (course_id, batch_id = null) =>
  apiFetch("/academic/enrol", { method: "POST", body: JSON.stringify({ course_id, batch_id }) })
export const withdrawCourse = (enrolment_id, reason = "") =>
  apiFetch(`/academic/enrol/${enrolment_id}`, { method: "DELETE", body: JSON.stringify({ reason }) })
export const changeBatch = (enrolment_id, batch_id) =>
  apiFetch(`/academic/enrol/${enrolment_id}/batch`, { method: "PATCH", body: JSON.stringify({ batch_id }) })
export const listEnrolments = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
  return apiFetch(`/academic/enrolments${qs ? `?${qs}` : ""}`)
}
export const reviewEnrolment = (id, status) => apiFetch(`/academic/enrolments/${id}`, { method: "PATCH", body: JSON.stringify({ status }) })

// ─── Course batches (admin) ──────────────────────────────
export const listBatches = (courseId) => apiFetch(`/admin/courses/${courseId}/batches`)
export const createBatch = (courseId, body) => apiFetch(`/admin/courses/${courseId}/batches`, { method: "POST", body: JSON.stringify(body) })
export const updateBatch = (batchId, body) => apiFetch(`/admin/batches/${batchId}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteBatch = (batchId) => apiFetch(`/admin/batches/${batchId}`, { method: "DELETE" })

// ─── Timetable ───────────────────────────────────────────
export const listTimetable   = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
  return apiFetch(`/admin/timetable${qs ? `?${qs}` : ""}`)
}
export const createTimetable = (body) => apiFetch("/admin/timetable", { method: "POST", body: JSON.stringify(body) })
export const updateTimetable = (id, body) => apiFetch(`/admin/timetable/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteTimetable = (id) => apiFetch(`/admin/timetable/${id}`, { method: "DELETE" })
export const publishTimetable = (body) => apiFetch("/admin/timetable/publish", { method: "POST", body: JSON.stringify(body) })

// ─── Faculty ─────────────────────────────────────────────
export const generateQR = (facultyId, period, gpsCoords = null) =>
  apiFetch(`/faculty/generate-qr/${facultyId}/${period}`, {
    method: "POST",
    body: JSON.stringify(gpsCoords
      ? { latitude: gpsCoords.lat, longitude: gpsCoords.lng, accuracy: gpsCoords.accuracy ?? 30 }
      : {}
    ),
  })
export const getFacultyAttendance = (period)  => apiFetch(`/faculty/attendance/${period}`)
export const getFacultyTimetable  = (day)     => apiFetch(`/faculty/timetable/${day}`)
export const getMyCourses         = ()        => apiFetch("/faculty/my-courses")
export const getStudentCourses    = ()        => apiFetch("/student/my-courses")
export const getClassList         = (courseId) => apiFetch(`/faculty/class-list${courseId ? `?course_id=${courseId}` : ""}`)
export const getAttendanceRegister = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
  return apiFetch(`/faculty/attendance-register${qs ? `?${qs}` : ""}`)
}

// ─── Attendance sessions (QR + selfie + GPS) ─────────────
export const getAttendanceCourses = () => apiFetch("/faculty/attendance/courses")
export const openAttendanceSession = (body) =>
  apiFetch("/faculty/attendance/sessions", { method: "POST", body: JSON.stringify(body) })
export const closeAttendanceSession = (id) => apiFetch(`/faculty/attendance/sessions/${id}/close`, { method: "POST" })
export const listAttendanceSessions = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
  return apiFetch(`/faculty/attendance/sessions${qs ? `?${qs}` : ""}`)
}
export const getAttendanceSession = (id) => apiFetch(`/faculty/attendance/sessions/${id}`)
export const markAttendance = (body) =>
  apiFetch("/student/attendance/mark", { method: "POST", body: JSON.stringify(body) })
export const getMyAttendance = () => apiFetch("/student/attendance/records")
export const correctAttendance = (id, status, reason) =>
  apiFetch(`/attendance/${id}/correction`, { method: "POST", body: JSON.stringify({ status, reason }) })
export const fetchAttendancePhoto = async (id) => {
  const res = await fetch(`${BASE_URL}/attendance/photo/${id}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(res.status === 403 ? "You are not authorised to view this attendance selfie." : "Attendance selfie could not be loaded.")
  return URL.createObjectURL(await res.blob())
}

// ─── Assessments & results ───────────────────────────────
export const listAssessments = (params = {}) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)).toString()
  return apiFetch(`/assessments${qs ? `?${qs}` : ""}`)
}
export const createAssessment = (body) => apiFetch("/assessments", { method: "POST", body: JSON.stringify(body) })
export const updateAssessment = (id, body) => apiFetch(`/assessments/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteAssessment = (id) => apiFetch(`/assessments/${id}`, { method: "DELETE" })
export const enterMarks = (id, marks, reason = null) =>
  apiFetch(`/assessments/${id}/marks`, { method: "POST", body: JSON.stringify({ marks, reason }) })
export const releaseAssessment = (id, release = true) =>
  apiFetch(`/assessments/${id}/release?release=${release}`, { method: "POST" })
export const getAssessmentResults = (id) => apiFetch(`/assessments/${id}/results`)
export const getMyResults = () => apiFetch("/student/results")

// ─── Grading bands (admin) ───────────────────────────────
export const listGradingBands = () => apiFetch("/admin/grading-bands")
export const createGradingBand = (body) => apiFetch("/admin/grading-bands", { method: "POST", body: JSON.stringify(body) })
export const updateGradingBand = (id, body) => apiFetch(`/admin/grading-bands/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteGradingBand = (id) => apiFetch(`/admin/grading-bands/${id}`, { method: "DELETE" })

// ─── Announcements ───────────────────────────────────────
export const createAnnouncement = (body) => apiFetch("/announcements", { method: "POST", body: JSON.stringify(body) })
export const updateAnnouncement = (id, body) => apiFetch(`/announcements/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteAnnouncement = (id) => apiFetch(`/announcements/${id}`, { method: "DELETE" })
export const listAnnouncements = () => apiFetch("/announcements")
export const listStudentAnnouncements = () => apiFetch("/student/announcements")

// ─── Learning materials ──────────────────────────────────
export const listMaterials  = (courseId) => apiFetch(`/academic/materials${courseId ? `?course_id=${courseId}` : ""}`)
export const createMaterial = (body) => apiFetch("/academic/materials", { method: "POST", body: JSON.stringify(body) })
export const updateMaterial = (id, body) => apiFetch(`/academic/materials/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const deleteMaterial = (id) => apiFetch(`/academic/materials/${id}`, { method: "DELETE" })

// ─── Student ─────────────────────────────────────────────
export const getAttendancePercentage = () => apiFetch("/student/attendance-percentage")
export const getStudentTimetable     = (day) => apiFetch(`/student/timetable${day != null ? `?day=${day}` : ""}`)
// The week endpoint returns slots grouped by day name; flatten to a single
// list ordered Monday→Saturday so pages can render one simple table.
export const getStudentTimetableWeek = async () => {
  const week = await apiFetch("/student/timetable/week")
  const order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
  return order.flatMap((day) => (week?.[day] || []).map((slot) => ({ ...slot, day_name: slot.day_name || day })))
}
export const getProfile              = () => apiFetch("/student/profile")
export const updateProfile           = (body) => apiFetch("/student/profile", { method: "PATCH", body: JSON.stringify(body) })
export const updateInterests         = (interests) =>
  apiFetch("/student/update-interests", { method: "PUT", body: JSON.stringify({ interests }) })
export const getRecommendations      = () => apiFetch("/student/recommendations")

// ─── Admin: external learning resources catalogue ────────
export const adminList   = (resource)            => apiFetch(`/admin/${resource}`)
export const adminCreate = (resource, body)      => apiFetch(`/admin/${resource}`, { method: "POST", body: JSON.stringify(body) })
export const adminUpdate = (resource, id, body)  => apiFetch(`/admin/${resource}/${id}`, { method: "PUT", body: JSON.stringify(body) })
export const adminDelete = (resource, id, query = "") => apiFetch(`/admin/${resource}/${id}${query}`, { method: "DELETE" })

// ─── Own account ─────────────────────────────────────────
export const changePassword = (current_password, new_password) =>
  apiFetch("/me/password", { method: "PUT", body: JSON.stringify({ current_password, new_password }) })

// ─── Self-service lecturer registration and payment policy ───────────────
export const getRegistrationPolicy = () => apiFetch("/public/registration-policy")
export const signupLecturer = (payload) =>
  apiFetch("/lecturer/signup", { method: "POST", body: JSON.stringify(payload) })
export const verifyLecturerPayment = (reference) => apiFetch(`/lecturer/payment/verify/${encodeURIComponent(reference)}`)
export const getLecturerFeePolicy = () => apiFetch("/admin/registration-policy")
export const saveLecturerFeePolicy = (payload) =>
  apiFetch("/admin/registration-policy", { method: "PUT", body: JSON.stringify(payload) })
export const getPendingLecturers = () => apiFetch("/admin/pending-lecturers")
export const approveLecturer = (id) => apiFetch(`/admin/lecturers/${id}/approve`, { method: "POST" })
export const rejectLecturer = (id) => apiFetch(`/admin/lecturers/${id}/reject`, { method: "POST" })
export const enrolByRegistrationCode = (registration_code, batch_id = null) =>
  apiFetch("/academic/enrol-by-code", { method: "POST", body: JSON.stringify({ registration_code, batch_id }) })
export const createMyCourseSchedule = (courseId, payload) =>
  apiFetch(`/faculty/courses/${courseId}/schedule`, { method: "POST", body: JSON.stringify(payload) })
export const updateMyCourseSchedule = (scheduleId, payload) =>
  apiFetch(`/faculty/schedules/${scheduleId}`, { method: "PUT", body: JSON.stringify(payload) })
export const deleteMyCourseSchedule = (scheduleId) =>
  apiFetch(`/faculty/schedules/${scheduleId}`, { method: "DELETE" })
// Private registration selfie endpoint. The caller must send the authenticated
// bearer token; this helper only builds the API URL.
export const registrationSelfieUrl = (userId) =>
  `${BASE_URL}/admin/registration-selfies/${encodeURIComponent(userId)}`

export const fetchRegistrationSelfie = async (userId) => {
  const res = await fetch(`${BASE_URL}/admin/registration-selfies/${userId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error("Registration selfie could not be loaded.")
  return URL.createObjectURL(await res.blob())
}

export const previewCourseByRegistrationCode = (code) => apiFetch(`/academic/course-preview?code=${encodeURIComponent(code)}`)

export const getLecturerPayments = () => apiFetch("/admin/lecturer-payments")

export const getMyProfile = () => apiFetch("/profile")
export const getUserProfile = (id) => apiFetch(`/profiles/${id}`)
export const getAdminUserActivity = (id) => apiFetch(`/admin/profiles/${id}/activity`)
export const updateMyProfile = (payload) => apiFetch("/profile", { method: "PATCH", body: JSON.stringify(payload) })

export const updateAttendancePoints = (id, points) => apiFetch(`/faculty/attendance/records/${id}/points`, { method: "PATCH", body: JSON.stringify({ points }) })
