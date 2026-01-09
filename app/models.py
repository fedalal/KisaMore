from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, JSON

class Base(DeclarativeBase):
    pass

class RackState(Base):
    __tablename__ = "rack_state"
    rack_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    light_on: Mapped[bool] = mapped_column(Boolean, default=False)
    water_on: Mapped[bool] = mapped_column(Boolean, default=False)

    light_mode: Mapped[str] = mapped_column(String, default="schedule")
    water_mode: Mapped[str] = mapped_column(String, default="schedule")

class RackSchedule(Base):
    __tablename__ = "rack_schedule"
    rack_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_json: Mapped[dict] = mapped_column(JSON, default=dict)
