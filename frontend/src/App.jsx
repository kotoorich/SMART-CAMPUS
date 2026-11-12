import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider, useAuth } from "./context/AuthContext"

import Landing            from "./pages/Landing"
import Login              from "./pages/auth/Login"
import StudentSignup      from "./pages/student/StudentSignupManaged"
import FacultySignup from "./pages/faculty/FacultySignupManaged"
import LecturerPaymentCallback from "./pages/faculty/LecturerPaymentCallback"
import AdminDashboard     from "./pages/admin/AdminDashboard"
import FacultyDashboard   from "./pages/faculty/FacultyDashboard"
import FacultyAttendance  from "./pages/faculty/FacultyAttendance"
import StudentDashboard   from "./pages/student/StudentDashboard"
import StudentAttendance  from "./pages/student/StudentAttendance"
import StudentAnnouncements from "./pages/student/StudentAnnouncements"
import AdminResources from "./pages/admin/AdminResources"
import Settings from "./pages/Settings"
import AcademicHub from "./pages/AcademicHub"
import AcademicStructure from "./pages/admin/AcademicStructure"
import AdminAcademicOversight from "./pages/AdminAcademicOversight"
import RegistrationSettings from "./pages/admin/RegistrationSettings"
import Announcements from "./pages/Announcements"
import AuditLog from "./pages/AuditLog"
import UserProfile from "./pages/UserProfile"

function ProtectedRoute({ children, role }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (role && user.role !== role) return <Navigate to={`/${user.role}/dashboard`} replace />
  return children
}

function AppRoutes() {
  const { user } = useAuth()
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={user ? <Navigate to={`/${user.role}/dashboard`} replace /> : <Login />} />
      <Route path="/signup" element={<StudentSignup />} />
      <Route path="/lecturer/signup" element={<FacultySignup />} />
      <Route path="/lecturer/payment/callback" element={<LecturerPaymentCallback />} />

      {/* Admin */}
      <Route path="/admin/dashboard" element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>} />
      <Route path="/admin/students" element={<ProtectedRoute role="admin"><AdminResources type="students" /></ProtectedRoute>} />
      <Route path="/admin/faculty" element={<ProtectedRoute role="admin"><AdminResources type="faculty" /></ProtectedRoute>} />
      <Route path="/admin/courses" element={<Navigate to="/admin/academic" replace />} />
      <Route path="/admin/structure" element={<ProtectedRoute role="admin"><AcademicStructure mode="admin" /></ProtectedRoute>} />
      <Route path="/admin/registration-settings" element={<ProtectedRoute role="admin"><RegistrationSettings /></ProtectedRoute>} />
      <Route path="/admin/announcements" element={<ProtectedRoute role="admin"><Announcements /></ProtectedRoute>} />
      <Route path="/admin/audit-log" element={<ProtectedRoute role="admin"><AuditLog /></ProtectedRoute>} />
      <Route path="/admin/grading-bands" element={<ProtectedRoute role="admin"><AdminResources type="grading" /></ProtectedRoute>} />
      <Route path="/admin/resources" element={<ProtectedRoute role="admin"><AdminResources type="courses" /></ProtectedRoute>} />
      <Route path="/admin/academic" element={<ProtectedRoute role="admin"><AdminAcademicOversight /></ProtectedRoute>} />
      <Route path="/admin/timetable" element={<Navigate to="/admin/academic" replace />} />
      <Route path="/admin/attendance-reports" element={<Navigate to="/admin/academic" replace />} />
      <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
      <Route path="/profiles/:id" element={<ProtectedRoute><UserProfile /></ProtectedRoute>} />

      {/* Faculty */}
      <Route path="/faculty/dashboard"  element={<ProtectedRoute role="faculty"><FacultyDashboard /></ProtectedRoute>} />
      <Route path="/faculty/attendance" element={<ProtectedRoute role="faculty"><FacultyAttendance /></ProtectedRoute>} />
      <Route path="/faculty/academic" element={<ProtectedRoute role="faculty"><AcademicHub mode="lecturer" /></ProtectedRoute>} />
      <Route path="/faculty/programmes" element={<ProtectedRoute role="faculty"><AcademicStructure mode="lecturer" /></ProtectedRoute>} />
      <Route path="/faculty/announcements" element={<ProtectedRoute role="faculty"><Announcements /></ProtectedRoute>} />
      <Route path="/faculty/curriculum" element={<Navigate to="/faculty/dashboard" replace />} />

      {/* Student */}
      <Route path="/student/dashboard"       element={<ProtectedRoute role="student"><StudentDashboard /></ProtectedRoute>} />
      <Route path="/student/attendance"      element={<ProtectedRoute role="student"><StudentAttendance /></ProtectedRoute>} />
      <Route path="/student/courses" element={<ProtectedRoute role="student"><AcademicHub mode="student" /></ProtectedRoute>} />
      <Route path="/student/announcements" element={<ProtectedRoute role="student"><StudentAnnouncements /></ProtectedRoute>} />
      <Route path="/student/curriculum"      element={<Navigate to="/student/dashboard" replace />} />
      <Route path="/student/skills" element={<Navigate to="/student/dashboard" replace />} />
      <Route path="/student/recommendations" element={<Navigate to="/student/dashboard" replace />} />
      <Route path="/student/nep" element={<Navigate to="/student/dashboard" replace />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  )
}