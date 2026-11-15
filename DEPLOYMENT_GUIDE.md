# COSMIC PULSE deployment guide

## Current release status

The GitHub repository `https://github.com/Amikumarsingh/Cosmic-Pulse` is connected to Vercel and Render on `main`. The deployment configuration at commit `4a70ae3` was verified live on both providers. The public URLs are `https://cosmic-pulse-nu.vercel.app` and `https://cosmic-pulse-api.onrender.com`.

Production checks passed: the frontend homepage and `/explorer`, `/time-machine`, `/lab`, `/capsules`, and `/about` direct routes return the SPA; a browser-origin request to the API returns the genuine observation `2025W17_4B_0001_1`; FITS inspection reports seven HDUs and IMAGE `BUNIT` `MJy / sr`; the preview returns PNG; source analysis reports 4,364 qualifying detections with 200 returned and `sources_capped=true`; Time Machine reports one epoch and `comparison_possible=false`. Render CORS allows the deployed frontend origin. IRSA TAP was unavailable (`HTTP_502`), so the observation search used the product metadata fallback. The Render Free dashboard warns that an idle service may spin down and delay requests by 50 seconds or more; a cold-start duration was not measured during this verification. A new deployment is required after environment/configuration changes.

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

## Provider configuration

- **Vercel:** repository `Amikumarsingh/Cosmic-Pulse`, root directory `frontend`, production branch `main`, output directory `dist`, with automatic production deployments from `main`.
- **Render:** Blueprint from the same repository using the root `render.yaml`; service root is `backend`, liveness check is `/live`, Python is pinned to 3.13.7, and automatic deployments from `main` are enabled.
- **Vercel production environment:** `VITE_API_URL=https://cosmic-pulse-api.onrender.com`. Vite embeds this value at build time; redeploy after changing it.
- **Render CORS:** `CORS_ORIGINS` in `render.yaml` includes `https://cosmic-pulse-nu.vercel.app` and local development origins. Keep the production frontend origin synchronized with the deployed Vercel domain and redeploy after changes.
- Confirm each provider's latest deployment is healthy, then test the production checklist before sharing the application.

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
