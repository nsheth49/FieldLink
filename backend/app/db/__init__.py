from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, connect_args={'check_same_thread': False, 'timeout': 30} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
if settings.database_url.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_setup(connection, _):
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')

Session = sessionmaker(engine, expire_on_commit=False)
