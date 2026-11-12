# Smart Campus rebuild notes

## Product decisions applied

- Smart Campus is an independent attendance platform for students and lecturers from different institutions. No institution creation, faculty/department setup wizard, or institution ownership workflow is exposed.
- Student and lecturer registrations collect their own institution and academic/professional profile details.
- Students can view lecturers connected to their approved courses. Lecturers can view students who have pending or approved enrolment requests for their own courses. Administrators can view all student and lecturer profiles.
- Shared profiles do not expose passwords, full Ghana Card numbers, or private registration/attendance images. Administrators have separate authorised evidence-review controls.
- Course timetables are informational. A lecturer can open attendance for any owned course at any time, regardless of the scheduled day or time.
- Each live attendance session snapshots the lecturer-selected GPS radius and expiry. Student submissions are checked against the live session, not the course timetable.
- Each attendance submission requires a selfie. Exact byte-for-byte reuse of a previous attendance selfie is rejected as an anti-replay measure. This is not face recognition or liveness detection.
- Lecturers can open each attendance selfie in their own course register. Administrators can review attendance records and evidence platform-wide.
- Student, lecturer and administrator guided tours are included and can be restarted from the Guided tour control.

## Verification status

- Backend Python compilation: passed.
- SQLite schema creation and migration smoke test: passed for institution/profile fields, course institution/programme fields, per-session GPS radius, selfie hash, GPS accuracy and distance fields.
- FastAPI import and route smoke test: passed. Institution setup routes are not mounted.
- Backend API integration tests: 39 passed using temporary local compatibility stubs for `passlib` and `python-jose`, which were unavailable in the execution environment. These stubs were only used by the test harness and are not included in the app. Production password hashing and JWT signing still require the real dependencies from `backend/requirements.txt`.
- Frontend syntax and local-import checks: passed for all 30 JavaScript/JSX files.
- Full Vite build and real dependency-backed lint were not completed: npm registry access timed out / DNS was unavailable, so frontend packages could not be installed in this environment.

## Deployment requirements and limitations

- Install the actual Python and npm dependencies using the included requirements and package lock files before deployment.
- Configure `JWT_SECRET_KEY`, database settings, private upload storage and Paystack settings in the backend environment. Never commit `.env` or secrets.
- Camera and GPS require browser permission and HTTPS in production.
- Selfie capture does not perform automated face matching or liveness detection. GPS is a proximity signal and can be spoofed on some devices; retain the combined session code, enrolment, GPS, selfie evidence and audit trail.
