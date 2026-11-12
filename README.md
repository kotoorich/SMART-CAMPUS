# Smart Campus

Smart Campus is a UCC-focused academic and attendance management application.

- **Frontend:** React, Vite and React Router
- **Backend:** FastAPI, SQLAlchemy and Uvicorn
- **Database:** SQLite for local development; PostgreSQL (Supabase) when hosted
- **Hosting:** Vercel (frontend) and Render (API)

Lecturers create and manage their own courses, class details and attendance sessions. Students register for courses and mark attendance using the lecturer's QR code, a live selfie and location verification. Administrators oversee users, academic activity, attendance and institution settings.

## 1. Run locally

Install Python 3.12, Node.js 20.19+ (or 22.12+) and Git.

### Backend

From the project root:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` and activate again.

On macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, and `cp .env.example .env` instead.

The local backend uses SQLite automatically. It creates the database and tables on startup. The local `.env.example` enables sample data for development only.

### Frontend

Open a second terminal at the project root:

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

### Local sample accounts

| Role | Email | Password |
|---|---|---|
| Administrator | admin@smartcampus.com | Admin@12345 |
| Lecturer | faculty1@smartcampus.com | Lecturer@12345 |
| Student | student@smartcampus.com | Student@12345 |

These accounts are for a local development database only. Do not use these passwords for a real institution.

## 2. Deploy the backend to Render

Use a normal **Web Service**. This project does not require a Render Blueprint.

1. Push the latest code to the `main` branch of this repository.
2. In Render, select **New + → Web Service** and connect `kotoorich/SMART-CAMPUS`.
3. Select branch `main`, runtime **Python 3**, and set the **Root Directory** to `backend`. The `backend/.python-version` file pins the service to Python 3.12.6.
4. Use these commands:

| Render field | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

5. If you want registration and attendance selfies to remain available after a Render redeploy or restart, add a **Persistent Disk** to the service (Render → service → Disks) and set its mount path to `/var/data`. The app stores private uploaded photos under that path. Without a persistent disk, the API can still run, but uploaded photos on Render's temporary filesystem may be lost after a restart or deploy.
6. Create a PostgreSQL project in Supabase. In Supabase, copy the **Session pooler** connection string. Use the URI with the PostgreSQL scheme and port shown by Supabase (normally port `5432` for Session pooler). URL-encode special characters in the database password.
7. In Render → **Environment**, add only these five variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | The complete Supabase Session pooler connection string |
| `JWT_SECRET_KEY` | A newly generated, long random secret used only for signing login tokens |
| `CORS_ORIGINS` | The exact deployed Vercel origin, e.g. `https://your-app.vercel.app` |
| `BOOTSTRAP_ADMIN_EMAIL` | The email address for your first administrator |
| `BOOTSTRAP_ADMIN_PASSWORD` | A strong, unique password for that administrator |

Do not add quotation marks around values. Keep these values private. Never put the database URL or JWT secret in the frontend or GitHub.

Render automatically identifies its hosted environment. You do **not** need to add separate environment variables for the institution name, timezone, attendance radius, GPS accuracy, attendance duration, student approval policy or course registration policy. Those settings are handled by the application. The administrator can configure the supported institution policies from the app's Settings pages.

Paid lecturer registration additionally requires `PAYSTACK_SECRET_KEY` and `PAYSTACK_CALLBACK_URL` in Render. Set the callback URL to `https://YOUR-VERCEL-DOMAIN/lecturer/payment/callback`. These two variables are only required if paid lecturer registration is enabled; free lecturer registration does not require Paystack. Keep the Paystack secret on the backend only.\n\nThe first administrator is created from the bootstrap email and password when the database is first initialized. Once that account exists, changing the bootstrap variables will not reset its password; use the in-app account controls.

Demo seeding is disabled on Render, including when `SEED_DEMO_DATA=true` is accidentally present. The sample users and sample academic records are for local development only. Never connect a public demo database containing real student records.

After the service deploys, open:

- `https://YOUR-RENDER-SERVICE.onrender.com/health`
- `https://YOUR-RENDER-SERVICE.onrender.com/docs`

The health endpoint should return `"status": "ok"` and `"database": true`.

## 3. Deploy the frontend to Vercel

1. In Vercel, import `kotoorich/SMART-CAMPUS`.
2. Set **Root Directory** to `frontend`.
3. Use the default Vite build settings:

| Vercel field | Value |
|---|---|
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | `npm ci` |

4. Add one environment variable:

| Variable | Value |
|---|---|
| `VITE_API_URL` | Your Render API URL, e.g. `https://your-service.onrender.com` |

5. Deploy or redeploy the Vercel project.

Make sure the Render `CORS_ORIGINS` value exactly matches the Vercel website origin, with no trailing slash. If the Vercel domain changes, update the Render value and redeploy the API.

## 4. App configuration

Use the administrator Settings screens for institution policies and operational settings. Do not create extra Render variables for settings that the app already manages.

The backend uses Ghana time (`Africa/Accra`). Attendance requires a secure HTTPS website in production so the browser can access camera and location permissions. Localhost is also permitted by modern browsers during development.

## 5. Run checks before release

Backend tests use an isolated temporary SQLite database:

```bash
cd backend
python -m pip install pytest
python -m pytest -q
```

Frontend production build:

```bash
cd frontend
npm ci
npm run build
```

Frontend lint:

```bash
npm run lint
```

A successful build or test run does not replace checking the deployed service. After deployment, test login for each role and complete the main student, lecturer and administrator workflows using test accounts.

## 6. Troubleshooting

**Render reports `ModuleNotFoundError: No module named 'psycopg'`**

The backend explicitly uses the installed `psycopg2-binary` driver for PostgreSQL URLs. Confirm that the latest `main` commit has deployed and that the build command installs `backend/requirements.txt`.

**The API starts but the health check says the database is unavailable**

Check that `DATABASE_URL` is the complete Supabase Session pooler URI, the database password is URL-encoded, and the Supabase project is active. Review the first database error in Render logs.

**The browser reports a CORS error**

Set `CORS_ORIGINS` in Render to the exact Vercel origin, save it and redeploy the backend. Set `VITE_API_URL` in Vercel to the Render API base URL and redeploy the frontend.

**Login fails after deployment**

Confirm that the first administrator bootstrap variables were set before the database's first initialization. Check that the account exists and use the correct role at login. The bootstrap variables do not overwrite an existing administrator's password.

**Camera or location access is blocked**

Use the deployed HTTPS Vercel address, allow camera and precise location access in the browser, and retry. Attendance location verification depends on the device's location accuracy.

## 7. Security notes

- Never commit `.env` files, database passwords, JWT secrets, real student records or private attendance photos.
- Use a separate production database; do not deploy the local sample dataset to an institution's live database.
- Use unique passwords for the administrator, database and JWT signing secret.
- If a secret has been shared publicly or committed, rotate it before production use.
- Attendance photographs are private application data and must only be accessed through authenticated application routes.
