from dataclasses import dataclass
from typing import Callable
from app.services.validator_service import ValidatorService

@dataclass
class Question:
    key: str
    text: str
    validator: Callable
    error_message: str


QUESTIONS = [

    Question(
        key="name",
        text="What is your name?",
        validator=ValidatorService.name,
        error_message="Please enter a valid name."
    ),

 
    Question(
        key="email",
        text="What is your email?",
        validator=ValidatorService.email,
        error_message="Please enter a valid email address."
    ),


    Question(
        key="mobile",
        text="What is your mobile number?",
        validator=ValidatorService.mobile,
        error_message="Please enter a valid 10-digit mobile number."
    ),


    Question(
        key="query",
        text="How can we help you today?",
        validator=ValidatorService.message,
        error_message="Please describe how we can help you."
    )

]