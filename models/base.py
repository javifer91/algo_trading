from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, String, Float, Integer, func
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    pass

class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    side: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    commission_paid: Mapped[float] = mapped_column(Float, default=0.0)
    spread_cost: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    
    gross_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    strategy_name: Mapped[str] = mapped_column(String)
    decision_reason: Mapped[str] = mapped_column(String)
