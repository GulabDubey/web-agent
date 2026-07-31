from pydantic import BaseModel, EmailStr, ConfigDict

class UserList(BaseModel):
    search: str | None = None
    status: str | None = None

class UserCreate(BaseModel):
    name: str
    email: str
    mobile_no: str

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    mobile_no: str | None = None

    model_config = ConfigDict(from_attributes=True)

class UserListResponse(BaseModel):
    pass 
