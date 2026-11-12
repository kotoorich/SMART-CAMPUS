import { useRef, useState } from "react";
import Webcam from "react-webcam";
import { ArrowLeft, ArrowRight, Camera, CheckCircle2, GraduationCap, ShieldCheck, UserPlus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { signupStudent } from "../../services/api";

const videoConstraints = { width: 640, height: 480, facingMode: "user" };

export default function StudentSignup() {
  const navigate = useNavigate();
  const webcam = useRef(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [selfie, setSelfie] = useState("");
  const [consent, setConsent] = useState(false);
  const [form, setForm] = useState({ name: "", index_number: "", email: "", phone: "", ghana_card_number: "", password: "", institution_name: "", faculty_name: "", department_name: "", programme_name: "", academic_year: "", level: "100" });
  const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [done, setDone] = useState(false);
  const change = e => setForm(current => ({ ...current, [e.target.name]: e.target.value }));

  const capture = () => {
    const image = webcam.current?.getScreenshot();
    if (!image) return setCameraError("The camera is not ready. Allow camera access and try again.");
    setSelfie(image); setCameraError("");
  };
  const uploadFallback = e => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return setCameraError("Choose a JPG, PNG or WebP image.");
    if (file.size > 3 * 1024 * 1024) return setCameraError("Choose an image smaller than 3 MB.");
    const reader = new FileReader();
    reader.onload = () => setSelfie(String(reader.result || ""));
    reader.onerror = () => setCameraError("The selected image could not be read.");
    reader.readAsDataURL(file);
  };

  const submit = async e => {
    e.preventDefault(); setError("");
    if (!selfie) return setError("Capture a registration selfie before continuing.");
    if (!consent) return setError("Please provide consent for secure identity-photo processing.");
    setLoading(true);
    try {
      const result = await signupStudent({
        name: form.name.trim(), index_number: form.index_number.trim().toUpperCase(),
        email: form.email.trim().toLowerCase(), phone: form.phone.trim(),
        ghana_card_number: form.ghana_card_number.trim().toUpperCase(),
        registration_selfie: selfie, biometric_method: "selfie", consent_biometrics: consent,
        password: form.password, level: Number(form.level),
        institution_name: form.institution_name.trim(), faculty_name: form.faculty_name.trim(),
        department_name: form.department_name.trim(), programme_name: form.programme_name.trim(),
        academic_year: form.academic_year.trim(),
      });
      setDone(result); setError("");
    } catch (err) { setError(err.message || "Registration could not be completed. Please try again."); }
    finally { setLoading(false); }
  };

  return <main className="auth-screen signup-auth-screen"><div className="auth-ambient auth-ambient-one"/><div className="auth-ambient auth-ambient-two"/>
    <header className="auth-topbar"><button className="brand-lockup" onClick={() => navigate("/")}><span className="brand-mark"><GraduationCap size={22}/></span><span><strong>smartcampus</strong><small>ATTENDANCE MANAGEMENT</small></span></button><button className="signup-back" onClick={() => navigate("/")}><ArrowLeft size={15}/> Back to sign in</button></header>
    <section className="auth-layout signup-auth-layout"><div className="auth-story"><div className="story-kicker"><UserPlus size={14}/> STUDENT REGISTRATION</div><h1>Your campus.<br/><em>Your attendance.</em></h1><p className="story-copy">Create your verified student account to join approved courses and record attendance in class.</p><div className="signup-benefit"><ShieldCheck size={18}/><span><b>Identity-protected registration</b><small>Your Ghana Card number is used for duplicate checks; the full number is not stored in plain text.</small></span></div></div>
      <div className="auth-card-wrap"><form className="auth-card signup-form-card" onSubmit={submit}>{done ? <div className="signup-success"><span><CheckCircle2 size={28}/></span><h2>Registration received.</h2><p>{done.status === "approved" ? "Your student account is active. You can sign in now." : "Your details and selfie have been submitted for administrator verification. You can sign in after approval."}</p><button type="button" className="auth-submit" onClick={() => navigate("/login")}>Return to sign in <ArrowRight size={17}/></button></div> : <><div className="auth-card-heading"><span className="auth-eyebrow">STUDENT ONBOARDING</span><h2>Create your account<span>.</span></h2><p>Complete each required field accurately.</p></div>
        <div className="signup-fields">
          <label>Full legal name<input name="name" value={form.name} onChange={change} placeholder="As shown on your student record" required autoComplete="name"/></label>
          <label>Index number<input name="index_number" value={form.index_number} onChange={change} placeholder="e.g. PSITC/22/001" required autoCapitalize="characters"/></label>
          <label>Institution name<input name="institution_name" value={form.institution_name} onChange={change} placeholder="Your university or college" required/></label>
          <label>Faculty / School<input name="faculty_name" value={form.faculty_name} onChange={change} placeholder="Faculty or school" required/></label>
          <label>Department<input name="department_name" value={form.department_name} onChange={change} placeholder="Your department" required/></label>
          <label>Programme<input name="programme_name" value={form.programme_name} onChange={change} placeholder="Your programme" required/></label>
          <label>Academic year<input name="academic_year" value={form.academic_year} onChange={change} placeholder="e.g. 2026/2027" required/></label>
          <label>Email address<input name="email" type="email" value={form.email} onChange={change} placeholder="you@example.com" required autoComplete="email"/></label>
          <label>Phone number<input name="phone" type="tel" value={form.phone} onChange={change} placeholder="+233..." required autoComplete="tel"/></label>
          <label className="signup-wide">Ghana Card number<input name="ghana_card_number" value={form.ghana_card_number} onChange={change} placeholder="GHA-XXXXXXXXX-X" required autoCapitalize="characters"/></label>
          <label>Password<input name="password" type="password" value={form.password} onChange={change} placeholder="At least 8 characters" minLength={8} required autoComplete="new-password"/></label>
          <label>Level<select name="level" value={form.level} onChange={change}>{["100","200","300","400","500","600","700"].map(l => <option key={l} value={l}>Level {l}</option>)}</select></label>
        </div>
        <div className="signup-selfie-block"><div className="auth-label"><Camera size={15}/> Registration selfie</div>
          {selfie ? <div className="signup-selfie-preview"><img src={selfie} alt="Captured registration selfie"/><button type="button" onClick={() => setSelfie("")}>Retake selfie</button></div> : <><div className="signup-webcam"><Webcam ref={webcam} audio={false} screenshotFormat="image/jpeg" screenshotQuality={0.78} videoConstraints={videoConstraints} onUserMedia={() => { setCameraReady(true); setCameraError(""); }} onUserMediaError={() => { setCameraReady(false); setCameraError("Camera unavailable. Allow camera access or use the secure image fallback below."); }} /></div><button type="button" className="auth-submit" onClick={capture} disabled={!cameraReady}><Camera size={16}/> Capture selfie</button><label className="signup-upload-fallback">Camera unavailable? Select a selfie<input type="file" accept="image/jpeg,image/png,image/webp" capture="user" onChange={uploadFallback}/></label></>}
          {cameraError && <div className="auth-error" role="alert">{cameraError}</div>}
          <label className="signup-consent"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}/> I consent to the secure collection and processing of my registration selfie for identity verification and attendance integrity.</label>
          <small className="signup-privacy-note">The selfie is stored privately. This registration captures identity evidence; no automated face recognition is performed; the image is retained as evidence for authorised review.</small>
        </div>
        {error&&<div className="auth-error" role="alert">{error}</div>}
        <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><span className="button-spinner"/> Creating account…</> : <>Submit registration <ArrowRight size={17}/></>}</button>
        <p className="auth-register">Already registered? <button type="button" onClick={() => navigate("/login")}>Sign in</button></p><div className="auth-card-footer"><ShieldCheck size={14}/> Your identity information is protected</div></>}</form></div></section>
    <footer className="auth-footer"><span>© {new Date().getFullYear()} Smart Campus</span><span>Attendance, verified.</span></footer></main>;
}
