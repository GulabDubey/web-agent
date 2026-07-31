from sqlalchemy import Column, Integer, String
from app.config.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key = True)
    name = Column(String(100))
    email = Column(String(255), unique=True)
    mobile_no = Column(String(255), unique=True)
    password = Column(String(255))