from app.config.question_config import QUESTIONS


class QuestionService:

    def validate_answer(
        self,
        session,
        answer
    ):

        index = session.current_question-1

        if index >= len(QUESTIONS):
            return True, None


        question = QUESTIONS[index]


        if not question.validator(answer):

            return (
                False,
                question.error_message
            )


        session.answers[
            question.key
        ] = answer


        return True, None



    def next_question(
        self,
        session
    ):

        if session.current_question < len(QUESTIONS):

            question = QUESTIONS[
                session.current_question
            ]

            session.current_question += 1

            return question


        return None