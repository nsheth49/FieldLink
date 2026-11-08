from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Float, Integer, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

JSON = JSON().with_variant(JSONB, 'postgresql')

def uid(): return uuid4().hex
def now(): return datetime.now(timezone.utc).timestamp()

class Base(DeclarativeBase): pass

class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str]
    network: Mapped[dict] = mapped_column(JSON)
    ops: Mapped[dict] = mapped_column(JSON)
    manifest: Mapped[dict] = mapped_column(JSON)
    start: Mapped[float]
    end: Mapped[float]

class Asset(Base):
    __tablename__ = 'assets'
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    topology: Mapped[dict] = mapped_column(JSON)

class Telemetry(Base):
    __tablename__ = 'telemetry'
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), primary_key=True)
    ts: Mapped[float] = mapped_column(Float, primary_key=True)
    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    metric: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[float]
    __table_args__ = (Index('ix_series', 'dataset_id', 'asset_id', 'metric', 'ts'),)

class Run(Base):
    __tablename__ = 'runs'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    mode: Mapped[str] = mapped_column(default='snapshot')
    cursor: Mapped[float]
    paused: Mapped[int] = mapped_column(default=1)
    speed: Mapped[int] = mapped_column(default=1)
    revision: Mapped[int] = mapped_column(default=0)
    state: Mapped[dict] = mapped_column(JSON, default=dict)

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)

class Plan(Base):
    __tablename__ = 'plans'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    version: Mapped[int]
    fingerprint: Mapped[str]
    status: Mapped[str] = mapped_column(default='PENDING_APPROVAL')
    expires: Mapped[float] = mapped_column(default=lambda: now()+900)
    data: Mapped[dict] = mapped_column(JSON)

class Reservation(Base):
    __tablename__ = 'reservations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    plan_id: Mapped[str] = mapped_column(ForeignKey('plans.id'))
    truck_id: Mapped[str]
    start: Mapped[float]
    end: Mapped[float]

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str]
    role: Mapped[str]
    facilities: Mapped[list] = mapped_column(JSON, default=list)

class AuthSession(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires: Mapped[float]

class ChannelIdentity(Base):
    __tablename__ = 'channel_identities'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    space_id: Mapped[str]
    project_id: Mapped[str]

class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), index=True)
    actor: Mapped[str]
    text: Mapped[str]
    scenario_ts: Mapped[float]
    wall_ts: Mapped[float] = mapped_column(default=now)
    delivery: Mapped[str] = mapped_column(default='mock')

class Constraint(Base):
    __tablename__ = 'constraints'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'))
    truck_id: Mapped[str]
    until: Mapped[float]
    source: Mapped[str]
    message_id: Mapped[str | None] = mapped_column(default=None)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(unique=True)
    kind: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    lease: Mapped[float] = mapped_column(default=0)
    next_attempt: Mapped[float] = mapped_column(default=0)

class Outbox(Base):
    __tablename__ = 'outbox'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    lease: Mapped[float] = mapped_column(default=0)
    next_attempt: Mapped[float] = mapped_column(default=0)

class Audit(Base):
    __tablename__ = 'audit_log'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor: Mapped[str]
    action: Mapped[str]
    run_id: Mapped[str | None]
    plan_id: Mapped[str | None]
    time: Mapped[float] = mapped_column(default=now)
    outcome: Mapped[str]
