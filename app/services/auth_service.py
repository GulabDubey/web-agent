class AuthService:
    def __init__(self, repository):
        self.repository = repository

    def login_user(self, user):
        user = self.repository.find_by_email(email)        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )


        if not verify_password(
            password,
            user.password
        ):

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )


        token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email
            }
        )


        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email
            }
        }
    