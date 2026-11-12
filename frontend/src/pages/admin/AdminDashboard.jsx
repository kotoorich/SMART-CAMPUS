import { useEffect, useState } from "react"
import MainLayout from "../../layouts/MainLayout"
import { getPendingStudents, approveStudent, rejectStudent, getAdminStats, registrationSelfieUrl } from "../../services/api"
import { getToken } from "../../utils/session"

export default function AdminDashboard() {
  const [pending, setPending] = useState([])
  const [stats, setStats] = useState({ total_students: 0, total_faculty: 0, pending_students: 0 })
  const [error, setError] = useState("")

  const fetchAll = async () => {
    try {
      //  FIX: Both calls now send Authorization header from api.js
      const [pendingData, statsData] = await Promise.all([
        getPendingStudents(),
        getAdminStats(),
      ])
      setPending(pendingData)
      setStats(statsData)
    } catch (err) {
      setError(err.message || "Failed to load data")
    }
  }

  useEffect(() => {
    // Deferred so the request resolves after mount instead of during the
    // synchronous effect body.
    const timer = setTimeout(fetchAll, 0)
    return () => clearTimeout(timer)
  }, [])

  const viewSelfie = async (id) => {
    try { const response = await fetch(registrationSelfieUrl(id), { headers: { Authorization: `Bearer ${getToken() || ""}` } }); if (!response.ok) throw new Error("Registration selfie could not be opened."); const blob = await response.blob(); const url = URL.createObjectURL(blob); window.open(url, "_blank", "noopener"); } catch (e) { setError(e.message); }
  }

  const handleApprove = async (id) => {
    try {
      await approveStudent(id)
      fetchAll()
    } catch (err) {
      setError(err.message || "Approval failed")
    }
  }

  const handleReject = async (id) => {
    if (!window.confirm("Reject and delete this registration? This cannot be undone.")) return
    try {
      await rejectStudent(id)
      fetchAll()
    } catch (err) {
      setError(err.message || "Reject failed")
    }
  }

  return (
    <MainLayout>

      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-8 mt-6">

        <div className="bg-white rounded-2xl shadow-lg p-6">
          <p className="text-gray-500 text-sm">Total Students</p>
          <h2 className="text-3xl font-bold text-blue-700">{stats.total_students}</h2>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-6">
          <p className="text-gray-500 text-sm">Total Lecturers</p>
          <h2 className="text-3xl font-bold text-indigo-700">{stats.total_faculty}</h2>
        </div>

        <div className="bg-white rounded-2xl shadow-lg p-6">
          <p className="text-gray-500 text-sm">Pending Approvals</p>
          <h2 className="text-3xl font-bold text-red-600">{stats.pending_students}</h2>
        </div>

      </div>

      {/* Pending Approvals Table */}
      <div>
        <h2 className="text-2xl font-bold text-gray-700 mb-4">
          Pending Student Approvals
        </h2>

        {pending.length === 0 ? (
          <p className="text-gray-500">No pending students.</p>
        ) : (
          <div className="bg-white rounded-2xl shadow-md p-3 sm:p-6 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b text-gray-500 text-sm">
                  <th className="py-2 pr-6">Name</th>
                  <th className="pr-6">Email</th>
                  <th className="pr-6">Programme</th>
                  <th className="pr-6">Level</th>
                  <th className="pr-6">Identity</th><th>Action</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((student) => (
                  <tr key={student.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 pr-6 font-medium">{student.name}</td>
                    <td className="pr-6 text-gray-600">{student.email}</td>
                    <td className="pr-6 text-gray-600">{student.programme_name || student.department || "—"}</td>
                    <td className="pr-6 text-gray-600">{student.level ? `Level ${student.level}` : "—"}</td>
                    <td className="pr-6 text-gray-600"><button onClick={() => viewSelfie(student.id)} className="text-blue-700 underline">View selfie</button><small className="block">•••• {student.ghana_card_last4 || "—"}</small></td>
                    <td>
                      <button
                        onClick={() => handleApprove(student.id)}
                        className="bg-green-600 text-white px-4 py-1 rounded-lg hover:bg-green-700 transition text-sm font-medium"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(student.id)}
                        className="ml-2 bg-red-600 text-white px-4 py-1 rounded-lg hover:bg-red-700 transition text-sm font-medium"
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </MainLayout>
  )
}