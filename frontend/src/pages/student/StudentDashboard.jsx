import { useNavigate } from "react-router-dom"
import { useState, useEffect } from "react"
import MainLayout from "../../layouts/MainLayout"
import { useAuth } from "../../context/AuthContext"
import { getAttendancePercentage, getStudentTimetable, getStudentCourses } from "../../services/api"

export default function StudentDashboard() {
  const { user } = useAuth()
  const navigate  = useNavigate()

  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState("")

  const [myCourses, setMyCourses] = useState([])
  const [myCoursesError, setMyCoursesError] = useState("")
  const [classes,       setClasses]       = useState([])
  const [classesError, setClassesError]   = useState("")
  const [now,          setNow]           = useState(new Date())
  const [classFilter, setClassFilter] = useState("upcoming")

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    getStudentTimetable().then(setClasses).catch(e => setClassesError(e.message))
    getStudentCourses().then(setMyCourses).catch(e => setMyCoursesError(e.message))
  }, [])

  const hhmm = now.toTimeString().slice(0, 5)
  const classStatus = (c) =>
    c.is_free ? "free" : hhmm < c.start_time ? "upcoming" : hhmm <= c.end_time ? "now" : "done"
  const STATUS_STYLE = {
    now:      "bg-green-100 text-green-700",
    upcoming: "bg-blue-100 text-blue-700",
    done:     "bg-gray-100 text-gray-500",
    free:     "bg-gray-50 text-gray-400",
  }
  const STATUS_LABEL = { now: "In progress", upcoming: "Upcoming", done: "Done", free: "Free" }

  useEffect(() => {
    if (!user) return
    getAttendancePercentage()
      .then(data => {
        setStats(data)
      })
      .catch(() => setError("Could not load attendance data"))
      .finally(() => setLoading(false))
  }, [user])

  const pctColor =
    !stats           ? "text-gray-800" :
    stats.percentage >= 75 ? "text-green-600" :
    stats.percentage >= 50 ? "text-yellow-500" : "text-red-600"

  return (
    <MainLayout>
      <div className="mt-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">
          Welcome, {user?.name}
        </h2>

        {/* ── KPI Cards ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Attendance % */}
          <div className="bg-white p-6 rounded-2xl shadow-md">
            <h3 className="text-lg font-semibold text-gray-700 mb-2">Attendance</h3>
            {loading ? (
              <p className="text-gray-400 animate-pulse">Loading...</p>
            ) : error ? (
              <p className="text-red-500 text-sm">{error}</p>
            ) : (
              <>
                <p className={`text-4xl font-bold ${pctColor}`}>{stats.percentage}%</p>
                <p className="text-sm text-gray-500 mt-1">
                  {stats.present_classes} present / {stats.total_classes} total classes
                </p>
                {stats.percentage < 75 && stats.total_classes > 0 && (
                  <p className="text-xs text-red-500 mt-2">Below 75% threshold</p>
                )}
              </>
            )}
          </div>

          {/* Mark Attendance */}
          <div className="bg-white rounded-2xl shadow-lg p-6">
            <h3 className="text-lg font-semibold mb-2">Mark Attendance</h3>
            <p className="text-gray-500 text-sm mb-4">
              Scan the faculty QR code to mark your attendance.
            </p>
            <button onClick={() => navigate("/student/attendance")}
              className="w-full py-2 rounded-xl font-medium transition bg-blue-600 text-white hover:bg-blue-700">
              Open QR attendance
            </button>
            <button onClick={() => navigate("/student/courses")}
              className="w-full mt-2 py-2 rounded-xl font-medium border border-blue-200 text-blue-700 hover:bg-blue-50">
              Join a course
            </button>
          </div>

        </div>

        <section className="mt-6 bg-white rounded-2xl shadow-lg p-6">
          <div className="flex items-center justify-between gap-3 mb-4"><div><h3 className="text-lg font-semibold">My registered courses</h3><p className="text-sm text-slate-500">Courses approved for your academic programme and enrolment.</p></div><button className="text-sm text-blue-700 font-semibold" onClick={() => navigate("/student/courses")}>Manage courses</button></div>
          {myCoursesError ? <p className="text-sm text-red-600">{myCoursesError}</p> : myCourses.length ? <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">{myCourses.map(course=><article key={course.course_id} className="border border-slate-200 rounded-xl p-4"><p className="text-xs font-bold text-blue-700">{course.code}</p><h4 className="font-semibold mt-1">{course.title}</h4><p className="text-xs text-slate-500 mt-2">{course.lecturer_name||"Lecturer"} · {course.credit_hours||"—"} credits</p><p className="text-xs text-slate-500">{course.batch_name||"No batch assigned"}</p></article>)}</div> : <p className="text-sm text-slate-500">You have no approved course enrolments yet. Register for a course to see it here.</p>}
        </section>

        {/* ── Today's classes ───────────────────────────────────────────── */}
        <div className="mt-6 bg-white rounded-2xl shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Your scheduled classes</h3>
          <div className="flex flex-wrap gap-2 mb-4">{[["upcoming","Upcoming"],["now","Live now"],["done","Completed"],["all","All classes"]].map(([value,label])=><button key={value} type="button" onClick={()=>setClassFilter(value)} className={`px-3 py-2 rounded-lg text-xs font-semibold border ${classFilter===value?"bg-blue-700 text-white border-blue-700":"bg-white text-slate-600 border-slate-200"}`}>{label}</button>)}</div>
          {classesError ? (
            <div className="text-red-500 text-sm">{classesError} <button className="underline ml-2" onClick={()=>getStudentTimetable().then(setClasses).catch(e=>setClassesError(e.message))}>Try again</button></div>
          ) : classes.length === 0 ? (
            <p className="text-gray-500 text-sm">No classes are scheduled for today.</p>
          ) : classes.filter(c=>classFilter==="all" || classStatus(c)===classFilter).length === 0 ? (
            <p className="text-gray-500 text-sm">No {classFilter === "now" ? "live" : classFilter} classes today.</p>
          ) : (
            <ul className="divide-y">
              {classes.filter(c=>classFilter==="all" || classStatus(c)===classFilter).map((c, i) => {
                const st = classStatus(c)
                return (
                  <li key={`${c.period}-${i}`} className={`flex items-center gap-4 py-3 ${c.is_free ? "opacity-60" : ""}`}>
                    <span className="w-10 font-semibold text-gray-700">{c.period}</span>
                    <span className="w-28 text-sm text-gray-500">{c.start_time}-{c.end_time}</span>
                    <span className="flex-1">
                      <span className="font-medium text-gray-800">{c.subject}</span>
                      {!c.is_free && (
                        <span className="block text-xs text-gray-500">
                          {[c.faculty_name, c.room_no && `Room ${c.room_no}`, c.class_type].filter(Boolean).join(" · ")}
                        </span>
                      )}
                    </span>
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_STYLE[st]}`}>{STATUS_LABEL[st]}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </MainLayout>
  )
}