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
    def mobile(value: str, country_code: str = "+91") -> bool:
        # India: 10 digits starting 6-9. Elsewhere: 6-14 national digits
        # (E.164 caps a full number at 15 digits including the country code).
        pattern = r"[6-9]\d{9}" if country_code == "+91" else r"\d{6,14}"
        return bool(re.fullmatch(pattern, value))


    @staticmethod
    def message(value: str) -> bool:
        return len(value.strip()) >= 5