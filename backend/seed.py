from sqlalchemy.orm import Session
import os
from datetime import datetime, timedelta
from secrets import token_urlsafe
from database import SessionLocal
from models import (
    User, NEPCourse, FacultySchedule, Faculty, Department, Programme,
    Venue, AcademicSession, Course, CourseEnrolment, CourseBatch, GradingBand,
)
from utils import hash_password


PERIOD_TIMES = {
    "P1": ("09:00", "09:50"),
    "P2": ("10:00", "10:50"),
    "P3": ("11:00", "11:50"),
    "P4": ("12:00", "12:50"),
    "P5": ("13:30", "14:20"),
    "P6": ("14:30", "15:20"),
}

ALL_PERIODS = ["P1", "P2", "P3", "P4", "P5", "P6"]

SEMESTERS = ["First Semester", "Second Semester"]

# Canonical demo courses — exactly three, each with a batch. The timetable
# fixtures below reference these records by code, so the whole demo dataset
# shares one authoritative course list instead of duplicating titles/codes.
DEMO_COURSES = [
    ("IT101", "Introduction to Programming", 3, "100", "First Semester"),
    ("DB201", "Database Management Systems", 3, "200", "First Semester"),
    ("SE301", "Software Engineering", 3, "300", "Second Semester"),
]

# Default grade bands, used when a lecturer releases marks.
DEFAULT_GRADE_BANDS = [
    ("A", 80, 100, 4.0, "Excellent"),
    ("B", 70, 79.99, 3.0, "Very Good"),
    ("C", 60, 69.99, 2.0, "Good"),
    ("D", 50, 59.99, 1.0, "Pass"),
    ("F", 0, 49.99, 0.0, "Fail"),
]


def _seed_structure(db: Session) -> dict:
    """Idempotently create the academic structure and return its ids."""
    faculty = db.query(Faculty).filter(Faculty.code == "SCISA").first()
    if not faculty:
        faculty = Faculty(name="School of Computing and Information Sciences",
                          code="SCISA", dean="Dean, SCISA")
        db.add(faculty)
        db.flush()

    department = db.query(Department).filter(Department.code == "CSE").first()
    if not department:
        department = Department(name="Department of Computer Science and Engineering",
                                code="CSE", faculty_id=faculty.id, head="Head of Department")
        db.add(department)
        db.flush()

    programme = db.query(Programme).filter(Programme.code == "BSC-AIDS").first()
    if not programme:
        programme = Programme(name="BSc. Computer Science with Artificial Intelligence & Data Science",
                              code="BSC-AIDS", department_id=department.id, award="BSc", duration_years=4)
        db.add(programme)
        db.flush()

    # A second department and programme so programme selection is meaningful and
    # the derived department/course scope visibly changes with the choice.
    for dept_code, dept_name in [("IT", "Department of Information Technology"),
                                 ("STAT", "Department of Statistics")]:
        d = db.query(Department).filter(Department.code == dept_code).first()
        if not d:
            db.add(Department(name=dept_name, code=dept_code, faculty_id=faculty.id,
                              head="Head of Department"))
    db.flush()
    it_dept = db.query(Department).filter(Department.code == "IT").first()
    stat_dept = db.query(Department).filter(Department.code == "STAT").first()
    for prog_code, prog_name, dept_id, award in [
        ("BSC-IT", "BSc. Information Technology", it_dept.id, "BSc"),
        ("BSC-STAT", "BSc. Statistics", stat_dept.id, "BSc"),
    ]:
        if not db.query(Programme).filter(Programme.code == prog_code).first():
            db.add(Programme(name=prog_name, code=prog_code, department_id=dept_id,
                             award=award, duration_years=4))
    db.flush()

    venues = {}
    for name, building, capacity, vtype in [
        ("Lecture Hall 10", "Science Block", 120, "lecture"),
        ("Lecture Hall 11", "Science Block", 120, "lecture"),
        ("Lecture Hall 12", "Science Block", 100, "lecture"),
        ("Lecture Hall 14", "Computer Lab Block", 60, "lab"),
        ("Lecture Hall 15", "Computer Lab Block", 60, "lab"),
        ("AI Laboratory 1", "Computer Lab Block", 45, "lab"),
    ]:
        venue = db.query(Venue).filter(Venue.name == name).first()
        if not venue:
            venue = Venue(name=name, building=building, capacity=capacity, venue_type=vtype)
            db.add(venue)
            db.flush()
        venues[name] = venue.id

    session = db.query(AcademicSession).filter(
        AcademicSession.academic_year == "2025/2026",
        AcademicSession.semester == "First Semester",
    ).first()
    if not session:
        session = AcademicSession(academic_year="2025/2026", semester="First Semester",
                                  registration_open=True, is_current=True)
        db.add(session)
        db.flush()

    db.commit()
    return {
        "faculty_id": faculty.id,
        "department_id": department.id,
        "department_name": department.name,
        "programme_id": programme.id,
        "venues": venues,
        "session_id": session.id,
        "academic_year": session.academic_year,
        "semester": session.semester,
    }


def _seed_demo_courses(db: Session, structure: dict, faculty_id: int) -> dict:
    """Create the canonical demo course records (linked to structure) + a batch each."""
    by_code = {}
    for code, title, credits, level, semester in DEMO_COURSES:
        course = db.query(Course).filter(Course.code == code).first()
        if not course:
            course = Course(
                code=code, title=title, credit_hours=credits, level=level, semester=semester,
                academic_year=structure["academic_year"], department="CSE(AI&DS)",
                department_id=structure["department_id"], programme_id=structure["programme_id"],
                lecturer_id=faculty_id, registration_code=token_urlsafe(9),
                registration_code_expires_at=datetime.utcnow() + timedelta(days=365),
                registration_open=True, enrolment_requires_approval=False, is_published=True,
            )
            db.add(course)
            db.flush()
        if not db.query(CourseBatch).filter_by(course_id=course.id, name="Batch 1").first():
            db.add(CourseBatch(course_id=course.id, name="Batch 1", lecturer_id=faculty_id,
                               capacity=None, is_active=True))
        by_code[code] = course.id
    db.commit()
    return by_code


def _seed_grade_bands(db: Session) -> None:
    if db.query(GradingBand).count() == 0:
        for name, lo, hi, gp, remark in DEFAULT_GRADE_BANDS:
            db.add(GradingBand(name=name, min_score=lo, max_score=hi, grade_point=gp, remark=remark))
        db.commit()


def seed_data():
    # Render sets RENDER=true automatically. Never seed demo identities or
    # sample academic records into a hosted/production database.
    is_production = (
        os.getenv("RENDER", "").lower() == "true"
        or os.getenv("ENVIRONMENT", "development").lower() == "production"
    )
    demo_enabled = os.getenv("SEED_DEMO_DATA", "false").lower() == "true" and not is_production
    db: Session = SessionLocal()
    if not demo_enabled:
        admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        if admin_email and admin_password:
            existing = db.query(User).filter(User.email == admin_email).first()
            if not existing:
                db.add(User(name="System Administrator",
                    email=admin_email, password=hash_password(admin_password), role="admin",
                    department="Institution", is_approved=True))
                db.commit()
        db.close()
        return

    # Local-only demonstration accounts and sample academic records.
    structure = _seed_structure(db)

    admin_email = os.getenv("DEMO_ADMIN_EMAIL", "admin@smartcampus.com").strip().lower()
    faculty_email = os.getenv("DEMO_FACULTY_EMAIL", "faculty1@smartcampus.com").strip().lower()
    student_email = os.getenv("DEMO_STUDENT_EMAIL", "student@smartcampus.com").strip().lower()

    demo_users = [
        {
            "name": os.getenv("DEMO_ADMIN_NAME", "Evelyn Owusu").strip(),
            "email": admin_email,
            "password": os.getenv("DEMO_ADMIN_PASSWORD", "Admin@12345"),
            "role": "admin",
            "department": "Smart Campus",
        },
        {
            "name": os.getenv("DEMO_FACULTY_NAME", "Daniel Mensah").strip(),
            "email": faculty_email,
            "password": os.getenv("DEMO_FACULTY_PASSWORD", "Lecturer@12345"),
            "role": "faculty",
            "department": os.getenv("DEMO_DEPARTMENT", "CSE(AI&DS)"),
        },
        {
            "name": os.getenv("DEMO_STUDENT_NAME", "Ama Serwaa").strip(),
            "email": student_email,
            "password": os.getenv("DEMO_STUDENT_PASSWORD", "Student@12345"),
            "role": "student",
            "department": os.getenv("DEMO_DEPARTMENT", "CSE(AI&DS)"),
            "index_number": os.getenv("DEMO_STUDENT_INDEX_NUMBER", "2024001").strip().upper(),
            "level": 100,
        },
    ]

    created = {}
    for record in demo_users:
        if not record["name"] or not record["email"] or not record["password"]:
            raise RuntimeError("Demo account name, email and password must all be set in backend/.env")
        user = db.query(User).filter(User.email.ilike(record["email"])).first()
        if user is None:
            user = User(email=record["email"])
            db.add(user)
        user.name = record["name"]
        user.email = record["email"]
        user.password = hash_password(record["password"])
        user.role = record["role"]
        user.department = record["department"]
        user.index_number = record.get("index_number")
        user.is_approved = True
        if record["role"] == "student":
            user.level = record.get("level", 100)
            user.programme_id = structure["programme_id"]
            user.department_id = structure["department_id"]
            user.department = structure["department_name"]
        db.flush()
        created[record["role"]] = user.id
    db.commit()

    faculty_id = created["faculty"]
    student_id = created["student"]

    # Three canonical courses, each with a batch, owned by the demo lecturer.
    course_ids = _seed_demo_courses(db, structure, faculty_id)
    venue_ids = structure["venues"]
    course_titles = {code: title for code, title, *_ in DEMO_COURSES}

    # A small, consistent weekly timetable referencing those exact courses and
    # their batch (the canonical cohort), not a free-text section.
    if db.query(FacultySchedule).filter(FacultySchedule.faculty_id == faculty_id).count() == 0:
        batch_ids = {c.id: b.id for c, b in db.query(Course, CourseBatch).join(
            CourseBatch, CourseBatch.course_id == Course.id).filter(CourseBatch.name == "Batch 1").all()}
        schedule_fixture = [
            (0, "P1", "IT101", "Lecture Hall 10", "theory"),
            (0, "P3", "DB201", "Lecture Hall 11", "theory"),
            (1, "P2", "SE301", "Lecture Hall 12", "theory"),
            (2, "P1", "IT101", "Lecture Hall 14", "lab"),
        ]
        for day, period, code, room, ctype in schedule_fixture:
            start, end = PERIOD_TIMES[period]
            cid = course_ids.get(code)
            db.add(FacultySchedule(
                faculty_id=faculty_id, day_of_week=day, period=period,
                subject=course_titles[code], subject_code=code,
                class_type=ctype, room_no=room, start_time=start, end_time=end,
                course_id=cid, venue_id=venue_ids.get(room),
                batch_id=batch_ids.get(cid),
                academic_session_id=structure["session_id"], is_published=True,
            ))
        db.commit()

    # Enrol the demo student in the demo courses (with the batch) so attendance,
    # results and the timetable all work end to end.
    for code, cid in course_ids.items():
        enrolment = db.query(CourseEnrolment).filter_by(course_id=cid, student_id=student_id).first()
        if not enrolment:
            batch = db.query(CourseBatch).filter_by(course_id=cid, name="Batch 1").first()
            db.add(CourseEnrolment(course_id=cid, student_id=student_id, status="approved",
                                   batch_id=batch.id if batch else None))
    db.commit()

    _seed_grade_bands(db)


    # ── NEP Courses — replace old incomplete rows, seed full 44-course list ──────
    # Upsert courses by title; never delete existing user data.
    courses = [

            # ── AI & Machine Learning ─────────────────────────────────────────
            NEPCourse(title="Machine Learning with Python",
                category="AI",
                skill_tag="machine learning python ai artificial intelligence scikit-learn statistics",
                duration="8 weeks", platform="NPTEL / Coursera",
                description="Supervised & unsupervised learning, model evaluation using scikit-learn."),

            NEPCourse(title="Deep Learning & Neural Networks",
                category="AI",
                skill_tag="deep learning neural networks tensorflow keras ai artificial intelligence python",
                duration="10 weeks", platform="Coursera (deeplearning.ai)",
                description="CNNs, RNNs, LSTMs, transfer learning with TensorFlow and Keras."),

            NEPCourse(title="Natural Language Processing",
                category="AI",
                skill_tag="nlp natural language processing transformers bert ai text python",
                duration="8 weeks", platform="NPTEL / Hugging Face",
                description="Text classification, sentiment analysis, transformers, BERT fine-tuning."),

            NEPCourse(title="Computer Vision with OpenCV",
                category="AI",
                skill_tag="computer vision opencv image processing ai deep learning python",
                duration="6 weeks", platform="Udemy / NPTEL",
                description="Image processing, object detection, face recognition, YOLO."),

            NEPCourse(title="Reinforcement Learning",
                category="AI",
                skill_tag="reinforcement learning ai q-learning openai gym python deep learning",
                duration="8 weeks", platform="Coursera",
                description="Markov decision processes, Q-learning, policy gradients, OpenAI Gym."),

            NEPCourse(title="Generative AI & Prompt Engineering",
                category="AI",
                skill_tag="generative ai llm chatgpt prompt engineering gpt langchain artificial intelligence",
                duration="4 weeks", platform="Google / OpenAI",
                description="LLMs, prompt design, RAG, LangChain application development."),

            # ── Data Science & Analytics ──────────────────────────────────────
            NEPCourse(title="Data Science with Python",
                category="Data",
                skill_tag="data science python pandas numpy matplotlib analysis statistics",
                duration="6 weeks", platform="NPTEL / Kaggle",
                description="EDA, data wrangling, visualisation, statistics with pandas and numpy."),

            NEPCourse(title="Data Visualisation & Storytelling",
                category="Data",
                skill_tag="data visualisation tableau power bi analytics storytelling dashboard",
                duration="4 weeks", platform="Tableau / Microsoft Learn",
                description="Dashboards, charts, Tableau, Power BI, data-driven storytelling."),

            NEPCourse(title="Big Data Analytics with Hadoop & Spark",
                category="Data",
                skill_tag="big data hadoop spark analytics distributed computing python",
                duration="8 weeks", platform="NPTEL / Cloudera",
                description="HDFS, MapReduce, Apache Spark, Hive for large-scale data processing."),

            NEPCourse(title="Statistics for Data Science",
                category="Data",
                skill_tag="statistics probability data science regression hypothesis testing python",
                duration="6 weeks", platform="NPTEL",
                description="Probability, distributions, hypothesis testing, regression analysis."),

            NEPCourse(title="Business Intelligence & Analytics",
                category="Data",
                skill_tag="business intelligence analytics power bi sql reporting dashboard",
                duration="5 weeks", platform="Microsoft Learn",
                description="KPIs, BI tools, SQL reporting, Power BI dashboards."),

            # ── Web Development ───────────────────────────────────────────────
            NEPCourse(title="Full Stack Web Development",
                category="Web",
                skill_tag="full stack web development react nodejs javascript html css mongodb",
                duration="12 weeks", platform="freeCodeCamp / NPTEL",
                description="HTML, CSS, JavaScript, React frontend + Node.js/Express backend."),

            NEPCourse(title="React & Modern Frontend Development",
                category="Web",
                skill_tag="react javascript frontend web development typescript hooks state",
                duration="6 weeks", platform="Scrimba / Udemy",
                description="React hooks, state management, TypeScript, component architecture."),

            NEPCourse(title="Backend Development with Node.js",
                category="Web",
                skill_tag="nodejs backend javascript api rest express mongodb web",
                duration="6 weeks", platform="Udemy / freeCodeCamp",
                description="REST APIs, Express.js, authentication, MongoDB integration."),

            NEPCourse(title="Django & Python Web Framework",
                category="Web",
                skill_tag="django python web development backend api rest framework",
                duration="6 weeks", platform="NPTEL / Udemy",
                description="Django ORM, REST Framework, authentication, deployment."),

            NEPCourse(title="Progressive Web Apps & UI/UX",
                category="Web",
                skill_tag="pwa ui ux design web frontend user interface mobile responsive",
                duration="5 weeks", platform="Google Developers",
                description="PWA concepts, service workers, responsive design, UX principles."),

            # ── Cloud Computing ───────────────────────────────────────────────
            NEPCourse(title="AWS Cloud Foundations",
                category="Cloud",
                skill_tag="cloud aws amazon web services devops infrastructure deployment",
                duration="6 weeks", platform="AWS Training",
                description="EC2, S3, Lambda, IAM, VPC — core AWS services and cloud concepts."),

            NEPCourse(title="Google Cloud Platform Essentials",
                category="Cloud",
                skill_tag="cloud gcp google cloud platform devops kubernetes deployment",
                duration="5 weeks", platform="Google Cloud Skills Boost",
                description="GCE, GCS, BigQuery, Cloud Run, Kubernetes on GKE."),

            NEPCourse(title="Microsoft Azure Fundamentals (AZ-900)",
                category="Cloud",
                skill_tag="cloud azure microsoft devops infrastructure certification",
                duration="4 weeks", platform="Microsoft Learn",
                description="Azure services, pricing, SLAs — AZ-900 certification prep."),

            NEPCourse(title="DevOps & CI/CD Pipelines",
                category="Cloud",
                skill_tag="devops cicd docker kubernetes jenkins git automation cloud deployment",
                duration="8 weeks", platform="Linux Foundation / Udemy",
                description="Docker, Kubernetes, Jenkins, GitHub Actions, infrastructure as code."),

            NEPCourse(title="Serverless & Microservices Architecture",
                category="Cloud",
                skill_tag="serverless microservices cloud aws lambda api gateway devops",
                duration="5 weeks", platform="AWS / Coursera",
                description="Serverless architecture, Lambda, API Gateway, microservices patterns."),

            # ── Cybersecurity ─────────────────────────────────────────────────
            NEPCourse(title="Ethical Hacking & Penetration Testing",
                category="Security",
                skill_tag="ethical hacking cybersecurity penetration testing security kali linux network",
                duration="10 weeks", platform="EC-Council / NPTEL",
                description="Network scanning, exploitation, web app hacking, Kali Linux tools."),

            NEPCourse(title="Cybersecurity Fundamentals",
                category="Security",
                skill_tag="cybersecurity network security firewalls encryption protocols defence",
                duration="6 weeks", platform="NPTEL / Cisco NetAcad",
                description="CIA triad, cryptography, firewalls, IDS/IPS, security policies."),

            NEPCourse(title="Web Application Security & OWASP",
                category="Security",
                skill_tag="web security owasp sql injection xss cybersecurity hacking testing",
                duration="5 weeks", platform="PortSwigger / OWASP",
                description="OWASP Top 10, Burp Suite, SQL injection, XSS, CSRF defences."),

            NEPCourse(title="Digital Forensics & Incident Response",
                category="Security",
                skill_tag="digital forensics cybersecurity incident response malware analysis security",
                duration="6 weeks", platform="SANS / Cybrary",
                description="Evidence acquisition, malware analysis, DFIR methodology."),

            # ── Mobile Development ────────────────────────────────────────────
            NEPCourse(title="Android App Development with Kotlin",
                category="Mobile",
                skill_tag="android kotlin mobile app development jetpack compose ui",
                duration="8 weeks", platform="Google Developers / Udacity",
                description="Kotlin basics, Jetpack Compose, MVVM, Firebase integration."),

            NEPCourse(title="Flutter & Cross-Platform Development",
                category="Mobile",
                skill_tag="flutter dart mobile app cross platform android ios development",
                duration="8 weeks", platform="Flutter.dev / Udemy",
                description="Dart, Flutter widgets, state management, REST API integration."),

            NEPCourse(title="React Native Mobile Development",
                category="Mobile",
                skill_tag="react native mobile javascript app development android ios",
                duration="6 weeks", platform="Expo / Udemy",
                description="React Native components, navigation, native APIs, deployment."),

            # ── IoT & Embedded Systems ────────────────────────────────────────
            NEPCourse(title="IoT with Arduino & Raspberry Pi",
                category="IoT",
                skill_tag="iot internet of things arduino raspberry pi embedded sensors python",
                duration="8 weeks", platform="NPTEL / Coursera",
                description="Sensors, actuators, MQTT, Arduino programming, IoT protocols."),

            NEPCourse(title="Industrial IoT & Edge Computing",
                category="IoT",
                skill_tag="iot industrial edge computing embedded systems automation ai",
                duration="6 weeks", platform="Coursera / edX",
                description="Edge AI, industrial protocols, OPC-UA, predictive maintenance."),

            # ── Database ──────────────────────────────────────────────────────
            NEPCourse(title="SQL & Relational Database Design",
                category="Database",
                skill_tag="sql database mysql postgresql relational schema design backend",
                duration="5 weeks", platform="NPTEL / Mode Analytics",
                description="SQL queries, joins, indexing, normalisation, stored procedures."),

            NEPCourse(title="MongoDB & NoSQL Databases",
                category="Database",
                skill_tag="mongodb nosql database json aggregation backend web",
                duration="4 weeks", platform="MongoDB University",
                description="Document model, CRUD, aggregation pipeline, Atlas cloud."),

            # ── Programming & Algorithms ──────────────────────────────────────
            NEPCourse(title="Data Structures & Algorithms in Python",
                category="Programming",
                skill_tag="data structures algorithms python dsa problem solving coding competitive",
                duration="10 weeks", platform="NPTEL / LeetCode",
                description="Arrays, trees, graphs, dynamic programming, competitive coding."),

            NEPCourse(title="Competitive Programming",
                category="Programming",
                skill_tag="competitive programming algorithms coding contests problem solving c++ dsa",
                duration="12 weeks", platform="Codeforces / ICPC",
                description="Graph algorithms, DP, segment trees, contest strategy."),

            NEPCourse(title="Python for Automation & Scripting",
                category="Programming",
                skill_tag="python automation scripting web scraping selenium pandas devops",
                duration="5 weeks", platform="Automate the Boring Stuff",
                description="File handling, web scraping, regex, task automation with Python."),

            NEPCourse(title="Java & Object-Oriented Programming",
                category="Programming",
                skill_tag="java object oriented programming oop backend spring development",
                duration="8 weeks", platform="NPTEL / Udemy",
                description="OOP principles, collections, exceptions, Spring Boot basics."),

            # ── Design ────────────────────────────────────────────────────────
            NEPCourse(title="UI/UX Design with Figma",
                category="Design",
                skill_tag="ui ux design figma user interface prototype wireframe web mobile",
                duration="6 weeks", platform="Figma / Google UX Design",
                description="User research, wireframing, prototyping, design systems in Figma."),

            NEPCourse(title="Graphic Design & Visual Communication",
                category="Design",
                skill_tag="graphic design adobe photoshop illustrator visual communication",
                duration="5 weeks", platform="Adobe / Canva",
                description="Design principles, typography, colour theory, Adobe tools."),

            # ── Business & Entrepreneurship ───────────────────────────────────
            NEPCourse(title="Startup & Entrepreneurship Fundamentals",
                category="Business",
                skill_tag="startup entrepreneurship business management innovation lean product",
                duration="4 weeks", platform="NPTEL / edX",
                description="Lean startup, business model canvas, pitching, funding basics."),

            NEPCourse(title="Digital Marketing & SEO",
                category="Business",
                skill_tag="digital marketing seo social media content google ads analytics business",
                duration="5 weeks", platform="Google Digital Garage",
                description="SEO, SEM, social media marketing, Google Ads, analytics."),

            NEPCourse(title="Product Management",
                category="Business",
                skill_tag="product management agile scrum roadmap ux business strategy startup",
                duration="6 weeks", platform="Coursera / ProductHunt",
                description="Product lifecycle, roadmaps, agile, user stories, metrics."),

            # ── Soft Skills ───────────────────────────────────────────────────
            NEPCourse(title="Communication & Presentation Skills",
                category="Soft Skills",
                skill_tag="communication presentation public speaking soft skills leadership interpersonal",
                duration="4 weeks", platform="Coursera / Toastmasters",
                description="Public speaking, storytelling, slide design, professional communication."),

            NEPCourse(title="Leadership & Team Management",
                category="Soft Skills",
                skill_tag="leadership management teamwork agile soft skills collaboration",
                duration="4 weeks", platform="Coursera / LinkedIn Learning",
                description="Leadership styles, conflict resolution, team dynamics, agile teams."),

            # ── Blockchain & Emerging Tech ────────────────────────────────────
            NEPCourse(title="Blockchain & Web3 Development",
                category="Blockchain",
                skill_tag="blockchain web3 ethereum solidity smart contracts cryptocurrency decentralised",
                duration="8 weeks", platform="Coursera / Buildspace",
                description="Ethereum, Solidity, smart contracts, DApps, NFT development."),

            NEPCourse(title="Quantum Computing Basics",
                category="Emerging Tech",
                skill_tag="quantum computing qiskit physics emerging technology research ai",
                duration="5 weeks", platform="IBM Quantum / edX",
                description="Qubits, quantum gates, Qiskit, quantum algorithms introduction."),

            NEPCourse(title="AR/VR Development with Unity",
                category="Emerging Tech",
                skill_tag="ar vr augmented reality virtual reality unity3d metaverse game",
                duration="6 weeks", platform="Unity / Meta",
                description="Unity3D, AR Foundation, VR headset development, XR interactions."),

            NEPCourse(title="Game Development with Unity",
                category="Emerging Tech",
                skill_tag="game development unity3d c# ar vr graphics animation",
                duration="8 weeks", platform="Unity Learn",
                description="Unity engine, C# scripting, physics, 2D/3D game development."),
    ]
    for course in courses:
        existing = db.query(NEPCourse).filter(NEPCourse.title == course.title).first()
        if existing:
            existing.category = course.category
            existing.skill_tag = course.skill_tag
            existing.duration = course.duration
            existing.platform = course.platform
            existing.description = course.description
        else:
            db.add(course)
    db.commit()
    db.close()