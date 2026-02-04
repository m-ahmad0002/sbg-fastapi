import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from db.models import Session as SessionModel, Message


def get_or_create_session(db: Session, session_id: str | None) -> str:
    """
    Get existing session or create a new one.
    Updates last_active timestamp on access.
    """
    if session_id:
        session = db.query(SessionModel).filter_by(session_id=session_id).first()
        if session:
            session.last_active = datetime.utcnow()
            db.commit()
            return session.session_id

    new_id = str(uuid.uuid4())
    session = SessionModel(
        session_id=new_id,
        created_at=datetime.utcnow(),
        last_active=datetime.utcnow()
    )
    db.add(session)
    db.commit()
    return new_id


def save_message(db: Session, session_id: str, role: str, content: str) -> None:
    """
    Save a single chat message and update session last_active.
    """
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.utcnow()
    )
    db.add(msg)

    # Update session activity
    session = db.query(SessionModel).filter_by(session_id=session_id).first()
    if session:
        session.last_active = datetime.utcnow()

    db.commit()


def get_chat_history(db: Session, session_id: str, limit: int = 6):
    """
    Get last N messages in chronological order.
    """
    messages = (
        db.query(Message)
        .filter_by(session_id=session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))
