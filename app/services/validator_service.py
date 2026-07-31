import re
from pydantic import EmailStr, TypeAdapter


class ValidatorService:

    @staticmethod
    def required(value: str) -> bool:
        return bool(value.strip())


    @staticmethod
    def name(value: str) -> bool:
        return len(value.strip()) >= 3


    @staticmethod
    def email(value: str) -> bool:
        try:
            TypeAdapter(EmailStr).validate_python(value)
            return True
        except Exception:
            return False


    @staticmethod
    def mobile(value: str) -> bool:
        return bool(
            re.fullmatch(
                r"[6-9]\d{9}",
                value
            )
        )


    @staticmethod
    def message(value: str) -> bool:
        return len(value.strip()) >= 5