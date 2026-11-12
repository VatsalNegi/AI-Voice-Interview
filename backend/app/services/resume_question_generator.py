
import json
import re

from json_repair import repair_json

from app.services.ai_provider_manager import AIProviderManager as OpenRouterClient


class ResumeQuestionGenerator:
    """
    Generates interview questions grounded in the candidate's resume.

    Questions are generated in batches to reduce API calls.
    """

    def __init__(self):
        self.client = OpenRouterClient()

    async def generate_questions(
        self,
        resume_text: str,
        asked_questions: list[str] | None = None,
        count: int = 3
    ) -> list[dict]:

        if not resume_text or not resume_text.strip():
            return []

        asked_questions = asked_questions or []

        system_prompt = """
You are an expert technical interviewer.

Generate interview questions using ONLY information
supported by the candidate's resume.

Focus on:
- Technologies and programming languages listed.
- Frameworks and tools listed.
- Projects and their stated features.
- Work experience and responsibilities.
- Technical decisions and implementation details.

Rules:
1. Do not invent projects, skills, experience, or achievements.
2. Do not assume the candidate used a technology unless
   it appears in the resume.
3. Questions must be relevant to the candidate's actual
   resume.
4. Prefer practical questions that test understanding.
5. Avoid repeating questions that have already been asked.
6. Each question must have 2 to 5 expected concepts.
7. Expected concepts must be short and assessable.
8. Generate different questions covering different
   resume topics when possible.
9. Do not include answers to the questions.
10. Return ONLY valid JSON.

Required JSON structure:

{
  "questions": [
    {
      "question": "Your interview question?",
      "expected_concepts": [
        "concept one",
        "concept two"
      ],
      "competency": "Technical Knowledge",
      "difficulty": "medium"
    }
  ]
}
"""

        user_prompt = f"""
Generate exactly {count} interview questions.

CANDIDATE RESUME:
{resume_text}

QUESTIONS ALREADY ASKED:
{json.dumps(asked_questions, indent=2)}

Generate questions grounded in the resume.
Do not repeat previously asked questions.

Return only the required JSON object.
"""

        try:

            response = await self.client.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

            data = self._parse_response(response)

            raw_questions = data.get("questions", [])

            if not isinstance(raw_questions, list):
                return []

            questions = []

            for item in raw_questions:

                if not isinstance(item, dict):
                    continue

                question_text = item.get("question", "")

                concepts = item.get(
                    "expected_concepts", []
                )

                if not isinstance(question_text, str):
                    continue

                question_text = question_text.strip()

                if len(question_text) < 12:
                    continue

                if not isinstance(concepts, list):
                    continue

                concepts = [
                    str(concept).strip()
                    for concept in concepts
                    if isinstance(concept, str)
                    and concept.strip()
                ]

                if not concepts:
                    continue

                # Prevent duplicate questions.
                normalized_question = self._normalize(
                    question_text
                )

                if normalized_question in {
                    self._normalize(q)
                    for q in asked_questions
                }:
                    continue

                if any(
                    self._normalize(existing["question"])
                    == normalized_question
                    for existing in questions
                ):
                    continue

                difficulty = str(
                    item.get("difficulty", "medium")
                ).lower()

                if difficulty not in [
                    "easy",
                    "medium",
                    "hard"
                ]:
                    difficulty = "medium"

                competency = str(
                    item.get(
                        "competency",
                        "Resume-Based Technical Knowledge"
                    )
                ).strip()

                questions.append({
                    "question": question_text,
                    "expected_concepts": concepts[:5],
                    "competency": competency,
                    "difficulty": difficulty
                })

                if len(questions) >= count:
                    break

            return questions

        except Exception as error:

            print(
                f"Resume question generation failed: {error}"
            )

            return []

    # --------------------------------------------------
    # JSON PARSING
    # --------------------------------------------------

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():
            raise ValueError(
                "Resume question generator returned an empty response."
            )

        cleaned = response.strip()

        if cleaned.startswith("```"):

            cleaned = re.sub(
                r"^```(?:json)?\s*",
                "",
                cleaned,
                flags=re.IGNORECASE
            )

            cleaned = re.sub(
                r"\s*```$",
                "",
                cleaned
            )

        try:

            result = json.loads(cleaned)

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            pass

        result = repair_json(
            cleaned,
            return_objects=True
        )

        if not isinstance(result, dict):
            raise ValueError(
                "Invalid JSON from resume question generator."
            )

        return result

    @staticmethod
    def _normalize(text: str) -> str:

        return " ".join(
            text.lower().split()
        )
