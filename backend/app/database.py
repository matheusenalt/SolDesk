from sqlalchemy import CheckConstraint, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Installation(Base):
    __tablename__ = "installation"
    __table_args__ = (CheckConstraint("id = 1", name="installation_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)


def session_factory(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    return engine, sessionmaker(engine)
