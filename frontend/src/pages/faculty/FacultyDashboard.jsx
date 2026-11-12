import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, MapPin, QrCode, RefreshCw, ShieldCheck, Users, XCircle } from "lucide-react";
import { QRCodeCanvas } from "qrcode.react";
import MainLayout from "../../layouts/MainLayout";
import { getAttendanceCourses, openAttendanceSession, closeAttendanceSession } from "../../services/api";
import { getBestPosition } from "../../utils/geo";

const getPosition = () => getBestPosition();

export default function FacultyDashboard() {
  const [courses,setCourses]=useState([]); const [selected,setSelected]=useState("");
  const [scheduleId,setScheduleId]=useState(""); const [session,setSession]=useState(null);
  const [radius,setRadius]=useState("50"); const [duration,setDuration]=useState("10");
  const [loading,setLoading]=useState(true); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const load=useCallback(async()=>{setLoading(true);setError("");try{const rows=await getAttendanceCourses();setCourses(rows||[]);const first=(rows||[])[0];if(first){setSelected(String(first.course_id));setScheduleId(String(first.schedules?.[0]?.id||""));}}catch(e){setError(e.message||"Could not load your scheduled classes.");}finally{setLoading(false);}},[]);
  useEffect(()=>{load();},[load]);
  const course=useMemo(()=>courses.find(c=>String(c.course_id)===selected),[courses,selected]);
  const slots=course?.schedules||[]; const slot=slots.find(s=>String(s.id)===scheduleId)||null;
  const open=async()=>{if(!course)return;setBusy(true);setError("");try{const gps=await getPosition();const data=await openAttendanceSession({course_id:course.course_id,batch_id:slot?.batch_id||null,schedule_id:slot?.id||null,period:slot?.period||null,radius_meters:Number(radius),session_minutes:Number(duration),...gps});setSession(data);}catch(e){setError(e.message||"Attendance session could not be opened.");}finally{setBusy(false);}};
  const close=async()=>{if(!session)return;setBusy(true);try{await closeAttendanceSession(session.id);setSession(null);await load();}catch(e){setError(e.message);}finally{setBusy(false);}};
  const qrPayload=session?.qr_payload||{session_id:session?.id,token:session?.token};
  return <MainLayout><main className="sc-page">
    <header className="sc-page-head"><div><p className="sc-eyebrow">LECTURER WORKSPACE</p><h1><QrCode size={25}/> Start attendance</h1><p className="sc-muted">Open attendance for any of your courses, whenever you need. The timetable is informational; the live session controls attendance.</p></div><button className="sc-button sc-button-secondary" onClick={load} disabled={loading}><RefreshCw size={16}/> Refresh</button></header>
    {error&&<div className="sc-notice error" role="alert">{error}</div>}
    {!session?<section className="sc-panel p-5 space-y-4"><div className="flex items-center gap-3"><span className="p-3 rounded-xl bg-blue-50 text-blue-700"><CalendarClock size={22}/></span><div><h2 className="font-semibold">Choose a course</h2><p className="text-sm text-slate-500">You can open attendance at any time. Class schedule does not restrict attendance.</p></div></div>
      {loading?<p className="text-sm text-slate-500">Loading your courses…</p>:courses.length===0?<div className="sc-empty"><CalendarClock size={28}/><strong>No courses yet</strong><p>Create a course first, then return here to start attendance.</p></div>:<>
        <label className="block text-sm font-medium">Course<select className="block w-full mt-1 border rounded-xl p-3" value={selected} onChange={e=>{setSelected(e.target.value);const c=courses.find(x=>String(x.course_id)===e.target.value);setScheduleId(String(c?.schedules?.[0]?.id||""));}}>{courses.map(c=><option key={c.course_id} value={c.course_id}>{c.code} · {c.title}</option>)}</select></label>
        <label className="block text-sm font-medium">Optional timetable entry<select className="block w-full mt-1 border rounded-xl p-3" value={scheduleId} onChange={e=>setScheduleId(e.target.value)}><option value="">No specific timetable entry</option>{slots.map(s=><option key={s.id} value={s.id}>{["Mon","Tue","Wed","Thu","Fri","Sat"][s.day_of_week]||"Class"} · {s.start_time}–{s.end_time} · {s.room_no} · {s.period}</option>)}</select></label>
        {slot&&<div className="rounded-xl bg-slate-50 p-3 text-sm"><b>Timetable reference:</b> {slot.start_time}–{slot.end_time} · {slot.room_no||"Room not set"}. This does not restrict attendance.</div>}
        <div className="grid grid-cols-2 gap-3"><label className="block text-sm font-medium">Allowed GPS radius<select className="block w-full mt-1 border rounded-xl p-3" value={radius} onChange={e=>setRadius(e.target.value)}>{[10,25,50,75,100,150,200,300,500].map(v=><option key={v} value={v}>{v} metres</option>)}</select></label><label className="block text-sm font-medium">Session duration<select className="block w-full mt-1 border rounded-xl p-3" value={duration} onChange={e=>setDuration(e.target.value)}>{[5,10,15,20,30,45,60,90,120,240].map(v=><option key={v} value={v}>{v} minutes</option>)}</select></label></div>
        <div className="rounded-xl bg-blue-50 border border-blue-100 p-3 text-sm text-blue-800"><ShieldCheck size={17} className="inline mr-2"/>Your live GPS location becomes the attendance reference point. Only the session's own expiry and radius govern attendance.</div>
        <button className="sc-button sc-button-primary w-full" onClick={open} disabled={busy||!course}>{busy?"Verifying location…":"Open attendance session"}</button>
      </>}</section>:<section className="sc-panel p-5 space-y-4 max-w-xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 text-emerald-700 font-semibold"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"/> Attendance session is live</div>
        <div><h2 className="text-xl font-bold">{session.course_code} · {session.course_title}</h2><p className="text-sm text-slate-500">{session.batch_name||"All approved students"} · {session.date} · {session.period}</p></div>
        <div className="bg-white border rounded-2xl p-5 inline-flex justify-center"><QRCodeCanvas value={JSON.stringify(qrPayload)} size={240} level="H" includeMargin/></div>
        <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Manual attendance code</p><div className="flex items-center justify-center gap-3"><p className="text-2xl font-bold tracking-[0.25em]">{session.access_code}</p><button type="button" className="text-sm text-blue-700 underline" onClick={()=>navigator.clipboard?.writeText(session.access_code)}>Copy</button></div><p className="text-xs text-slate-500 mt-1">Expires {session.expires_at?new Date(session.expires_at).toLocaleTimeString():"automatically"}</p></div>
        <div className="grid grid-cols-2 gap-3 text-left"><div className="rounded-xl bg-slate-50 p-3"><Users size={18}/><small className="block text-slate-500">Marked present</small><b className="text-xl">{session.present_count||0}</b></div><div className="rounded-xl bg-slate-50 p-3"><MapPin size={18}/><small className="block text-slate-500">Allowed radius</small><b className="text-xl">{session.radius_meters||50} m</b></div></div>
        <p className="text-sm text-slate-500">Students must already be enrolled in this course. Do not share this QR outside the classroom.</p>
        <button className="sc-button sc-button-secondary w-full" onClick={close} disabled={busy}><XCircle size={17}/>{busy?"Closing…":"Close attendance session"}</button>
      </section>}
  </main></MainLayout>;
}
