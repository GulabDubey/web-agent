from app.schemas.user_schema import UserList, UserCreate

class UserService:
    def __init__(self, repository):
        self.repository = repository

    def create_user(self, user: UserCreate):
        return self.repository.create(user)

    def update_user():
        pass

    def delete_user():
        pass

    def list_users(self, filters: UserList):
        return self.repository.list(filters)

    def get_user(self, id):
        return self.repository.find_by_id(id)
