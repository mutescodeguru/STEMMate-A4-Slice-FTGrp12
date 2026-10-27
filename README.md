# STEMMate Namibia — A4 Vertical Slice

**Course:** SDN621S — Software Design
**Assessment:** A4 — Architecture, Vertical Slice, Tests, Evaluation and Redesign

## Project purpose

This project develops a working vertical slice of STEMMate Namibia, focused on creating and saving STEM practical session plans.

## Technology stack

- Python
- Flask
- SQLite
- pytest

## Setup

1. Install Python 3.13 or a compatible version.
2. Create and activate a Python virtual environment.
3. Install dependencies using `python -m pip install -r requirements.txt`.
4. Follow the project's setup instructions as they are documented.

## Status

Initial repository setup. Requirements, architecture, implementation and testing documentation will be added as the team develops the vertical slice.

## Data and privacy

Use synthetic demonstration data only. Do not commit secrets, real learner data, or local database files.


Run the backend
1. python -m venv .venv then .venv\Scripts\activate.bat (Windows)
2. pip install -r requirements.txt
3. flask --app stemmate init-db
4. flask --app stemmate create-user <name> (you will be asked for a password)
5. python run.py then open http://127.0.0.1:5000/health
6. Tests: pytest
Environment variables (all optional in development)
Variable	Purpose
STEMMATE_SECRET_KEY	Signs session cookies. Set a long random value outside development.
STEMMATE_DATABASE	Path to the SQLite file (default instance/stemmate.db).
STEMMATE_SYNC_KEY	Shared key for the central store (Phase 5).
STEMMATE_STORAGE_LIMIT_BYTES	Storage limit for QR-01 tests (default 50 MB).

Never commit .env, *.db or real passwords. All data is synthetic (PR-01).





## API summary (Phases 1-4)

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | /api/auth/login | 200 | 401, 422 |
| POST | /api/auth/logout | 204 | 401 |
| GET | /api/auth/me | 200 | 401 |
| PUT | /api/plans/{id} | 200 | 401, 404, 409, 422, 507 |
| POST | /api/plans/{id}/complete | 200 | 401, 404, 409, 422 |
| GET | /api/plans | 200 | 401 |
| GET | /api/plans/{id} | 200 | 401, 404 |
| GET | /api/drafts/latest | 200 or 204 | 401 |
| GET | /api/materials | 200 | 401 |
| GET | /api/storage | 200 | 401 |

Errors always look like `{"error": {"code", "message", "fields?"}}`.
Seed the materials with `flask --app stemmate seed-materials`.
Example requests are in the `examples/` folder.
