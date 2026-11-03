# QueueLess BD

**A Smart Queue Management System**

QueueLess BD is a full-stack queue management application designed to simplify customer flow and reduce unnecessary waiting. It provides a digital token system, real-time queue monitoring, service counter management, and estimated waiting times.

## Features

- **Digital Token Booking** – Generate queue tokens for customers.
- **Live Queue Updates** – Track queue activity in real time using WebSockets.
- **Multiple Service Counters** – Manage different services and counters from one system.
- **Staff Dashboard** – Call the next customer, recall tokens, skip customers, and complete services.
- **Public Display Screen** – Show currently serving and waiting tokens.
- **Waiting Time Estimation** – Estimate waiting times using recent completed service durations, with a configured fallback.
- **Voice Announcements** – Browser-based Bangla and English announcements, depending on device and browser support.
- **Demo Data** – Initial organization, services, and counters are created automatically.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| Real-time Updates | WebSockets |
| Voice Announcements | Browser Speech Synthesis API |

## Project Structure

```text
QueueLess-BD/
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── backend/
│   ├── app/
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

## Getting Started

### Requirements

Install the following before running the project:

- Python 3.10 or later
- Node.js 18 or later
- npm

### 1. Clone the Repository

```bash
git clone https://github.com/sakibulkabir/QueueLess-BD.git
cd QueueLess-BD
```

### 2. Start the Backend

Open a terminal and run:

```powershell
cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file inside the `backend` folder if your configuration requires one.

Start the API server:

```powershell
py -3.12 -m uvicorn app.main:app --reload
```

Backend API documentation:

http://localhost:8000/docs

### 3. Start the Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the application:

http://localhost:5173

## Demo Configuration

The development admin key is:

```text
dev-admin-key-change-me
```

This is intended for local development only. Set a strong, private admin key before deploying the application.

## External Integrations

The core queue management features do not require third-party API credentials.

Optional integrations such as SMS notifications, WhatsApp messaging, payment processing, and cloud-based text-to-speech require their own provider accounts and configuration.

The SMS module currently contains a provider integration placeholder. Actual SMS delivery requires a configured gateway or provider.

## Current Limitations

- Waiting times are estimates and may change as queue activity changes.
- Browser voice availability depends on the device, browser, and installed voices.
- SMS delivery is not active without a working provider integration.
- SQLite is used for the current development setup.

## Production Considerations

QueueLess BD is currently an MVP intended for demonstration, testing, and further development. Before using it in a real-world environment, the following improvements are recommended:

- Implement secure authentication and role-based access control.
- Add audit logs and request rate limiting.
- Configure HTTPS and secure environment variables.
- Use PostgreSQL for persistent production data.
- Set up automated database backups and monitoring.
- Introduce a reliable background worker for scheduled notifications.
- Apply appropriate privacy and security measures before handling personal or patient information.

Queue priority and emergency decisions should always remain under the control of qualified staff. The system's waiting-time estimates should not be used for clinical decisions.

## Author

**Sakibul Kabir Risat**

GitHub: [@sakibulkabir](https://github.com/sakibulkabir)