import { useEffect, useState } from "react"
import { apiFetch } from "../services/api"
import MainLayout from "../layouts/MainLayout"
import { useAuth } from "../context/AuthContext"
import { changePassword, getMyProfile, updateMyProfile } from "../services/api"

export default function Settings() {
  const { user, updateUser } = useAuth()
  const [form, setForm] = useState({ current: "", next: "", confirm: "" })
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [policy,setPolicy] = useState({auto_approve_students:false,default_enrolment_approval:true,attendance_session_minutes:10,attendance_gps_radius_meters:50})
  const [policyMsg,setPolicyMsg] = useState("")
  const [profile,setProfile] = useState({name:"",email:"",phone:"",index_number:"",staff_id:"",institution_name:"",faculty_name:"",department:"",programme:"",academic_year:"",designation:"",level:null,ghana_card_last4:""})
  const [profileMsg,setProfileMsg] = useState("")
  const [profileBusy,setProfileBusy] = useState(false)
  useEffect(()=>{ getMyProfile().then(setProfile).catch(e=>setProfileMsg(e.message)); if(user?.role === "admin") apiFetch("/admin/settings").then(setPolicy).catch(e=>setPolicyMsg(e.message)) },[user?.role])
  const savePolicy=async()=>{try{await apiFetch("/admin/settings",{method:"PUT",body:JSON.stringify(policy)});setPolicyMsg("Platform settings saved successfully.")}catch(e){setPolicyMsg(e.message)}}
  const saveProfile=async e=>{e.preventDefault();setProfileBusy(true);setProfileMsg("");try{await updateMyProfile({name:profile.name,email:profile.email,phone:profile.phone,institution_name:profile.institution_name,faculty_name:profile.faculty_name,department:profile.department,programme_name:profile.programme,academic_year:profile.academic_year,designation:profile.designation});updateUser({name:profile.name,email:profile.email});setProfileMsg("Profile updated successfully.")}catch(e){setProfileMsg(e.message)}finally{setProfileBusy(false)}}

  const submit = async (e) => {
    e.preventDefault()
    setMsg(null)
    if (form.next.length < 6) return setMsg({ ok: false, text: "New password must be at least 6 characters." })
    if (form.next !== form.confirm) return setMsg({ ok: false, text: "New passwords do not match." })
    setBusy(true)
    try {
      await changePassword(form.current, form.next)
      setForm({ current: "", next: "", confirm: "" })
      setMsg({ ok: true, text: "Password changed successfully." })
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    } finally {
      setBusy(false)
    }
  }

  const input = "w-full border rounded-lg bg-white px-3 py-2"
  return (
    <MainLayout>
      <section className="max-w-md space-y-6">
        <div>
          <p className="text-sm text-slate-500">Account</p>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-sm text-slate-500 mt-1">{user?.name} · {user?.role}</p>
        </div>
        <form onSubmit={saveProfile} className="space-y-4 rounded-2xl bg-white p-6 shadow">
          <h2 className="font-semibold">Personal profile</h2>
          <label className="block text-sm">Full name<input className={`${input} mt-1`} value={profile.name||""} onChange={e=>setProfile({...profile,name:e.target.value})} required minLength={2}/></label>
          <label className="block text-sm">Email address<input className={`${input} mt-1`} type="email" value={profile.email||""} onChange={e=>setProfile({...profile,email:e.target.value})} required/></label>
          <label className="block text-sm">Institution<input className={`${input} mt-1`} value={profile.institution_name||""} onChange={e=>setProfile({...profile,institution_name:e.target.value})}/></label>
          <label className="block text-sm">Faculty / School<input className={`${input} mt-1`} value={profile.faculty_name||""} onChange={e=>setProfile({...profile,faculty_name:e.target.value})}/></label>
          <label className="block text-sm">Department<input className={`${input} mt-1`} value={profile.department||""} onChange={e=>setProfile({...profile,department:e.target.value})}/></label>
          <label className="block text-sm">Programme / Subject area<input className={`${input} mt-1`} value={profile.programme||""} onChange={e=>setProfile({...profile,programme:e.target.value})}/></label>
          <label className="block text-sm">Academic year<input className={`${input} mt-1`} value={profile.academic_year||""} onChange={e=>setProfile({...profile,academic_year:e.target.value})}/></label>
          {user?.role==="student"&&<div className="grid grid-cols-2 gap-3 text-sm"><div><span className="text-slate-500">Index number</span><b className="block">{profile.index_number||"—"}</b></div><div><span className="text-slate-500">Level</span><b className="block">{profile.level?`Level ${profile.level}`:"—"}</b></div></div>}
          {user?.role==="faculty"&&<><label className="block text-sm">Designation / Rank<input className={`${input} mt-1`} value={profile.designation||""} onChange={e=>setProfile({...profile,designation:e.target.value})}/></label><div className="text-sm"><span className="text-slate-500">Staff ID</span><b className="block">{profile.staff_id||"—"}</b></div></>}
          {profile.ghana_card_last4&&<p className="text-xs text-slate-500">Ghana Card on file: •••• {profile.ghana_card_last4} · Identity fields require administrator correction.</p>}
          {profileMsg&&<p className="text-sm text-slate-600">{profileMsg}</p>}
          <button disabled={profileBusy} className="rounded-lg bg-blue-600 px-5 py-2 text-white disabled:opacity-60">{profileBusy?"Saving…":"Save profile"}</button>
        </form>
        <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow">
          <h2 className="font-semibold">Change password</h2>
          {msg && <div className={`rounded-lg p-3 text-sm ${msg.ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{msg.text}</div>}
          <input type="password" className={input} placeholder="Current password" value={form.current}
            onChange={(e) => setForm({ ...form, current: e.target.value })} required />
          <input type="password" className={input} placeholder="New password (min 6 characters)" value={form.next}
            onChange={(e) => setForm({ ...form, next: e.target.value })} required />
          <input type="password" className={input} placeholder="Confirm new password" value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })} required />
          <button disabled={busy} className="rounded-lg bg-blue-600 px-5 py-2 text-white hover:bg-blue-700 disabled:opacity-60">
            {busy ? "Saving..." : "Update password"}
          </button>
        </form>
        {user?.role === "admin" && <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow space-y-4"><div><h2 className="font-semibold">Platform policies</h2><p className="text-sm text-slate-500">These platform-wide defaults apply unless a lecturer sets a different attendance-session radius or duration.</p></div><label className="flex items-center justify-between gap-4"><span><strong className="block text-sm">Automatic student approval</strong><small className="text-slate-500">Activate students immediately after registration.</small></span><input type="checkbox" checked={policy.auto_approve_students} onChange={e=>setPolicy({...policy,auto_approve_students:e.target.checked})}/></label><label className="flex items-center justify-between gap-4"><span><strong className="block text-sm">Require lecturer approval for course enrolment</strong><small className="text-slate-500">Default policy for newly created courses.</small></span><input type="checkbox" checked={policy.default_enrolment_approval} onChange={e=>setPolicy({...policy,default_enrolment_approval:e.target.checked})}/></label><label className="block text-sm">Default attendance session duration (minutes)<input type="number" min="1" max="180" className={`${input} mt-2`} value={policy.attendance_session_minutes} onChange={e=>setPolicy({...policy,attendance_session_minutes:Number(e.target.value)})}/></label><label className="block text-sm">Classroom attendance radius (metres)<input type="number" min="10" max="500" className={`${input} mt-2`} value={policy.attendance_gps_radius_meters ?? 50} onChange={e=>setPolicy({...policy,attendance_gps_radius_meters:Number(e.target.value)})}/><small className="text-slate-500">Default: 50 metres. GPS accuracy and device capability still affect verification.</small></label>{policyMsg&&<p className="text-sm text-slate-600">{policyMsg}</p>}<button onClick={savePolicy} className="rounded-lg bg-blue-600 px-5 py-2 text-white">Save platform settings</button></section>}
      </section>
    </MainLayout>
  )
}
