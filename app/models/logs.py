from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.base_class import Base

class Logs(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=True)
    email = Column(String, index=True, nullable=True)
    action_type = Column(String, index=True, nullable=True)
    reference_id = Column(String, index=True, nullable=True)
    status = Column(String, index=True, nullable=True)
    date_time = Column(DateTime, default=datetime.utcnow)
