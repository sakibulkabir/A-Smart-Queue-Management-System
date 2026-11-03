import os
import asyncio

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Header,
    WebSocket,
    WebSocketDisconnect
)

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .database import Base, engine, get_db, SessionLocal
from .models import Organization, Service, Counter, Token
from .predictor import estimate_wait, average_service_minutes
from .notifications import send_sms


# ENVIRONMENT
load_dotenv()

Base.metadata.create_all(bind=engine)


# DATABASE MIGRATION
# Existing token data will be preserved.
def migrate_database():
    inspector = inspect(engine)

    if "tokens" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("tokens")
    }

    new_columns = {
        "estimated_call_at": "DATETIME",
        "confirmation_sms_sent_at": "DATETIME",
        "reminder_sent_at": "DATETIME"
    }

    with engine.begin() as connection:
        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE tokens ADD COLUMN "
                    f"{column_name} {column_type}"
                )


migrate_database()


app = FastAPI(
    title="QueueLess BD API",
    version="1.2"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"]
)


# WEBSOCKET CLIENTS
clients = []


# BACKGROUND REMINDER TASK
reminder_task = None


# REQUEST MODELS
class Booking(BaseModel):
    service_id: int
    counter_id: int
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = ""


class Complete(BaseModel):
    service_minutes: float | None = Field(
        default=None,
        ge=0.5,
        le=240
    )


# ADMIN AUTHENTICATION
def admin(
    x_admin_key: str | None = Header(default=None)
):
    if x_admin_key != os.getenv(
        "ADMIN_API_KEY",
        "dev-admin-key-change-me"
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key"
        )


# WEBSOCKET BROADCAST
async def broadcast(event):
    for ws in clients[:]:
        try:
            await ws.send_json(event)
        except Exception:
            if ws in clients:
                clients.remove(ws)


# SMS TIME FORMAT
def format_sms_time(value):
    if not value:
        return "Not available"

    # Database time is stored as UTC.
    utc_time = value.replace(tzinfo=ZoneInfo("UTC"))

    dhaka_time = utc_time.astimezone(
        ZoneInfo("Asia/Dhaka")
    )

    return dhaka_time.strftime("%I:%M %p")


# QUEUE ETA CALCULATION
def recalculate_queue_estimates(db, counter_id=None):
    now = datetime.utcnow()

    counter_query = db.query(Counter)

    if counter_id is not None:
        counter_query = counter_query.filter(
            Counter.id == counter_id
        )

    all_counters = counter_query.all()

    for counter in all_counters:

        queue_tokens = (
            db.query(Token)
            .filter(
                Token.counter_id == counter.id,
                Token.status.in_(["waiting", "serving"])
            )
            .order_by(Token.created_at.asc())
            .all()
        )

        serving_tokens = [
            token for token in queue_tokens
            if token.status == "serving"
        ]

        waiting_tokens = [
            token for token in queue_tokens
            if token.status == "waiting"
        ]

        cursor = now

        # If a patient is already being served,
        # estimate their remaining time using average service time.
        if serving_tokens:
            current = serving_tokens[0]

            current_service = db.get(
                Service, current.service_id
            )

            if current_service:
                cursor += timedelta(
                    minutes=average_service_minutes(
                        db, current_service
                    )
                )

        # Estimate each waiting patient's call time.
        for token in waiting_tokens:

            token.estimated_call_at = cursor

            service = db.get(Service, token.service_id)

            if service:
                duration = average_service_minutes(
                    db, service
                )
            else:
                duration = 8

            cursor += timedelta(minutes=duration)


# TOKEN RESPONSE
def payload(db, t):

    service = db.get(Service, t.service_id)
    counter = db.get(Counter, t.counter_id)

    ahead = db.query(Token).filter(
        Token.counter_id == t.counter_id,
        Token.status == "waiting",
        Token.created_at < t.created_at
    ).count()

    estimated_wait = 0

    if (
        t.status == "waiting"
        and t.estimated_call_at
    ):
        estimated_wait = max(
            0,
            round(
                (
                    t.estimated_call_at -
                    datetime.utcnow()
                ).total_seconds() / 60
            )
        )

    else:
        estimated_wait = estimate_wait(
            db,
            service,
            t.counter_id
        ) if service else 0

    return {
        "id": t.id,
        "token_number": t.token_number,
        "customer_name": t.customer_name,
        "phone": t.phone,
        "service_id": t.service_id,
        "service_name": service.name if service else "",
        "counter_id": t.counter_id,
        "counter_name": counter.name if counter else "",
        "status": t.status,
        "position": ahead + 1 if t.status == "waiting" else 0,
        "estimated_wait_minutes": estimated_wait,
        "estimated_call_at": (
            t.estimated_call_at.isoformat()
            if t.estimated_call_at else None
        ),
        "created_at": t.created_at.isoformat(),
        "call_count": t.call_count
    }


# DATABASE SEED
def seed():
    db = SessionLocal()

    try:
        organization = db.query(Organization).first()

        if not organization:
            organization = Organization(
                name="QueueLess Demo Hospital"
            )
            db.add(organization)
            db.flush()

        service1 = db.query(Service).filter(
            Service.organization_id == organization.id,
            Service.name == "General Consultation"
        ).first()

        if not service1:
            service1 = Service(
                organization_id=organization.id,
                name="General Consultation",
                average_minutes=8,
                active=True
            )
            db.add(service1)
            db.flush()
        else:
            service1.active = True

        service2 = db.query(Service).filter(
            Service.organization_id == organization.id,
            Service.name == "Diagnostic Collection"
        ).first()

        if not service2:
            service2 = Service(
                organization_id=organization.id,
                name="Diagnostic Collection",
                average_minutes=5,
                active=True
            )
            db.add(service2)
            db.flush()
        else:
            service2.active = True

        counter_data = [
            ("Counter 01", service1.id),
            ("Counter 02", service1.id),
            ("Counter 03", service2.id)
        ]

        for counter_name, service_id in counter_data:

            counter = db.query(Counter).filter(
                Counter.organization_id == organization.id,
                Counter.name == counter_name
            ).first()

            if not counter:
                counter = Counter(
                    organization_id=organization.id,
                    name=counter_name,
                    service_id=service_id,
                    active=True
                )
                db.add(counter)
            else:
                counter.service_id = service_id
                counter.active = True

        db.commit()

        print("QueueLess BD: Demo services and counters ready.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


seed()


# BACKGROUND REMINDER CHECKER
def process_reminders():
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        # Refresh estimated call times.
        recalculate_queue_estimates(db)

        waiting_tokens = db.query(Token).filter(
            Token.status == "waiting",
            Token.reminder_sent_at.is_(None),
            Token.estimated_call_at.isnot(None),
            Token.phone != ""
        ).all()

        for token in waiting_tokens:

            eta = token.estimated_call_at

            if not eta:
                continue

            # Send reminder when estimated call time
            # is within the next 10 minutes.
            # Do not send if estimated time has already passed.
            if now < eta <= now + timedelta(minutes=10):

                service = db.get(Service, token.service_id)
                counter = db.get(Counter, token.counter_id)

                eta_text = format_sms_time(eta)

                message = (
                    f"QueueLess BD Reminder: Your token "
                    f"{token.token_number} is expected to be "
                    f"called around {eta_text}. "
                    f"Service: {service.name if service else 'N/A'}. "
                    f"Counter: {counter.name if counter else 'N/A'}. "
                    f"Please be ready."
                )

                result = send_sms(token.phone, message)

                # Mark as sent only after provider confirms success.
                if result and result.get("sent") is True:
                    token.reminder_sent_at = datetime.utcnow()

        db.commit()

    except Exception as error:
        db.rollback()
        print("Reminder worker error:", error)

    finally:
        db.close()


async def reminder_worker():
    while True:
        try:
            await asyncio.to_thread(process_reminders)
        except Exception as error:
            print("Reminder worker error:", error)

        await asyncio.sleep(30)


@app.on_event("startup")
async def start_reminder_worker():
    global reminder_task
    reminder_task = asyncio.create_task(reminder_worker())


@app.on_event("shutdown")
async def stop_reminder_worker():
    global reminder_task

    if reminder_task:
        reminder_task.cancel()

        try:
            await reminder_task
        except asyncio.CancelledError:
            pass


# ROOT
@app.get("/")
def root():
    return {
        "name": "QueueLess BD API",
        "docs": "/docs"
    }


# HEALTH
@app.get("/api/health")
def health():
    return {"status": "ok"}


# SERVICES
@app.get("/api/services")
def services(db: Session = Depends(get_db)):

    return [
        {
            "id": s.id,
            "name": s.name,
            "average_minutes": s.average_minutes
        }
        for s in db.query(Service).filter(
            Service.active == True
        ).all()
    ]


# COUNTERS
@app.get("/api/counters")
def counters(db: Session = Depends(get_db)):

    return [
        {
            "id": c.id,
            "name": c.name,
            "service_id": c.service_id
        }
        for c in db.query(Counter).filter(
            Counter.active == True
        ).all()
    ]


# BOOK TOKEN + CONFIRMATION SMS
@app.post("/api/book")
async def book(
    data: Booking,
    db: Session = Depends(get_db)
):

    service = db.get(Service, data.service_id)
    counter = db.get(Counter, data.counter_id)

    if (
        not service
        or not service.active
        or not counter
        or not counter.active
        or counter.organization_id != service.organization_id
        or (
            counter.service_id
            and counter.service_id != service.id
        )
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid service/counter selection"
        )

    start = datetime.now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    number = db.query(Token).filter(
        Token.service_id == service.id,
        Token.created_at >= start
    ).count() + 1

    token = Token(
        token_number=f"{datetime.now():%m%d}-{number:03d}",
        organization_id=service.organization_id,
        service_id=service.id,
        counter_id=counter.id,
        customer_name=data.customer_name.strip(),
        phone=data.phone.strip()
    )

    db.add(token)
    db.flush()

    # Calculate queue ETA after booking.
    recalculate_queue_estimates(
        db,
        counter_id=counter.id
    )

    db.commit()
    db.refresh(token)

    result = payload(db, token)

    # Confirmation SMS
    eta_text = format_sms_time(token.estimated_call_at)

    confirmation_message = (
        f"QueueLess BD: Booking confirmed! "
        f"Token: {token.token_number}. "
        f"Service: {service.name}. "
        f"Counter: {counter.name}. "
        f"Estimated call time: {eta_text}. "
        f"Please check live queue for updates."
    )

    notification = send_sms(
        token.phone,
        confirmation_message
    )

    if notification and notification.get("sent") is True:
        token.confirmation_sms_sent_at = datetime.utcnow()
        db.commit()

    result["notification"] = notification

    await broadcast({
        "type": "queue_updated"
    })

    return result


# LIVE QUEUE
@app.get("/api/queue")
def queue(
    counter_id: int | None = None,
    db: Session = Depends(get_db)
):

    query = db.query(Token).filter(
        Token.status.in_(["waiting", "serving"])
    )

    if counter_id:
        query = query.filter(
            Token.counter_id == counter_id
        )

    tokens = query.order_by(Token.created_at).all()

    return [
        payload(db, token)
        for token in tokens
    ]


# GET SINGLE TOKEN
@app.get("/api/tokens/{token_id}")
def get_token(
    token_id: int,
    db: Session = Depends(get_db)
):

    token = db.get(Token, token_id)

    if not token:
        raise HTTPException(
            status_code=404,
            detail="Token not found"
        )

    return payload(db, token)


# CALL NEXT TOKEN
@app.post(
    "/api/counters/{counter_id}/next",
    dependencies=[Depends(admin)]
)
async def next_token(
    counter_id: int,
    db: Session = Depends(get_db)
):

    counter = db.get(Counter, counter_id)

    if not counter:
        raise HTTPException(
            status_code=404,
            detail="Counter not found"
        )

    current = db.query(Token).filter(
        Token.counter_id == counter_id,
        Token.status == "serving"
    ).first()

    if current:
        raise HTTPException(
            status_code=409,
            detail="Complete or skip current token first"
        )

    token = db.query(Token).filter(
        Token.counter_id == counter_id,
        Token.status == "waiting"
    ).order_by(
        Token.created_at
    ).first()

    if not token:
        raise HTTPException(
            status_code=404,
            detail="No waiting token"
        )

    token.status = "serving"
    token.called_at = datetime.utcnow()
    token.call_count += 1

    recalculate_queue_estimates(
        db,
        counter_id=counter_id
    )

    db.commit()
    db.refresh(token)

    result = payload(db, token)

    await broadcast({
        "type": "token_called",
        "token": result
    })

    return result


# COMPLETE CURRENT PATIENT AND CALL NEXT
@app.post(
    "/api/counters/{counter_id}/complete-and-next",
    dependencies=[Depends(admin)]
)
async def complete_and_next(
    counter_id: int,
    db: Session = Depends(get_db)
):

    counter = db.get(Counter, counter_id)

    if not counter:
        raise HTTPException(
            status_code=404,
            detail="Counter not found"
        )

    current = db.query(Token).filter(
        Token.counter_id == counter_id,
        Token.status == "serving"
    ).first()

    if not current:
        raise HTTPException(
            status_code=409,
            detail="No active patient to complete"
        )

    now = datetime.utcnow()

    current.status = "completed"
    current.completed_at = now

    if current.called_at:
        current.service_minutes = max(
            0.5,
            (now - current.called_at).total_seconds() / 60
        )

    next_patient = db.query(Token).filter(
        Token.counter_id == counter_id,
        Token.status == "waiting"
    ).order_by(
        Token.created_at
    ).first()

    if next_patient:
        next_patient.status = "serving"
        next_patient.called_at = datetime.utcnow()
        next_patient.call_count += 1

    recalculate_queue_estimates(
        db,
        counter_id=counter_id
    )

    db.commit()

    if not next_patient:

        await broadcast({
            "type": "queue_updated"
        })

        return {
            "completed": True,
            "token": None,
            "message": "Patient completed. No more waiting patients."
        }

    db.refresh(next_patient)

    result = payload(db, next_patient)

    await broadcast({
        "type": "token_called",
        "token": result
    })

    return {
        "completed": True,
        "token": result,
        "message": "Current patient completed. Next patient called."
    }


# RECALL TOKEN
@app.post(
    "/api/tokens/{token_id}/recall",
    dependencies=[Depends(admin)]
)
async def recall(
    token_id: int,
    db: Session = Depends(get_db)
):

    token = db.get(Token, token_id)

    if not token or token.status not in (
        "waiting",
        "serving"
    ):
        raise HTTPException(
            status_code=404,
            detail="Recall not available"
        )

    token.status = "serving"
    token.called_at = datetime.utcnow()
    token.call_count += 1

    recalculate_queue_estimates(
        db,
        counter_id=token.counter_id
    )

    db.commit()
    db.refresh(token)

    result = payload(db, token)

    await broadcast({
        "type": "token_called",
        "token": result
    })

    return result


# SKIP TOKEN
@app.post(
    "/api/tokens/{token_id}/skip",
    dependencies=[Depends(admin)]
)
async def skip(
    token_id: int,
    db: Session = Depends(get_db)
):

    token = db.get(Token, token_id)

    if not token or token.status not in (
        "waiting",
        "serving"
    ):
        raise HTTPException(
            status_code=404,
            detail="Token cannot be skipped"
        )

    token.status = "skipped"

    recalculate_queue_estimates(
        db,
        counter_id=token.counter_id
    )

    db.commit()

    await broadcast({
        "type": "queue_updated"
    })

    return {"ok": True}


# COMPLETE TOKEN (LEGACY ENDPOINT)
@app.post(
    "/api/tokens/{token_id}/complete",
    dependencies=[Depends(admin)]
)
async def complete(
    token_id: int,
    data: Complete,
    db: Session = Depends(get_db)
):

    token = db.get(Token, token_id)

    if not token or token.status != "serving":
        raise HTTPException(
            status_code=409,
            detail="Only serving token can be completed"
        )

    now = datetime.utcnow()

    token.status = "completed"
    token.completed_at = now

    token.service_minutes = (
        data.service_minutes
        if data.service_minutes
        else max(
            0.5,
            (now - token.called_at).total_seconds() / 60
        ) if token.called_at else None
    )

    recalculate_queue_estimates(
        db,
        counter_id=token.counter_id
    )

    db.commit()

    await broadcast({
        "type": "queue_updated"
    })

    return {"ok": True}


# STATISTICS
@app.get(
    "/api/stats",
    dependencies=[Depends(admin)]
)
def stats(db: Session = Depends(get_db)):

    return {
        key: db.query(Token).filter(
            Token.status == value
        ).count()
        for key, value in [
            ("waiting", "waiting"),
            ("serving", "serving"),
            ("completed", "completed"),
            ("skipped", "skipped")
        ]
    } | {
        "total": db.query(Token).count()
    }


# WAIT PREDICTION
@app.get("/api/predict/{service_id}")
def predict(
    service_id: int,
    counter_id: int,
    db: Session = Depends(get_db)
):

    service = db.get(Service, service_id)

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found"
        )

    return {
        "estimated_wait_minutes": estimate_wait(
            db,
            service,
            counter_id
        ),
        "method": "recent observed average with configured fallback",
        "is_trained_ml": False
    }


# WEBSOCKET
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):

    await ws.accept()
    clients.append(ws)

    try:
        while True:
            await ws.receive_text()

    except WebSocketDisconnect:

        if ws in clients:
            clients.remove(ws)