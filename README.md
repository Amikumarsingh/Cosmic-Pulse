# COSMIC PULSE

> The universe is not a picture. It's an unfolding story.

COSMIC PULSE is a research prototype for exploring genuine NASA/IPAC SPHEREx DR1 observations. It includes an IRSA-connected Explorer, FITS image inspection, full-resolution source detection and aperture photometry, and a Time Machine view that honestly reports when a compatible second epoch is unavailable.

The current analysis uses observation `2025W17_4B_0001_1`. Measurements are not confirmed discoveries or transients. The IMAGE unit is `MJy / sr`; photometric uncertainty is not reported because VARIANCE semantics have not been verified. Product astrometry has not been independently calibrated. Evidence Capsules are static example records, not saved analysis results.

## Project layout

- `frontend/` — React, TypeScript, Vite, Tailwind CSS
- `backend/` — FastAPI, NumPy, SciPy, Astropy, Matplotlib, Pillow

## Local development

Install dependencies once:

```powershell
cd frontend
npm ci
cd ..\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

In separate terminals:

```powershell
cd backend
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

The UI runs at `http://localhost:5173`; the API is at `http://localhost:8000`. See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for environment setup, production hosting, and the Git update workflow.

## Verification

```powershell
cd backend
python -m pytest -m "not live" -q
cd ..\frontend
npm run build
```
