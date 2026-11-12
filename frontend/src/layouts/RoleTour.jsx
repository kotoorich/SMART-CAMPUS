import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, GraduationCap, HelpCircle, X } from "lucide-react";

const TOURS = {
  student: [
    ["Your student profile", "Complete your institution, faculty, department, programme and academic details. Keep your contact details current."],
    ["Join a lecturer's course", "Enter the course registration code shared by your lecturer. Preview the course and request enrolment."],
    ["Know your class schedule", "View the timetable for courses you have joined. The timetable helps with planning; it does not restrict attendance."],
    ["Mark attendance", "When your lecturer opens a session, scan the QR code or enter the short code, enable GPS and capture a fresh selfie."],
    ["Track your record", "Review attendance history and contact your lecturer if a record needs attention."]
  ],
  faculty: [
    ["Set up your lecturer profile", "Add your institution, faculty, department, programme or subject area, staff ID and designation."],
    ["Create your courses", "Create a course, define its eligible programme and share the generated registration code with students."],
    ["Manage enrolment", "Review requests and approve or reject students who want to join your own courses. Open their profiles from your roster."],
    ["Set a timetable", "Add recurring class days, times and venues so students know where classes are held."],
    ["Open attendance whenever needed", "Choose any of your courses, set the GPS radius and session duration, then share the QR or short code. Timetable time never blocks attendance."],
    ["Review selfie evidence", "See present and absent students, open each submitted attendance selfie, check GPS evidence and export the register."]
  ],
  admin: [
    ["Review registrations", "Review student and lecturer details and registration selfies before approving or rejecting accounts."],
    ["Manage platform users", "Search, view, edit, approve, suspend or remove student and lecturer accounts across all institutions."],
    ["Oversee attendance", "Monitor courses, attendance sessions, reports and private evidence with authorised access."],
    ["Configure platform policies", "Set lecturer registration fees, default attendance duration, GPS defaults and security controls."],
    ["Use audit history", "Review important account, payment and attendance actions for accountability."]
  ]
};

export default function RoleTour({ role }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const steps = useMemo(() => TOURS[role] || [], [role]);
  useEffect(() => {
    if (!steps.length) return;
    const key = `smart-campus-tour-seen-${role}`;
    if (!window.localStorage.getItem(key)) setOpen(true);
  }, [role, steps.length]);
  const finish = () => {
    window.localStorage.setItem(`smart-campus-tour-seen-${role}`, "1");
    setOpen(false); setStep(0);
  };
  if (!steps.length) return null;
  return <>
    <button type="button" onClick={() => { setStep(0); setOpen(true); }} className="fixed bottom-5 right-5 z-30 inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow-xl hover:bg-blue-700"><HelpCircle size={17}/> Guided tour</button>
    {open && <div className="fixed inset-0 z-[60] grid place-items-center bg-slate-950/60 p-4" role="dialog" aria-modal="true" aria-label={`${role} guided tour`}>
      <section className="w-full max-w-lg overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div className="flex items-center gap-2 text-sm font-bold text-slate-800"><span className="grid h-9 w-9 place-items-center rounded-xl bg-blue-50 text-blue-700"><GraduationCap size={20}/></span>Smart Campus · {role === "faculty" ? "Lecturer" : role === "admin" ? "Administrator" : "Student"} guide</div><button onClick={finish} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close tour"><X size={18}/></button></div>
        <div className="px-6 py-7"><div className="mb-5 flex gap-1.5">{steps.map((_, i) => <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-blue-600" : "bg-slate-200"}`}/>)}</div><p className="text-xs font-bold uppercase tracking-[.18em] text-blue-700">Step {step + 1} of {steps.length}</p><h2 className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{steps[step][0]}</h2><p className="mt-3 leading-7 text-slate-600">{steps[step][1]}</p></div>
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-5 py-4"><button onClick={finish} className="text-sm font-medium text-slate-500 hover:text-slate-900">Skip tour</button><div className="flex gap-2"><button onClick={() => setStep(v => Math.max(0, v - 1))} disabled={step === 0} className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40"><ArrowLeft size={15}/> Previous</button><button onClick={() => step === steps.length - 1 ? finish() : setStep(v => v + 1)} className="inline-flex items-center gap-1 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">{step === steps.length - 1 ? "Finish" : "Next"} <ArrowRight size={15}/></button></div></div>
      </section>
    </div>}
  </>;
}
