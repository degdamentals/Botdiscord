"""
SQLAlchemy models for Deg Bot database
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Client(Base):
    """
    Represents a Discord user who uses the coaching service
    """
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, nullable=False, index=True)
    discord_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_sessions = Column(Integer, default=0, nullable=False)

    # Relationships
    bookings = relationship("Booking", back_populates="client", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client(discord_name='{self.discord_name}', total_sessions={self.total_sessions})>"


class Booking(Base):
    """
    Represents a coaching session booking
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    google_event_id = Column(String, unique=True, nullable=True, index=True)
    booking_type = Column(String, nullable=False)  # "gratuit" or "payant"
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    status = Column(String, default="confirmed", nullable=False)  # confirmed, completed, cancelled, no_show
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ticket_channel_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    client = relationship("Client", back_populates="bookings")
    feedback = relationship("Feedback", back_populates="booking", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Booking(id={self.id}, type='{self.booking_type}', status='{self.status}', scheduled_at={self.scheduled_at})>"


class Feedback(Base):
    """
    Represents feedback from a client after a coaching session
    """
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, unique=True)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    posted_to_channel = Column(Boolean, default=False, nullable=False)

    # Relationships
    booking = relationship("Booking", back_populates="feedback")

    def __repr__(self):
        return f"<Feedback(booking_id={self.booking_id}, rating={self.rating})>"


class Note(Base):
    """
    Represents coach notes about a client
    """
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_discord_id = Column(String, nullable=False)  # Coach who created the note

    # Relationships
    client = relationship("Client", back_populates="notes")

    def __repr__(self):
        return f"<Note(client_id={self.client_id}, created_at={self.created_at})>"


class Event(Base):
    """
    Represents a Discord event (coaching de groupe, tournoi, etc.)
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    google_event_id = Column(String, unique=True, nullable=True, index=True)
    discord_event_id = Column(String, unique=True, nullable=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    max_participants = Column(Integer, nullable=True)
    announcement_message_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String, default="scheduled", nullable=False)  # scheduled, completed, cancelled

    # Relationships
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(title='{self.title}', scheduled_at={self.scheduled_at}, status='{self.status}')>"


class EventParticipant(Base):
    """
    Represents a participant registered for an event
    """
    __tablename__ = "event_participants"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    discord_id = Column(String, nullable=False)
    discord_name = Column(String, nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    event = relationship("Event", back_populates="participants")

    def __repr__(self):
        return f"<EventParticipant(event_id={self.event_id}, discord_name='{self.discord_name}')>"
