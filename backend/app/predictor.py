from sqlalchemy import desc

from .models import Token


def average_service_minutes(db, service):
    rows = (
        db.query(Token.service_minutes)
        .filter(
            Token.service_id == service.id,
            Token.status == "completed",
            Token.service_minutes.isnot(None)
        )
        .order_by(desc(Token.completed_at))
        .limit(30)
        .all()
    )

    values = [
        float(row[0])
        for row in rows
        if row[0] is not None and float(row[0]) > 0
    ]

    if values:
        return sum(values) / len(values)

    return float(service.average_minutes or 8)


def estimate_wait(db, service, counter_id):
    avg = average_service_minutes(db, service)

    waiting = (
        db.query(Token)
        .filter(
            Token.counter_id == counter_id,
            Token.status == "waiting"
        )
        .count()
    )

    serving = (
        db.query(Token)
        .filter(
            Token.counter_id == counter_id,
            Token.status == "serving"
        )
        .count()
    )

    return max(0, round(avg * (waiting + serving)))