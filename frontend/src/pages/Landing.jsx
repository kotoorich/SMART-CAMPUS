import { useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  ArrowRight, BookOpen, CalendarDays, ClipboardCheck, GraduationCap, Landmark,
  LayoutDashboard, MapPin, Menu, QrCode, ShieldCheck, Users, X,
} from "lucide-react"
import "./Landing.css"

const CAMPUS_IMAGE = "https://images.unsplash.com/photo-1562774053-701939374585?auto=format&fit=crop&w=1920&q=80"

const FEATURES = [
  { icon: BookOpen, title: "Code-based course enrolment", text: "Students join only the courses for which their lecturer has issued a registration code." },
  { icon: CalendarDays, title: "Class scheduling", text: "Students can view planned class times, while lecturers can open attendance whenever needed." },
  { icon: QrCode, title: "Live QR attendance", text: "Short-lived attendance sessions prevent reuse of old classroom codes." },
  { icon: MapPin, title: "Classroom proximity", text: "GPS distance checks confirm that students are near the location set for the live session." },
  { icon: ClipboardCheck, title: "Attendance registers", text: "Lecturers see the complete enrolled roster, timestamps, absences and reports." },
  { icon: ShieldCheck, title: "Platform administration", text: "Administrators manage users, approvals, fees and platform-wide attendance policies." },
]

const PORTALS = [
  { icon: GraduationCap, role: "Student", text: "Join courses with a lecturer code and mark verified attendance.", to: "/login?role=student" },
  { icon: BookOpen, role: "Lecturer", text: "Create courses, schedule classes and manage attendance registers.", to: "/login?role=faculty" },
  { icon: LayoutDashboard, role: "Administrator", text: "Manage accounts, registration fees, courses and platform-wide reports.", to: "/login?role=admin" },
]

export default function Landing() {
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [imageOk, setImageOk] = useState(true)
  const go = (to) => { setMenuOpen(false); navigate(to) }

  return (
    <div className="landing">
      <header className="landing-nav">
        <button className="landing-brand" onClick={() => go("/")} aria-label="Smart Campus home">
          <span className="landing-brand-mark"><GraduationCap size={22} /></span>
          <span className="landing-brand-text"><strong>Smart Campus</strong><small>INDEPENDENT ATTENDANCE PLATFORM</small></span>
        </button>
        <nav className={`landing-links ${menuOpen ? "open" : ""}`} aria-label="Primary">
          <a href="#platform" onClick={() => setMenuOpen(false)}>Platform</a>
          <a href="#portals" onClick={() => setMenuOpen(false)}>Portals</a>
          <a href="#features" onClick={() => setMenuOpen(false)}>Features</a>
          <button className="landing-cta" onClick={() => go("/login")}>Sign in <ArrowRight size={16} /></button>
          <button className="landing-cta landing-lecturer-register" onClick={() => go("/lecturer/signup")}>Lecturer registration</button>
        </nav>
        <button type="button" className="landing-menu-toggle" onClick={() => setMenuOpen((v) => !v)} aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen}>
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-media" aria-hidden="true">{imageOk ? <img src={CAMPUS_IMAGE} alt="" onError={() => setImageOk(false)} /> : <div className="landing-hero-fallback" />}<div className="landing-hero-scrim" /></div>
        <div className="landing-hero-inner">
          <p className="landing-kicker"><Landmark size={15} /> SMART CAMPUS · INDEPENDENT PLATFORM</p>
          <h1>Attendance that works across institutions.</h1>
          <p className="landing-lede">A shared attendance platform where students, lecturers and administrators work together without being tied to one university or college.</p>
          <div className="landing-hero-actions">
            <button className="landing-primary" onClick={() => go("/login")}>Access the portal <ArrowRight size={17} /></button>
            <button className="landing-ghost" onClick={() => go("/signup")}>Create your student account</button>
            <button className="landing-ghost" onClick={() => go("/lecturer/signup")}>Register as a lecturer</button>
          </div>
          <div className="landing-hero-facts"><span><MapPin size={15} /> Across institutions</span><span><ShieldCheck size={15} /> Server-verified access</span><span><Users size={15} /> Three role portals</span></div>
        </div>
      </section>

      <main className="landing-body">
        <section id="platform" className="landing-section">
          <div className="landing-section-head"><p className="landing-eyebrow">THE PLATFORM</p><h2>One platform. Three clear workspaces.</h2><p>Lecturers create and manage their own courses. Students join with a course code, while administrators oversee accounts, approvals and platform-wide attendance.</p></div>
          <div className="landing-flow" role="list">
            {[
              { step: "01", title: "Lecturer creates a course", text: "The lecturer sets the course details and generates a secure enrolment code." },
              { step: "02", title: "Lecturer plans the timetable", text: "Students can see scheduled classes; attendance opens separately whenever the lecturer starts a session." },
              { step: "03", title: "Student joins by code", text: "The course is previewed and eligibility is checked before enrolment." },
              { step: "04", title: "Lecturer opens attendance", text: "A live QR or short code, GPS verification and a fresh attendance selfie." },
            ].map((item) => <article className="landing-flow-item" role="listitem" key={item.step}><span>{item.step}</span><strong>{item.title}</strong><p>{item.text}</p></article>)}
          </div>
        </section>

        <section id="portals" className="landing-section">
          <div className="landing-section-head"><p className="landing-eyebrow">PORTALS</p><h2>Choose your workspace</h2></div>
          <div className="landing-portals">
            {PORTALS.map(({ icon: Icon, role, text, to }) => (
              <div className="landing-portal" key={role}>
                <span className="landing-portal-icon"><Icon size={22} /></span><strong>{role}</strong><p>{text}</p>
                <button className="landing-portal-link" type="button" onClick={() => go(to)}>Sign in <ArrowRight size={15} /></button>
                {role === "Lecturer" && <button className="landing-portal-link" type="button" onClick={() => go("/lecturer/signup")}>Register as lecturer <ArrowRight size={15} /></button>}
                {role === "Student" && <button className="landing-portal-link" type="button" onClick={() => go("/signup")}>Register as student <ArrowRight size={15} /></button>}
              </div>
            ))}
          </div>
        </section>

        <section id="features" className="landing-section">
          <div className="landing-section-head"><p className="landing-eyebrow">CAPABILITIES</p><h2>What the system does</h2></div>
          <div className="landing-features">{FEATURES.map(({ icon: Icon, title, text }) => <article className="landing-feature" key={title}><span><Icon size={19} /></span><strong>{title}</strong><p>{text}</p></article>)}</div>
        </section>

        <section className="landing-cta-band">
          <div><h2>Attendance, made simpler across institutions.</h2><p>Sign in to your Smart Campus account, or register as a student or lecturer to get started.</p></div>
          <div className="landing-cta-actions"><button className="landing-primary" onClick={() => go("/login")}>Sign in <ArrowRight size={17} /></button><button className="landing-ghost dark" onClick={() => go("/signup")}>Student registration</button><button className="landing-ghost dark" onClick={() => go("/lecturer/signup")}>Lecturer registration</button></div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-grid">
          <div><span className="landing-brand-mark small"><GraduationCap size={19} /></span><strong>Smart Campus</strong><p>An independent attendance platform for students and lecturers across institutions.</p></div>
          <div><h3>Platform</h3><a href="#platform">Academic record</a><a href="#features">Capabilities</a><a href="#portals">Portals</a></div>
          <div><h3>Access</h3><button onClick={() => go("/login?role=student")}>Student portal</button><button onClick={() => go("/login?role=faculty")}>Lecturer portal</button><button onClick={() => go("/login?role=admin")}>Administrator portal</button><button onClick={() => go("/lecturer/signup")}>Lecturer registration</button></div>
          <div><h3>Support</h3><span>Contact the Smart Campus administrator</span><span>Platform support · Account assistance</span></div>
        </div>
        <div className="landing-footer-base"><span>© {new Date().getFullYear()} Smart Campus · Independent attendance platform</span><span>Built for students, lecturers and administrators across institutions.</span></div>
      </footer>
    </div>
  )
}