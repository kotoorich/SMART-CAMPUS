import { useEffect, useRef, useState } from "react";
import Webcam from "react-webcam";
import { ArrowLeft, ArrowRight, Camera, CheckCircle2, GraduationCap, ShieldCheck, UserPlus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getRegistrationPolicy, signupLecturer } from "../../services/api";

const videoConstraints = { width: 640, height: 480, facingMode: "user" };
export default function FacultySignup() {
  const navigate = useNavigate(); const webcam = useRef(null);
  const [policy, setPolicy] = useState(null);
  const [selfie, setSelfie] = useState(""); const [cameraReady, setCameraReady] = useState(false);
  const [consent, setConsent] = useState(false); const [error, setError] = useState("");
  const [loading, setLoading] = useState(false); const [done, setDone] = useState(null);
  const [form, setForm] = useState({ name: "", staff_id: "", email: "", phone: "", ghana_card_number: "", password: "", institution_name: "", faculty_name: "", department_name: "", programme_name: "", designation: "" });
  useEffect(() => {
    getRegistrationPolicy().then(setPolicy)
      .catch(e => setError(e.message || "Registration settings could not be loaded."));
  }, []);
  const change = e => setForm(v => ({ ...v, [e.target.name]: e.target.value }));
  const capture = () => { const shot = webcam.current?.getScreenshot(); if (!shot) return setError("Camera is not ready."); setSelfie(shot); setError(""); };
  const upload = e => { const file=e.target.files?.[0]; if(!file)return; if(file.size>3*1024*1024)return setError("Selfie must be smaller than 3 MB."); const r=new FileReader(); r.onload=()=>setSelfie(String(r.result||"")); r.readAsDataURL(file); };
  const submit = async e => {
    e.preventDefault(); setError(""); if(!selfie)return setError("Capture your registration selfie first."); if(!consent)return setError("Consent is required to process your registration selfie.");
    setLoading(true);
    try {
      const result = await signupLecturer({ ...form,
        staff_id: form.staff_id.trim().toUpperCase(), ghana_card_number: form.ghana_card_number.trim().toUpperCase(),
        registration_selfie: selfie, biometric_method: "selfie", consent_biometrics: consent });
      if (result.authorization_url) { window.location.assign(result.authorization_url); return; }
      setDone(result);
    } catch (err) { setError(err.message || "Lecturer registration failed."); }
    finally { setLoading(false); }
  };
  return <main className="auth-screen signup-auth-screen"><div className="auth-ambient auth-ambient-one"/><div className="auth-ambient auth-ambient-two"/>
    <header className="auth-topbar"><button className="brand-lockup" onClick={()=>navigate("/")}><span className="brand-mark"><GraduationCap size={22}/></span><span><strong>smartcampus</strong><small>ATTENDANCE MANAGEMENT</small></span></button><button className="signup-back" onClick={()=>navigate("/login?role=faculty")}><ArrowLeft size={15}/> Back to sign in</button></header>
    <section className="auth-layout signup-auth-layout"><div className="auth-story"><div className="story-kicker"><UserPlus size={14}/> LECTURER ONBOARDING</div><h1>Teach smarter.<br/><em>Track attendance.</em></h1><p className="story-copy">Register your staff identity to create courses, manage class lists and run verified attendance sessions.</p><div className="signup-benefit"><ShieldCheck size={18}/><span><b>Staff verification</b><small>New lecturer accounts are reviewed by a Smart Campus administrator.</small></span></div></div>
      <div className="auth-card-wrap"><form className="auth-card signup-form-card" onSubmit={submit}>{done ? <div className="signup-success"><span><CheckCircle2 size={28}/></span><h2>Application submitted.</h2><p>{done.message} You can sign in after administrator approval.</p><button type="button" className="auth-submit" onClick={()=>navigate("/login?role=faculty")}>Return to sign in <ArrowRight size={17}/></button></div> : <><div className="auth-card-heading"><span className="auth-eyebrow">LECTURER REGISTRATION</span><h2>Create lecturer account<span>.</span></h2><p>Provide your official staff and identity details.</p></div>
        <div className="signup-fields"><label>Full name<input name="name" value={form.name} onChange={change} required autoComplete="name"/></label><label>Staff ID<input name="staff_id" value={form.staff_id} onChange={change} required/></label><label>Email address<input name="email" type="email" value={form.email} onChange={change} required autoComplete="email"/></label><label>Phone number<input name="phone" type="tel" value={form.phone} onChange={change} required autoComplete="tel"/></label><label className="signup-wide">Ghana Card number<input name="ghana_card_number" value={form.ghana_card_number} onChange={change} placeholder="GHA-XXXXXXXXX-X" required/></label><label>Password<input name="password" type="password" value={form.password} onChange={change} minLength={8} required autoComplete="new-password"/></label><label>Institution name<input name="institution_name" value={form.institution_name} onChange={change} placeholder="Your university or college" required/></label><label>Faculty / School<input name="faculty_name" value={form.faculty_name} onChange={change} placeholder="Faculty or school" required/></label><label>Department<input name="department_name" value={form.department_name} onChange={change} placeholder="Your department" required/></label><label>Programme / Subject area<input name="programme_name" value={form.programme_name} onChange={change} placeholder="Programme or teaching area" required/></label><label>Designation / Rank<input name="designation" value={form.designation} onChange={change} placeholder="e.g. Lecturer, Senior Lecturer"/></label></div>
        <div className="signup-selfie-block"><div className="auth-label"><Camera size={15}/> Registration selfie</div>{selfie ? <div className="signup-selfie-preview"><img src={selfie} alt="Registration selfie"/><button type="button" onClick={()=>setSelfie("")}>Retake selfie</button></div> : <><div className="signup-webcam"><Webcam ref={webcam} audio={false} screenshotFormat="image/jpeg" screenshotQuality={0.78} videoConstraints={videoConstraints} onUserMedia={()=>setCameraReady(true)} onUserMediaError={()=>setError("Camera unavailable. Use the image fallback below.")}/></div><button type="button" className="auth-submit" disabled={!cameraReady} onClick={capture}><Camera size={16}/> Capture selfie</button><label className="signup-upload-fallback">Camera unavailable? Select selfie<input type="file" accept="image/jpeg,image/png,image/webp" capture="user" onChange={upload}/></label></>}
          <label className="signup-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> I consent to secure collection and processing of my registration selfie.</label><small className="signup-privacy-note">The image is stored privately for identity review. Automated face matching requires an institution-approved verification provider.</small></div>
        {policy && <div className="signup-payment-note">{policy.lecturer_registration_free ? "Lecturer registration is currently free." : `Lecturer registration fee: GHS ${Number(policy.lecturer_registration_fee_ghs).toFixed(2)}.`}{!policy.lecturer_registration_free && !policy.payment_provider && " Online payment is not configured; contact the administrator."}</div>}
        {error&&<div className="auth-error" role="alert">{error}</div>}<button className="auth-submit" type="submit" disabled={loading || !policy || (!policy.lecturer_registration_free && !policy.payment_provider)}>{loading?<><span className="button-spinner"/> Submitting…</>:<>Submit lecturer registration <ArrowRight size={17}/></>}</button><p className="auth-register">Already registered? <button type="button" onClick={()=>navigate("/login?role=faculty")}>Sign in</button></p><div className="auth-card-footer"><ShieldCheck size={14}/> Staff identity is reviewed securely</div></>}</form></div></section>
    <footer className="auth-footer"><span>© {new Date().getFullYear()} Smart Campus</span><span>Attendance, verified.</span></footer></main>;
}
