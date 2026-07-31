from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ContactUsRequest(BaseModel):
    session_id: str
    name: str
    email: str
    country_code: str
    contact: str