# Smart Campus — UCC-ready attendance and academic workspace

Smart Campus is a React/Vite frontend, FastAPI backend and PostgreSQL database application. The intended production arrangement is **GitHub → Vercel (frontend) → Render (API) → Supabase PostgreSQL (database)**.

> **Important production note:** the backend currently stores private attendance selfies on its local filesystem (`backend/private_uploads/attendance`). Render's ordinary ephemeral filesystem can be cleared during restarts/redeploys. For production selfie retention, attach a Render persistent disk mounted at `backend/private_uploads`, or migrate the private image store to a private Supabase Storage bucket before launch. Do not assume the free ephemeral filesystem is durable.

## 1. Project structure

- `frontend/` — React 19, Vite and React Router application.
- `backend/` — FastAPI API, SQLAlchemy models, authentication, attendance and academic workflows.
- `backend/routers/` — role-specific API routes.
- `backend/tests/` — API integration tests.
- `render.yaml` — Render Blueprint for the backend.
- `frontend/vercel.json` — SPA route rewrite for Vercel.
- `backend/.env.example` and `frontend/.env.example` — configuration templates. Never commit real `.env` files or secrets.

## 2. Requirements for local development

Install:
- Python 3.11 or 3.12
- Node.js 20 or newer and npm
- Git
- A modern browser

Camera and location APIs require HTTPS in production. Browsers permit them on `localhost` for local development.

### Start the backend (Windows PowerShell)

```powershell
cd Smart-Campusackend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

### Start the frontend (a second terminal)

```powershell
cd Smart-Campusrontend
npm ci
Copy-Item .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. API documentation is at `http://127.0.0.1:8000/docs`.

For macOS/Linux, replace `py -3.12` with `python3`, use `source .venv/bin/activate`, and copy files with `cp .env.example .env`.

## 3. Supabase database setup

1. Create a Supabase project.
2. Open **Project Settings → Database → Connection string**.
3. Choose the connection string intended for a persistent server connection. For Render, use the Supabase pooler connection if direct IPv6 connectivity is unavailable; use the transaction/session pooler mode recommended by Supabase for your connection pattern.
4. Copy the URI and replace the password placeholder with the database password. URL-encode special characters in the password.
5. Keep the URI private. It belongs only in Render's backend environment variables, never in Vercel or frontend code.
6. The backend normalizes `postgres://` URLs and uses SSL for remote PostgreSQL connections. Tables are created/migrated by the backend startup logic; do not paste SQL manually unless a future migration explicitly instructs you to.

Use a dedicated database password. If it has characters such as `@`, `:`, `/`, `#` or `%`, URL-encode them before inserting them into the connection URI.

## 4. Push the project to GitHub

Create an empty GitHub repository, then from the project root:

```bash
git init
git add .
git status
git commit -m "Prepare Smart Campus for deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Replace the repository URL with your actual GitHub repository. Check `git status` before committing and confirm that `.env`, `.venv`, `node_modules`, local databases and private uploads are not staged.

## 5. Deploy the backend to Render

1. Sign in to Render and choose **New → Blueprint** (or create a Web Service manually).
2. Connect the GitHub repository containing this project. Render detects the root `render.yaml`.
3. The Blueprint uses `backend` as the root directory, installs `backend/requirements.txt`, starts Uvicorn on Render's `$PORT`, and checks `/health`.
4. In the Render service's **Environment** tab, set the variables below.
5. Deploy and wait for the service to become **Live**.
6. Open `https://YOUR-API.onrender.com/health`. It should return a healthy response. Also open `/docs` to confirm the API is reachable.

### Required Render environment variables

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Supabase PostgreSQL connection URI |
| `JWT_SECRET_KEY` | Long, random, private secret (at least 32 random bytes) |
| `CORS_ORIGINS` | Your exact Vercel origin, e.g. `https://your-app.vercel.app` (comma-separate additional trusted origins) |
| `SEED_DEMO_DATA` | `false` |
| `APP_TIMEZONE` | `Africa/Accra` |
| `BOOTSTRAP_ADMIN_NAME` | Name of the initial administrator |
| `BOOTSTRAP_ADMIN_EMAIL` | Real administrator email |
| `BOOTSTRAP_ADMIN_PASSWORD` | Strong, unique initial password |
| `ATTENDANCE_GPS_RADIUS_METERS` | `50` (or institutional policy) |
| `ATTENDANCE_GPS_ACCURACY_CEILING` | `500` (maximum tolerated reported GPS accuracy in metres) |
| `ATTENDANCE_GPS_SESSION_ACCURACY_CEILING` | `500` |

Optional payment configuration (only if lecturer registration payments are enabled):

| Variable | Value |
|---|---|
| `PAYSTACK_SECRET_KEY` | Paystack **secret** key; backend only |
| `PAYSTACK_CALLBACK_URL` | `https://YOUR-VERCEL-DOMAIN/lecturer/payment/callback` |

Do not put Paystack secret keys, Supabase service-role keys, database passwords or JWT secrets in Vercel. The frontend must never receive a backend secret.

## 6. Deploy the frontend to Vercel

1. In Vercel choose **Add New → Project** and import the GitHub repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Vite**.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add this environment variable:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://YOUR-RENDER-SERVICE.onrender.com` (no trailing slash) |

7. Deploy. Copy the Vercel production domain.
8. Return to Render and set `CORS_ORIGINS` to that exact origin, then redeploy the backend.
9. If you change `VITE_API_URL`, trigger a new Vercel deployment because Vite embeds it at build time.

`frontend/vercel.json` contains the SPA rewrite so direct navigation/refresh on nested React routes returns the application entry point.

## 7. First production login and security

- Create the initial administrator using the `BOOTSTRAP_ADMIN_*` values on Render.
- Keep `SEED_DEMO_DATA=false` in production. The demo users shown for local testing are not production accounts.
- Sign in with the bootstrap administrator account, then change the password if the application provides that workflow.
- Never reuse the sample local demo passwords in production.
- Keep the Supabase database, Render service and Vercel project private to the people who administer them.
- Configure backups and test restoration before real student records are entered.
- Provide an institutional privacy notice and retention/deletion policy for student identity details, selfies and location evidence.

## 8. GPS and attendance troubleshooting

- Open the site over HTTPS on the student's phone; browser geolocation is not available on an ordinary non-secure HTTP production origin.
- Allow location permission for the site and enable Location Services on Android/iOS.
- On Android, set the browser/site permission to allow location and enable precise location where the OS offers that option.
- Turn off battery saver/location restrictions temporarily, move near a window or outdoors, and retry if the device reports a very coarse fix.
- A lecturer must open the attendance session with a valid location before students scan its QR code.
- The system records reported GPS accuracy and still checks the student's coordinate against the lecturer's session radius. A permissive accuracy ceiling does **not** enlarge the classroom radius.
- If the device cannot return any coordinates, no web application can manufacture a reliable GPS fix. Try another browser/device or correct the device's location settings.

The default student GPS accuracy ceiling is now 500 metres to avoid rejecting many usable Android/network-derived fixes at the previous 150-metre threshold. The actual geofence distance remains independently enforced. Institutions that require stricter location assurance should lower this value and test it across their campus devices and buildings.

## 9. Common deployment errors

**Frontend says Failed to fetch**
- Confirm `VITE_API_URL` is the live Render URL, without a trailing slash.
- Confirm Render `/health` responds.
- Confirm Render `CORS_ORIGINS` exactly matches the Vercel origin, including `https://` and excluding a trailing slash.
- Redeploy Vercel after changing its environment variable and redeploy Render after changing CORS.

**Database connection fails**
- Recheck the Supabase URI, password encoding and SSL requirement.
- Use the appropriate Supabase pooler URI if Render cannot connect directly.
- Confirm the Supabase project is not paused and database credentials have not been rotated.

**Camera or GPS permission fails**
- Use HTTPS, grant browser permission, and check the device-level camera/location settings.

**Selfie cannot be retrieved after redeployment**
- Check whether the backend is using an ephemeral filesystem. Attach a persistent Render disk at the configured private-upload directory or implement private object storage before relying on long-term photo retention.

## 10. Run checks before release

Backend:

```bash
cd backend
python -m compileall -q .
pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Do not call the application production-ready solely because it deploys. Test the full workflow on actual phones and accounts: student signup/login, lecturer course creation, student course registration, lecturer attendance session/QR generation, student QR scan + selfie + GPS, lecturer register review, administrator oversight, and refresh/deep-link navigation on mobile.

## 11. Known implementation boundaries

The app's attendance verification uses QR/session credentials, a selfie upload and browser geolocation. It does not by itself provide certified face recognition/liveness detection, official Ghana Card/NIA verification, native offline attendance or SMS/email delivery. Do not describe those as available unless separately integrated and tested. The application must be tested with your institution's real policies and devices before live student use.
