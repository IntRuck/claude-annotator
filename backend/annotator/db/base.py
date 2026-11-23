"""SQLAlchemy declarative base. Tables are created by Flyway only: never call Base.metadata.create_all."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
