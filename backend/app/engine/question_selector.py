
from app.config.question_bank import QUESTION_BANK


class QuestionSelector:

    @staticmethod
    def get_questions_for_stage(stage: str):

        return QUESTION_BANK.get(stage, [])

    @staticmethod
    def select_next_question(
        stage: str,
        asked_question_ids: list
    ):

        # Get questions belonging to the current stage
        stage_questions = QUESTION_BANK.get(stage, [])

        # Find questions that haven't been asked
        available_questions = [
            question
            for question in stage_questions
            if question["question_id"] not in asked_question_ids
        ]

        # No questions remaining in this stage
        if not available_questions:
            return None

        # Select the first available question
        return available_questions[0]
