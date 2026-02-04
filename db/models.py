from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from datetime import datetime
from .database import Base

class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.session_id"))
    role = Column(String)  # user / assistant
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
