import os

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, JSON, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    item = Column(String, nullable=False)
    price = Column(Float, nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False)
    response = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("key", name="uq_idempotency_key"),)


def init_db():
    Base.metadata.create_all(bind=engine)


class Repository:
    def save_order(self, order):
        with SessionLocal() as session:
            row = Order(item=order["item"], price=order["price"])
            session.add(row)
            session.commit()
            return row.id

    def get_idempotent_response(self, key):
        with SessionLocal() as session:
            row = session.query(IdempotencyRecord).filter_by(key=key).one_or_none()
            return row.response if row else None

    def save_idempotent_response(self, key, response):
        with SessionLocal() as session:
            session.add(IdempotencyRecord(key=key, response=response))
            try:
                session.commit()
            except Exception:
                session.rollback()
                return self.get_idempotent_response(key)
            return response
