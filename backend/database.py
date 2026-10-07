import os
from datetime import date, datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv()
url = os.getenv("DATABASE_URL", "sqlite:///./datapulse.db")
for prefix in ("postgres://", "postgresql://"):
    if url.startswith(prefix):
        url = url.replace(prefix, "postgresql+psycopg://", 1)
engine = create_engine(
    url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
)
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    pass


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    row_count: Mapped[int] = mapped_column(Integer)


class Sale(Base):
    __tablename__ = "sales"
    sale_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    product: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
