# COSMIC PULSE deployment guide

## Current release status

The project is prepared for a Vercel frontend and Render FastAPI backend, but it is **not deployed**. The intended GitHub repository is `https://github.com/Amikumarsingh/Cosmic-Pulse`; the local `main` branch is being published. No hosting services, public URLs, or automatic deployments are configured by this initial GitHub release.

## Architecture

- **Frontend:** Vercel static site, built from `frontend/`; `frontend/vercel.json` sends direct route requests back to the React app.
- **Backend:** Render Python web service from `backend/`, started with Uvicorn and health-checked at `/live`.
- **Data:** The backend downloads the genuine SPHEREx FITS product from IRSA on demand. No FITS file needs to be uploaded to the host. A 200 MiB download limit and the trusted IRSA host restriction remain in place.
- **Cache:** `FITS_CACHE_DIR` defaults to the system temporary directory. Render Free has an ephemeral filesystem: cached FITS and analysis results are lost on restart, redeploy, or spin-down and must be fetched/recomputed again.

The configuration pins Render to Python 3.13.7, matching the local Python 3.13 environment and the installed scientific stack. `render.yaml` selects Render Free for a student prototype. Render documents that a free web service spins down after 15 minutes without traffic, commonly takes about one minute to wake, has ephemeral storage, and receives 750 free instance-hours per workspace per month. Bandwidth/build limits can suspend service or prevent builds if exceeded. This is a demo tier, not a production availability commitment. See [Render Free instance limits](https://render.com/docs/free).

Vercel lists Hobby at $0/month with usage limits; verify account eligibility and current limits before release. See [Vercel pricing](https://vercel.com/pricing). Provider pricing and limits can change.

## Local development

Use Python 3.13 and Node 22.12 or newer (Vite 8 requirement). From the repository root in PowerShell:

```powershell
Copy-Item .env.example frontend\.env.local
Copy-Item backend\.env.example backend\.env

cd frontend
npm ci
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API and frontend in separate terminals:

```powershell
cd backend
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`. Backend environment values are loaded from `backend/.env`; Vite loads `frontend/.env.local`.

## First deployment (requires account/repository access)

1. Import `Amikumarsingh/Cosmic-Pulse` into Vercel. Set **Root Directory** to `frontend`, keep build command `npm run build` and output directory `dist`, and use `main` as the production branch.
2. Set up the backend in Render by creating a Blueprint from the same repository and selecting the root `render.yaml`. The service root is `backend`, the start command binds to Render's `$PORT`, and the liveness check is `/live`. The Blueprint requests Python 3.13.7 and enables automatic deploys from the connected branch.
3. Set Vercel's `VITE_API_URL` build variable to the actual Render API HTTPS URL for Production and Preview. Vite embeds this value at build time.
4. After Vercel assigns the actual frontend URL, set Render's `CORS_ORIGINS` to that exact HTTPS origin (plus local origins only if desired). Do not leave a placeholder origin in production; redeploy the backend after changing it.
5. Verify the production branch is `main` and automatic deployment from the GitHub branch is enabled in both providers.
6. Test the public endpoints and user flows in the production-test checklist before sharing the URL. This guide is not evidence that a deployment or public URL exists.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `APP_ENV` | Render runtime; `backend/.env` locally | `production` disables interactive API docs; local example enables them. |
| `VITE_API_URL` | Vercel build environment; `frontend/.env.local` locally | Absolute HTTPS base URL for the FastAPI service; required in production builds. |
| `CORS_ORIGINS` | Render runtime; `backend/.env` locally | Comma-separated exact browser origins allowed by API CORS. Include the assigned frontend origin. |
| `FITS_CACHE_DIR` | Render runtime; optional locally | Writable parent directory for disposable FITS and analysis caches. Render Free storage is ephemeral. |
| `PYTHON_VERSION` | Render Blueprint | Pinned to `3.13.7` in `render.yaml`. |

No API key or credential is needed for the current public IRSA product. Do not add secrets unless a future integration requires them.

## Automatic update workflow

After GitHub, Vercel, and Render are connected:

```powershell
git checkout main
git pull --ff-only
# edit and test
git add <changed-files>
git commit -m "Describe the change"
git push origin main
```

Vercel rebuilds the frontend and Render rebuilds the backend on pushes to the connected production branch. For review deployments, push a feature branch and use the providers' preview deployment workflow; merge only after testing.

## Production verification checklist

Once deployed, verify rather than infer:

- Frontend home and `/explorer`, `/time-machine`, `/lab`, `/capsules`, and `/about` load over HTTPS, including direct refresh.
- Backend `GET /live` and `GET /health` return successfully; note `/health` also checks IRSA availability.
- Production API docs and OpenAPI schema are disabled; local development retains `/docs`.
- Browser CORS allows the exact Vercel origin.
- Explorer searches and displays the real observation `2025W17_4B_0001_1`.
- FITS preview, image-info, and `/api/fits/inspect` work; inspection reports seven HDUs.
- Discovery Lab runs full-resolution analysis and distinguishes the exact qualifying count from the returned catalogue cap of 200.
- Time Machine reports that only one compatible real epoch is available.
- IMAGE unit stays `MJy / sr`; unsupported uncertainties remain unavailable; WCS/SIP and independent astrometric calibration limitations remain visible.
- Browser console and Render logs contain no uncaught application failures or internal filesystem paths.
- Record first-request delay separately. Render Free may require a spin-up, and the FITS preview/analysis can then incur an IRSA download. Do not describe the delay until timed against the live service.

## Troubleshooting

- **Production UI says API is not configured:** Set `VITE_API_URL` in the Vercel project and redeploy; Vite variables are embedded at build time.
- **Browser reports CORS failure:** Set Render `CORS_ORIGINS` to the exact scheme/host of the deployed UI, save, and redeploy the API.
- **API is slow after inactivity:** Render Free may have spun down. Wait for the service to start, then retry. `/live` is a liveness probe; `/health` additionally probes IRSA.
- **Preview/analysis is slow or fails:** The FITS product is fetched from IRSA on demand. Inspect Render logs and retry after checking IRSA reachability. Free instance restarts discard the download and computed cache.
- **Build fails after a dependency update:** Confirm Python 3.13.7 is selected, then review Render's dependency-install logs. Locally run `python -m pytest -m "not live" -q` and `npm run build`.
- **Direct page refresh returns 404:** Confirm Vercel's project root is `frontend` and `frontend/vercel.json` is present.
- **Auto-deploy does not run:** Verify both providers are linked to the intended GitHub repository and production branch, then check provider deploy logs and repository integration permissions.
