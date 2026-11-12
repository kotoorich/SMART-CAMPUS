import { ArrowRight, BookOpen, Eye, EyeOff, GraduationCap, LockKeyhole, Mail, ShieldCheck, Sparkles, Users, UserRoundCog, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { loginUser } from "../../services/api";

const roles = [
  { id: "student", label: "Student", icon: GraduationCap, description: "Attendance portal" },
  { id: "faculty", label: "Lecturer", icon: BookOpen, description: "Lecturer attendance workspace" },
  { id: "admin", label: "Administrator", icon: UserRoundCog, description: "Campus control" },
];

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedRole = searchParams.get("role");
  const { login } = useAuth();
  const [role, setRole] = useState(roles.some((r) => r.id === requestedRole) ? requestedRole : "student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (event) => {
    event?.preventDefault();
    setError("");
    if (!email.trim() || !password) return setError("Enter your email address and password to continue.");
    try {
      setLoading(true);
      const data = await loginUser(email.trim(), password, role);
      login(data);
      navigate(`/${data.role}/dashboard`, { replace: true });
    } catch (err) {
      const detail = err?.message || "";
      setError(/failed to fetch|networkerror|load failed/i.test(detail)
        ? "We cannot reach the Smart Campus server. Check that the backend is running and that the frontend API URL and backend CORS settings match."
        : detail || "We could not sign you in. Check your details and try again.");
    } finally {
      setLoading(false);
    }
  };

  const activeRole = roles.find((item) => item.id === role);

  return (
    <main className="auth-screen">
      <div className="auth-ambient auth-ambient-one" />
      <div className="auth-ambient auth-ambient-two" />
      <div className="auth-topbar">
        <button className="brand-lockup" onClick={() => navigate("/")} aria-label="Smart Campus home">
          <span className="brand-mark"><GraduationCap size={22} strokeWidth={2.2} /></span>
          <span><strong>smartcampus</strong><small>THE CONNECTED CAMPUS</small></span>
        </button>
        <div className="auth-top-note"><span className="live-dot" /> Campus access portal</div>
      </div>

      <section className="auth-layout">
        <div className="auth-story">
          <div className="story-kicker"><Sparkles size={14} /> CAMPUS ATTENDANCE. MADE ACCOUNTABLE.</div>
          <h1>Make every<br /><em>moment</em> count.</h1>
          <p className="story-copy">A focused, secure way to manage attendance across institutions — from course enrolment to verified classroom check-ins.</p>
          <div className="story-visual" aria-hidden="true">
            <div className="orbit orbit-a" /><div className="orbit orbit-b" />
            <div className="orbit-core"><GraduationCap size={42} /></div>
            <div className="float-card float-card-top"><span className="float-icon"><BookOpen size={16}/></span><span><b>Attendance, verified</b><small>Courses & class lists</small></span><CheckCircle2 size={17} className="float-check"/></div>
            <div className="float-card float-card-bottom"><span className="float-icon float-icon-green"><Users size={16}/></span><span><b>Campus attendance</b><small>People & attendance</small></span><span className="mini-pulse"/></div>
            <span className="visual-spark spark-one">✳</span><span className="visual-spark spark-two">✦</span>
          </div>
          <div className="story-foot"><ShieldCheck size={16}/> Secure access for your campus community</div>
        </div>

        <div className="auth-card-wrap">
          <form className="auth-card" onSubmit={handleLogin}>
            <div className="auth-card-heading">
              <span className="auth-eyebrow">WELCOME BACK</span>
              <h2>Sign in to continue<span>.</span></h2>
              <p>Choose your workspace and enter your account details.</p>
            </div>

            <div className="role-picker" role="tablist" aria-label="Choose account type">
              {roles.map(({ id, label, icon: Icon }) => (
                <button type="button" key={id} role="tab" aria-selected={role === id} className={`role-option ${role === id ? "is-active" : ""}`} onClick={() => { setRole(id); setError(""); }}>
                  <Icon size={17}/><span>{label}</span>
                </button>
              ))}
            </div>
            <div className="role-hint"><span className="role-hint-icon"><activeRole.icon size={15}/></span><span><b>{activeRole.description}</b><small>Sign in with your registered campus account</small></span></div>

            <label className="auth-label" htmlFor="login-email">Email address</label>
            <div className="auth-input-wrap"><Mail size={17}/><input id="login-email" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required /></div>

            <div className="auth-label-row"><label className="auth-label" htmlFor="login-password">Password</label></div>
            <div className="auth-input-wrap"><LockKeyhole size={17}/><input id="login-password" type={showPassword ? "text" : "password"} placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required/><button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>

            {error && <div className="auth-error" role="alert">{error}</div>}
            <button className="auth-submit" type="submit" disabled={loading}>{loading ? <><span className="button-spinner"/> Signing you in...</> : <>Continue to {activeRole.label}<ArrowRight size={18}/></>}</button>

            <div className="auth-register-options" aria-label="Registration options">
              <p className="auth-register">New student? <button type="button" onClick={() => navigate("/signup")}>Register here</button></p>
              <p className="auth-register">New lecturer? <button type="button" onClick={() => navigate("/lecturer/signup")}>Register your staff account</button></p>
            </div>
            {import.meta.env.DEV && <details className="demo-access"><summary>Local demo accounts</summary><div><span>Evelyn Owusu · Administrator</span><code>admin@smartcampus.com / Admin@12345</code></div><div><span>Daniel Mensah · Lecturer</span><code>faculty1@smartcampus.com / Lecturer@12345</code></div><div><span>Ama Serwaa · Student</span><code>student@smartcampus.com / Student@12345</code></div><small>These development-only accounts are configured in backend/.env and are disabled in production.</small></details>}
            <div className="auth-card-footer"><ShieldCheck size={14}/> Your information is protected with secure sign-in</div>
          </form>
          <div className="auth-help">Having trouble accessing your account? <span>Contact the Smart Campus administrator.</span></div>
        </div>
      </section>
      <footer className="auth-footer"><span>© {new Date().getFullYear()} Smart Campus</span><span>Built for a more connected campus <span className="footer-star">✳</span></span></footer>
    </main>
  );
}