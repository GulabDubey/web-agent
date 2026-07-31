from app.models.user_model import User
from app.repositories.base_repository import BaseRepository
from fastapi import HTTPException
from app.core.security import hash_password

class UserRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db)

    def create(self, user_data):
        password = f"{user_data.name[:4].upper()}{user_data.mobile_no[-4:]}"
        user = User(
            name=user_data.name,
            email=user_data.email,
            mobile_no=user_data.mobile_no,
            password=hash_password(
                password
            )
        )
        return self.save(user)

    def update():
        pass

    def delete():
        pass

    def find_by_id(self, id: int):
        user = (self.db.query(User).filter(User.id == id).first())

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )    

        return user

    def find_by_email(self, email: str):
        user = (self.db.query(User).filter(User.email == email).first())

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )  
        return user

    def list(self, filters={}):
        query = self.db.query(User)

        if filters.search:
            query = query.filter(
                User.name.ilike(f"%{filters.search}%")
            )

        if filters.status:
            query = query.filter(
                User.status == filters.status
            )

        return self.paginate(query)


