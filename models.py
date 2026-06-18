# models.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, date

class Net(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)   # e.g. "net-1"
    lat: float
    lon: float
    area_m2: float = 10.0
    mesh_type: str = "standard"
    capacity_l: float = 200.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SensorReading(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    net_id: str = Field(foreign_key="net.id")
    timestamp: datetime
    humidity: float
    temperature: float
    pm25: float

class Metric(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    net_id: str = Field(foreign_key="net.id")
    date: date
    water_l: float = 0.0
    humidity: float = 0.0
    fog_prob: float = 0.0
    pm25: float = 0.0
    pm10: float = 0.0
    aqi: float = 0.0
    last_update: datetime = Field(default_factory=datetime.utcnow)

class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    net_id: Optional[str] = Field(default=None, foreign_key="net.id")
    ts: datetime = Field(default_factory=datetime.utcnow)
    type: str
    message: str
    acknowledged: bool = False
