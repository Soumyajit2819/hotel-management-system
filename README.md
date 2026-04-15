# Hotel Management System

Hotel management app built with FastAPI, Streamlit, and SQLAlchemy.

## Folder Layout

Everything is now grouped inside one replacement folder:

```text
hotel_management_system/
├── backend/
├── database/
├── frontend/
├── hotel.db
├── README.md
└── requirements.txt
```

## What is fixed

- Working backend endpoints for rooms, users, reservations, check-in/out, payments, food orders, feedback, and reports
- Three role-based UIs: `admin`, `receptionist`, and `guest`
- Guest self-registration and guest booking flow
- Persistent login event storage in the main database
- Optional MongoDB mirror for login events when `MONGODB_URL` is configured

## Default logins

- `admin / admin123`
- `receptionist / rec123`
- `guest / guest123`

## Run

From the `hotel_management_system` folder, install dependencies:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
cd backend
python main.py
```

Start the frontend:

```bash
cd frontend
streamlit run app.py
```

## Optional MongoDB

If you want login events copied into MongoDB too, set:

```bash
export MONGODB_URL="mongodb://localhost:27017"
export MONGODB_DB="hotel_hms"
```

If `MONGODB_URL` is not set, login data is still saved in the main app database.
