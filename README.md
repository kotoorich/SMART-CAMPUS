# Smart Campus — UCC-ready academic and attendance platform

Smart Campus is a web application built with **React + Vite** (frontend), **FastAPI + SQLAlchemy** (backend), and **SQLite or PostgreSQL** (database).

The application supports student, lecturer and administrator workflows. Lecturers manage their courses/classes and attendance sessions; students register for courses and record attendance; administrators oversee academic and attendance activity.

This README contains two independent setup guides:

- **Part A — Run Smart Campus on your own computer (localhost).** Use this when developing, testing or demonstrating the application locally.
- **Part B — Deploy Smart Campus online.** Use this when publishing the frontend on Vercel, the API on Render and the production database on Supabase.

You do **not** need to deploy to Vercel or Render to run the application locally. You do **not** need Supabase for the default local setup.

---

## Contents

1. [Technology and project structure](#1-technology-and-project-structure)
2. [Part A — Local installation and running](#part-a--local-installation-and-running)
   - [Requirements](#a1-requirements)
   - [Download the project](#a2-download-the-project)
   - [Configure the local backend](#a3-configure-the-local-backend)
   - [Install backend packages](#a4-install-backend-packages)
   - [Start the backend](#a5-start-the-backend)
   - [Configure and start the frontend](#a6-configure-and-start-the-frontend)
   - [Local demo accounts](#a7-local-demo-accounts)
   - [Stop and restart](#a8-stop-and-restart-the-application)
3. [Part B — Online production deployment](#part-b--online-production-deployment)
   - [Prepare GitHub](#b1-prepare-github)
   - [Create the Supabase database](#b2-create-the-supabase-database)
   - [Deploy the API to Render](#b3-deploy-the-api-to-render)
   - [Deploy the frontend to Vercel](#b4-deploy-the-frontend-to-vercel)
   - [Create the first production administrator](#b5-create-the-first-production-administrator)
   - [Production storage and privacy](#b6-production-storage-and-privacy)
4. [Environment variables explained](#4-environment-variables-explained)
5. [Testing before release](#5-testing-before-release)
6. [Troubleshooting](#6-troubleshooting)
7. [Important implementation and security notes](#7-important-implementation-and-security-notes)

---

## 1. Technology and project structure

| Area | Technology | Purpose |
|---|---|---|
| Frontend | React 19, Vite 7, React Router | Web interface |
| Backend | Python 3.12, FastAPI, Uvicorn | API and application logic |
| ORM | SQLAlchemy | Database access |
| Local database | SQLite | Simple local development database |
| Production database | PostgreSQL (Supabase) | Hosted production data |
| Frontend hosting | Vercel | Public web application |
| Backend hosting | Render | Public API |
| Realtime updates | Server-Sent Events | Live application updates |

Main folders and files:

```text
SMART-CAMPUS/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── database.py             # SQLite/PostgreSQL connection
│   ├── models.py               # SQLAlchemy database models
│   ├── migrations.py           # Additive schema updates
│   ├── seed.py                 # Local demo data and account setup
│   ├── routers/                # API route modules
│   ├── tests/                  # Backend tests
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Backend configuration template
├── frontend/
│   ├── src/                    # React source code
│   ├── package.json            # Frontend scripts and dependencies
│   ├── package-lock.json       # Locked npm dependency versions
│   ├── vercel.json             # Vercel SPA route rewrite
│   └── .env.example            # Frontend configuration template
├── render.yaml                 # Render service configuration
└── README.md
```

---

# Part A — Local installation and running

This part runs the frontend and backend on your computer. Keep the backend and frontend running in **two separate terminal windows**.

## A1. Requirements

Install the following before continuing:

1. **Python 3.12** — check with `py --version` on Windows or `python3 --version` on macOS/Linux.
2. **Node.js 20.19+ or 22.12+** — check with `node --version`.
3. **npm** — installed with Node.js; check with `npm --version`.
4. **Git** — check with `git --version`.
5. **Visual Studio Code** (recommended) or another code editor.
6. A modern browser such as Chrome or Edge.

You do not need to install PostgreSQL or create a Supabase project for the default local setup. The backend uses a local SQLite file automatically.

## A2. Download the project

### Option 1 — Clone with Git (recommended)

Open PowerShell or a terminal and run:

```powershell
git clone https://github.com/kotoorich/SMART-CAMPUS.git
cd SMART-CAMPUS
```

### Option 2 — Download ZIP

1. Open the [Smart Campus GitHub repository](https://github.com/kotoorich/SMART-CAMPUS).
2. Select **Code → Download ZIP**.
3. Extract the ZIP to a folder you can find easily, for example `C:\Projects\SMART-CAMPUS`.
4. Open that extracted folder in Visual Studio Code.
5. In VS Code, select **Terminal → New Terminal**.

Before running commands, make sure your terminal is at the project root. The root folder should contain both `backend` and `frontend`.

## A3. Configure the local backend

The backend has a local SQLite default. If you do not set `DATABASE_URL`, the database file is created at:

`backend/smart_campus.db`

Create your local environment file by copying the template.

**Windows PowerShell (from the project root):**

```powershell
Copy-Item backend/.env.example backend/.env
```

**macOS/Linux (from the project root):**

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` in your editor. For local development, keep these settings:

```dotenv
ENVIRONMENT=development
SEED_DEMO_DATA=true
APP_TIMEZONE=Africa/Accra
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

The example file already contains local demo account names and passwords. You can change them before the first start. The demo seed process updates these demo accounts on backend startup while demo seeding is enabled.

**Important:** `backend/.env` is a private local file. Do not upload it to GitHub. The repository ignores real `.env` files; commit only the safe `.env.example` template.

## A4. Install backend packages

Open **Terminal 1** (PowerShell on Windows):

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell says script execution is disabled, run this in the same terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

If the `py -3.12` command is not available, use the Python 3.12 installation command available on your computer, for example:

```powershell
python -m venv .venv
```

**macOS/Linux:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Wait until pip finishes installing the packages. Keep this terminal open.

## A5. Start the backend

Make sure you are inside the `backend` folder and that the virtual environment is active.

Run:

```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

You should see Uvicorn report that the application has started.

Open these addresses in your browser:

- API root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- Interactive API documentation: http://127.0.0.1:8000/docs

The health check should report a healthy database connection. Keep Terminal 1 running while you use the frontend.

### What happens on the first backend start?

The application creates the database tables and runs its additive schema migration routine. With `SEED_DEMO_DATA=true` in development, it also inserts the local demo academic structure and demo accounts. You do not need to run SQL manually for the normal local setup.

## A6. Configure and start the frontend

Open **Terminal 2**. Do not stop Terminal 1.

From the project root, copy the frontend environment template:

**Windows PowerShell:**

```powershell
Copy-Item frontend/.env.example frontend/.env
```

**macOS/Linux:**

```bash
cp frontend/.env.example frontend/.env
```

Open `frontend/.env` and confirm that it contains:

```dotenv
VITE_API_URL=http://localhost:8000
```

This tells the browser application to send API requests to your local FastAPI server.

Install frontend dependencies and start Vite:

```powershell
cd frontend
npm ci
npm run dev
```

If you are using macOS/Linux, the same commands apply.

Vite will display a local address. Open:

**http://localhost:5173**

You should now have:

| Component | Local address |
|---|---|
| Smart Campus frontend | http://localhost:5173 |
| FastAPI backend | http://127.0.0.1:8000 |
| API documentation | http://127.0.0.1:8000/docs |
| Backend health | http://127.0.0.1:8000/health |

Do not close either terminal while testing. The backend and frontend are separate processes; both must be running.

## A7. Local demo accounts

When local demo seeding is enabled, the default accounts in the example environment file are:

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@smartcampus.com` | `Admin@12345` |
| Lecturer | `faculty1@smartcampus.com` | `Lecturer@12345` |
| Student | `student@smartcampus.com` | `Student@12345` |

The demo student index number is `2024001`.

These are **development-only demonstration credentials**. They are not production credentials. Change them in `backend/.env` if you share your development environment, and never reuse them on a live deployment.

If you change the demo account settings after the backend has started, restart the backend. The demo seeding routine synchronizes the configured demo accounts on startup while `SEED_DEMO_DATA=true`.

## A8. Stop and restart the application

To stop either server, click its terminal and press:

`CTRL + C`

To start again:

1. Start the backend first from the `backend` folder with the virtual environment activated.
2. Start the frontend from the `frontend` folder in a second terminal.
3. Open http://localhost:5173.

### Reset the local demo database

If you want to remove all local development data and let the application recreate its demo database:

1. Stop the backend.
2. Back up anything you need.
3. Delete `backend/smart_campus.db`.
4. Start the backend again with `SEED_DEMO_DATA=true`.

This permanently deletes the data stored in that local SQLite database. Do not do this to a production database.

---

# Part B — Online production deployment

This part publishes the application on the internet. The production architecture is:

```text
Student / Lecturer / Administrator browser
                  |
                  v
        Vercel — React frontend
                  |
          HTTPS API requests
                  |
                  v
          Render — FastAPI API
                  |
          PostgreSQL connection
                  |
                  v
       Supabase — Production database
```

Local and production configuration are different:

| Setting | Local development | Online production |
|---|---|---|
| Frontend | Vite on localhost:5173 | Vercel domain |
| Backend | Uvicorn on localhost:8000 | Render service URL |
| Database | SQLite file | Supabase PostgreSQL |
| Frontend API URL | `http://localhost:8000` | Render HTTPS URL |
| Demo seeding | Enabled for local testing | Disabled |
| Secrets | Private local `.env` | Render environment settings |
| Browser camera/location | localhost is permitted | HTTPS is required |

## B1. Prepare GitHub

1. Sign in to GitHub.
2. Open [the Smart Campus repository](https://github.com/kotoorich/SMART-CAMPUS).
3. Confirm that the code you intend to deploy is committed to the `main` branch.
4. Confirm that the root of the repository contains `backend/`, `frontend/` and `render.yaml`.
5. Confirm that real secrets and local data are not committed.

If you make changes locally, commit and push them:

```bash
git status
git add .
git status
git commit -m "Describe the changes"
git push origin main
```

Before pushing, check that you are not staging `backend/.env`, `frontend/.env`, `.venv`, `node_modules`, `backend/smart_campus.db`, private attendance images or other secrets.

## B2. Create the Supabase database

1. Visit [Supabase](https://supabase.com/) and sign in.
2. Create a new project.
3. Choose a project name and a strong database password. Save the password securely.
4. Select a region suitable for your users and hosting services.
5. Wait for the database project to finish provisioning.
6. Open **Connect** or **Project Settings → Database → Connection string**.
7. Select **Session pooler**. This example uses the session-pooler host and port for this Supabase project.
8. Use this connection URI format:

```text
postgresql://postgres.glnarqrqwohdrejfqnij:YOUR_URL_ENCODED_DATABASE_PASSWORD@aws-1-eu-west-2.pooler.supabase.com:5432/postgres
```

9. Replace `YOUR_URL_ENCODED_DATABASE_PASSWORD` with the actual database password, URL-encoding reserved characters. For example, an `@` character in a password must be represented as `%40` inside the URI.
10. Paste the completed URI privately into Render's `DATABASE_URL` environment variable. Never put the completed URI in this README, GitHub, the frontend or a `VITE_...` variable.

**Security:** if the password you shared in this conversation is your real Supabase database password, rotate/change it in Supabase before using it. Treat a password shared in chat, screenshots or source control as exposed.

The backend uses SQLAlchemy, creates the application's tables and runs its additive migration routine during startup. For the normal first deployment, do not manually paste table-creation SQL into Supabase.

**Do not put the database URI in the frontend, in a public repository, or in a `VITE_...` variable.**

## B3. Create the backend web service manually in Render (no Blueprint)

**Use the Render dashboard for this deployment. Do not choose Blueprint.** Create a normal Web Service and enter the settings yourself.

1. Visit [Render](https://render.com/) and sign in.
2. Click **New + → Web Service**.
3. Choose **Build and deploy from a Git repository**.
4. Connect GitHub if Render requests access.
5. Select `kotoorich/SMART-CAMPUS` and click **Connect**.
6. Configure the service:

| Render setting | Value |
|---|---|
| Name | `smart-campus-api` |
| Runtime | `Python 3` |
| Branch | `main` |
| Region | Choose a region suitable for your users and database |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` (Advanced settings, if available) |
| Auto-Deploy | On, if you want pushes to `main` to deploy automatically |

7. Select your preferred Render plan. Check current pricing and free-instance limitations before choosing.
8. Open **Advanced** if environment variables can be entered before creation. Otherwise create the service, then open its **Environment** tab.
9. Add each environment variable in the next table. Do not upload a production `.env` file to GitHub.
10. Click **Create Web Service** (or **Save Changes**) and wait for the build.
11. Open **Logs** and check for build, database or startup errors.
12. When the service is live, copy its public URL, for example `https://smart-campus-api.onrender.com`.

### Add the production environment variables in Render

In the service dashboard, open **Environment → Add Environment Variable** and enter:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.6` |
| `ENVIRONMENT` | `production` |
| `APP_TIMEZONE` | `Africa/Accra` |
| `INSTITUTION_NAME` | `Smart Campus` |
| `SEED_DEMO_DATA` | `false` |
| `DATABASE_URL` | Your completed Supabase Session Pooler URI from section B2 |
| `JWT_SECRET_KEY` | A newly generated long, random private signing secret |
| `CORS_ORIGINS` | Your exact Vercel origin, e.g. `https://your-project.vercel.app` |
| `BOOTSTRAP_ADMIN_NAME` | Name of the first production administrator |
| `BOOTSTRAP_ADMIN_EMAIL` | Email address of the first production administrator |
| `BOOTSTRAP_ADMIN_PASSWORD` | A new, strong, unique administrator password |
| `ATTENDANCE_GPS_RADIUS_METERS` | `50` (metres; confirm institutional policy) |
| `ATTENDANCE_GPS_ACCURACY_CEILING` | `500` (metres; validate with real devices) |
| `ATTENDANCE_GPS_SESSION_ACCURACY_CEILING` | `500` (metres; validate with real devices) |

**Important:**
- `DATABASE_URL` must be the full PostgreSQL URI from Supabase, not a SQLite path.
- Do not add quotation marks around values in the Render dashboard.
- Keep `SEED_DEMO_DATA=false`; production must not be populated with local demo accounts.
- The backend reads the three `BOOTSTRAP_ADMIN_...` variables and creates the administrator only if that email does not already exist.
- Generate a unique JWT secret. Do not reuse your database password or administrator password.
- Save environment changes and allow Render to restart/redeploy the service.

### Verify the Render API before deploying the frontend

Open these URLs using your actual Render hostname:
- `https://YOUR-RENDER-SERVICE.onrender.com/`
- `https://YOUR-RENDER-SERVICE.onrender.com/health`
- `https://YOUR-RENDER-SERVICE.onrender.com/docs`

The health endpoint should report a healthy database connection. If it reports `"database": false` or `"status": "degraded"`, inspect the Render logs and check the Supabase URI, password encoding, host, port and database password.
## B4. Deploy the frontend to Vercel

1. Visit [Vercel](https://vercel.com/) and sign in.
2. Select **Add New → Project**.
3. Import the `kotoorich/SMART-CAMPUS` GitHub repository.
4. In project configuration, set **Root Directory** to `frontend`.
5. Select **Vite** as the framework preset if Vercel does not detect it automatically.
6. Set the build command to `npm run build`.
7. Set the output directory to `dist`.
8. Open **Environment Variables** and add:

| Name | Value |
|---|---|
| `VITE_API_URL` | Your Render API URL, e.g. `https://smart-campus-api.onrender.com` |

9. Make sure the variable is available to the Production environment (and Preview if you intend to test preview deployments).
10. Deploy the project.
11. Wait for the deployment to finish and open the Vercel domain.

The frontend reads `VITE_API_URL` at build time. If you change it, trigger a new Vercel deployment. Do not add a trailing slash to the API URL.

The repository's `frontend/vercel.json` supplies the single-page application rewrite needed for direct navigation and page refreshes on nested frontend routes.

## B5. Connect Vercel and Render, then create the first administrator

The frontend and backend must allow each other to communicate.

1. Copy the exact Vercel production origin, for example `https://smart-campus.vercel.app`.
2. Open the Render service → **Environment**.
3. Set `CORS_ORIGINS` to that exact origin. Do not include a path such as `/login`.
4. If you have multiple trusted frontend origins, separate them with commas.
5. Save the environment changes and redeploy/restart the Render service.
6. In Render, confirm that `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are configured.
7. The backend creates the initial administrator account if that email does not already exist.
8. Open the Vercel application and sign in using that administrator email and password.
9. Change the initial password through the application's supported account/security workflow, if available, and store it securely.

If the bootstrap email already exists in the database, changing the environment variable does not automatically reset that existing account's password. Use the application's password-management process or a controlled administrative recovery procedure.

## B6. Production storage and privacy

**Attendance image storage must be addressed before relying on production selfie retention.**

The backend stores private attendance selfies under its local private-upload directory. A standard Render web service filesystem is ephemeral, so files can be lost when the service is redeployed or restarted.

Before using the platform for real attendance records, choose and test a durable private storage approach:

- Attach a Render persistent disk and mount it at the exact path used by the backend's private upload storage; or
- Implement and test private Supabase Storage/object storage, including access controls and authorized image retrieval.

Do not assume that a normal Render deployment permanently retains uploaded selfies. Confirm the actual configured storage path and test upload, retrieval, access permissions and retention after a redeployment.

Student identity details, Ghana Card-derived data, registration selfies, attendance selfies and location information are sensitive personal data. Before institutional use, establish an appropriate privacy notice, lawful collection basis, access controls, retention/deletion schedule, backup process and incident response procedure.

---

## 4. Environment variables explained

There are separate environment files and settings for local development and production.

### Local files

| File | Purpose |
|---|---|
| `backend/.env` | Local backend configuration and demo account credentials |
| `frontend/.env` | Local frontend API address |

Create them from the committed example templates. Never commit the real files.

### Backend variables

| Variable | Meaning |
|---|---|
| `ENVIRONMENT` | Use `development` locally and `production` on Render |
| `SEED_DEMO_DATA` | Enables local demo data; must be `false` in production |
| `DATABASE_URL` | Optional locally; if omitted, SQLite is used. Required on Render for Supabase PostgreSQL |
| `JWT_SECRET_KEY` | Secret used to sign login tokens. A local key is generated if not configured; must be configured in production |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |
| `APP_TIMEZONE` | Application timezone; this project uses `Africa/Accra` |
| `BOOTSTRAP_ADMIN_NAME` | Initial production administrator's name |
| `BOOTSTRAP_ADMIN_EMAIL` | Initial production administrator's email |
| `BOOTSTRAP_ADMIN_PASSWORD` | Initial production administrator's password |
| `ATTENDANCE_GPS_RADIUS_METERS` | Geofence radius in metres |
| `ATTENDANCE_GPS_ACCURACY_CEILING` | Maximum accepted reported GPS accuracy for student location |
| `ATTENDANCE_GPS_SESSION_ACCURACY_CEILING` | Maximum accepted reported GPS accuracy when opening a session |
| `DB_SSLMODE` | Optional PostgreSQL SSL mode override; remote connections default to `require` |

### Local demo account variables

The backend example file includes:

- `DEMO_ADMIN_NAME`, `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD`
- `DEMO_FACULTY_NAME`, `DEMO_FACULTY_EMAIL`, `DEMO_FACULTY_PASSWORD`
- `DEMO_STUDENT_NAME`, `DEMO_STUDENT_EMAIL`, `DEMO_STUDENT_PASSWORD`
- `DEMO_STUDENT_INDEX_NUMBER`
- `DEMO_DEPARTMENT`

These variables are for local development only. Production uses the bootstrap administrator variables and must not seed demo accounts.

### Frontend variable

| Variable | Local value | Production value |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Render API HTTPS URL |

Anything prefixed with `VITE_` is embedded in the browser build and must be treated as public. Never put passwords, JWT secrets, database credentials or private API keys in frontend environment variables.

---

## 5. Testing before release

Run these checks before pushing changes or releasing a new version.

### Backend checks

From the project root:

```bash
cd backend
python -m compileall -q .
pytest -q
```

If tests require optional test packages not included in `requirements.txt`, install the test dependencies documented by the project before interpreting a missing-package error as an application failure.

### Frontend checks

Open a terminal at the project root:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

A successful build does not prove that every workflow works. Test the application with separate student, lecturer and administrator accounts.

### Recommended end-to-end checklist

- [ ] Backend starts and `/health` reports a healthy database.
- [ ] Frontend loads and can communicate with the backend.
- [ ] Administrator can sign in and access administrative oversight.
- [ ] Lecturer can sign in and create/manage their academic courses/classes.
- [ ] Lecturer can open and close an attendance session and display its QR code.
- [ ] Student can sign up with the required information and sign in after approval.
- [ ] Student can register for the correct course using the lecturer's registration process.
- [ ] Student can scan the lecturer's attendance QR code.
- [ ] Student can grant camera and location permission and submit the attendance selfie/location.
- [ ] Lecturer can review attendance records and timestamps.
- [ ] Administrator can review institution-wide activity and attendance records.
- [ ] Refreshing a nested page does not produce a Vercel 404.
- [ ] Mobile navigation and page navigation work on a real phone.
- [ ] Private images remain retrievable after a backend redeployment (once durable storage is configured).

---

## 6. Troubleshooting

### A. Frontend displays “Failed to fetch”

1. Check that the backend is running.
2. Open the backend `/health` URL directly.
3. Confirm `VITE_API_URL` points to the correct API host.
4. For local development, it should be `http://localhost:8000`.
5. For production, it should be the Render HTTPS service URL.
6. Confirm the Render `CORS_ORIGINS` value exactly matches the Vercel origin.
7. Restart the backend after changing CORS.
8. Redeploy the frontend after changing `VITE_API_URL`.

### B. Backend cannot connect to Supabase

1. Confirm the Supabase project is active.
2. Re-copy the database connection URI.
3. Check that the database password is correct and special characters are URL-encoded.
4. Use a suitable Supabase pooler connection if the host cannot reach the direct database endpoint.
5. Confirm Render's `DATABASE_URL` contains the production database URI, not a local SQLite path.
6. Review Render logs for the exact connection error.

### C. Login returns 401 or 403

- Check the email and password.
- Make sure the selected role matches the account role.
- A student or lecturer account may require administrator approval before login.
- Confirm that you are using local demo credentials only on a local database.
- Confirm the production administrator was bootstrapped successfully.
- If the token secret was changed, sign out and sign in again.

### D. Camera or GPS permission is unavailable

- Use HTTPS for the deployed website. Browsers normally allow camera and location APIs on localhost during development.
- Allow camera and location permissions in the browser.
- Enable Location Services on the phone and allow precise location if available.
- Try outdoors or near a window if the phone reports poor GPS accuracy.
- Check that the lecturer's attendance session has a valid location and is still open.
- A GPS accuracy threshold is not the same as the geofence radius. Increasing the accuracy ceiling does not make a student farther away from the classroom eligible to attend.

### E. Vercel refreshes a nested page to a 404

- Confirm that `frontend/vercel.json` is committed.
- Confirm that Vercel's Root Directory is `frontend`.
- Redeploy after correcting the project settings.

### F. Attendance selfies disappear after redeployment

This usually indicates that the backend is using an ephemeral filesystem. Configure persistent disk or durable private object storage as described in [Production storage and privacy](#b6-production-storage-and-privacy).

### G. PowerShell does not recognize `uvicorn`

- Confirm that the backend virtual environment is activated.
- Run `pip install -r requirements.txt` again if necessary.
- You can also start it with `python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`.

### H. Port 8000 or 5173 is already in use

Stop the other process using that port, or choose another port. If you change the backend port, also update `VITE_API_URL` in `frontend/.env` to match and restart Vite.

---

## 7. Important implementation and security notes

1. **Never commit secrets.** Keep real `.env` files, database passwords, JWT secrets, private uploads and production credentials out of Git.
2. **Do not seed demo data in production.** Keep `SEED_DEMO_DATA=false` and `ENVIRONMENT=production`.
3. **Use HTTPS online.** Camera and location permissions require a secure browser context.
4. **Protect personal data.** Restrict access to student identity information, selfies and location records. Define retention and deletion policies before institutional deployment.
5. **Back up production data.** Configure database backups and test restoration.
6. **Persist private uploads.** Render's ordinary ephemeral filesystem is not durable storage.
7. **Test on real devices.** GPS accuracy varies between phones, buildings, network conditions and operating systems.
8. **Validate institutional workflows.** Confirm academic structure, approval settings, course registration, attendance rules and user permissions with the institution before going live.
9. **Do not overstate identity assurance.** The current attendance process uses a lecturer-issued QR/session, a selfie and browser geolocation. This alone does not constitute certified facial-recognition/liveness verification or official Ghana Card/NIA verification.
10. **Keep local and production databases separate.** Deleting or resetting `backend/smart_campus.db` affects only the local SQLite database. Never use local reset instructions against the production Supabase database.

---

## Useful links

- [GitHub repository](https://github.com/kotoorich/SMART-CAMPUS)
- [Supabase](https://supabase.com/)
- [Render](https://render.com/)
- [Vercel](https://vercel.com/)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Vite documentation](https://vite.dev/)

