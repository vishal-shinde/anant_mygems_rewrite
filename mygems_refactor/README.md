# MYGEMS Refactor

This folder contains a clean PySide6-based refactor of the original desktop ERP project.

## Structure

- `app/config.py` - environment-based database configuration
- `app/db/connection.py` - PostgreSQL connection handling
- `app/repositories/` - database access layer
- `app/services/` - business logic
- `app/ui/` - Qt windows and widgets
- `app/models/` - domain models

## Setup

```bash
cd mygems_refactor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Notes

- The original app code is left untouched.
- This scaffold keeps the refactor isolated in one folder.
- The database credentials are still configurable through environment variables.
