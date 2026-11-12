
import json
import re
from typing import Any

from json_repair import repair_json

from app.services.ai_provider_manager import AIProviderManager as OpenRouterClient


class JDQuestionGenerator:
    """Generate a complete, pre-planned, branch-aware interview blueprint."""

    STAGES = {
        "introduction": "Introduction",
        "candidate_background": "Candidate Background",
        "technical_interview": "Technical Interview",
        "behavioral_interview": "Behavioral Interview",
        "closing": "Closing",
    }

    def __init__(self):
        self.client = OpenRouterClient()

    async def generate_questions(
        self,
        job_role: str,
        job_description: str,
        jd_analysis: dict[str, Any],
        resume_analysis: dict[str, Any] | None = None,
        count: int = 10,
    ) -> list[dict]:

        if not isinstance(job_role, str) or not job_role.strip():
            raise ValueError("Job role cannot be empty.")

        if not isinstance(job_description, str) or not job_description.strip():
            raise ValueError("Job description cannot be empty.")

        if not isinstance(jd_analysis, dict):
            raise ValueError("JD analysis must be a dictionary.")

        if not isinstance(resume_analysis, dict):
            raise ValueError("Resume analysis must be a dictionary.")

        if count != 10:
            raise ValueError(
                "The staged interview blueprint currently requires exactly 10 questions."
            )

        candidate_type = resume_analysis.get("candidate_type", "uncertain")

        if candidate_type not in {"fresher", "experienced", "uncertain"}:
            candidate_type = "uncertain"

        system_prompt = """
You are an expert interviewer creating a fair, personalized interview blueprint.

Generate exactly 10 questions in the exact sequence and stage distribution below.

All questions must be prepared now. The live interview will only serve these saved
questions; there will be no live question generation or candidate classification.

MANDATORY SEQUENCE:

1. introduction (1 question):
   Invite the candidate to introduce themselves.

2-3. candidate_background (2 questions):
   - fresher: ask about internships, academic/personal projects,
     contributions and learning.
   - experienced: ask about full-time/professional employment,
     responsibilities, impact and ownership.
   - uncertain: ask neutral clarification questions that establish
     whether listed work was internship, project, contract or
     full-time employment. Do not assume either branch.

4-7. technical_interview (4 questions):
   Assess JD requirements and personalize using relevant resume
   evidence. Do not assume resume skills that are not explicitly
   present. Prioritize required JD skills.

8-9. behavioral_interview (2 questions):
   Assess job-relevant collaboration, problem solving,
   communication, ownership or adaptability. Use STAR-friendly prompts.

10. closing (1 question):
    Invite the candidate to add relevant information or ask a question.

FOR EVERY QUESTION RETURN:

- question: natural spoken question, not a heading or multi-part questionnaire
- stage: one of introduction, candidate_background, technical_interview,
  behavioral_interview, closing
- stage_label: human-readable stage label
- candidate_branch: fresher, experienced, uncertain, or all
- competency: concise competency label
- difficulty: easy, medium, hard
- expected_concepts: 2 to 5 short assessable concepts
- estimated_time_seconds: integer from 30 to 300

RULES:

- Use candidate_branch="all" for introduction, technical, behavioral
  and closing questions.
- Background questions must use the actual selected candidate branch.
- For uncertain candidates, background questions must be neutral
  and clarify evidence.
- Never treat internships or academic projects as full-time
  professional experience.

COMPETENCY GROUNDING RULES:

1. Every technical competency must directly represent a skill,
   responsibility, tool, or requirement explicitly mentioned
   in the JOB DESCRIPTION or EXTRACTED JOB REQUIREMENTS.

2. Prefer competency labels that reuse the terminology from
   the JD.

3. You may use concise paraphrases only when their meaning is
   directly supported by the JD.

4. Never invent additional competencies based on assumptions
   about the job title or industry.

5. Do not introduce skills such as data cleaning, data validation,
   Python, statistics, machine learning, or programming unless
   the JD explicitly requires them.

6. The technical question itself must assess the competency
   specified in its competency field.

7. Distribute the four technical questions across different
   JD requirements whenever sufficient distinct requirements
   are available.

8. Do not use a generic competency label when a more precise
   JD-grounded label is available.

9. Resume evidence may personalize the question, but it must
   not introduce a new job requirement absent from the JD.

10. If a requirement is ambiguous, prefer a competency label
    that uses the exact wording from the JD.

ADDITIONAL RULES:

- Technical questions must be grounded in the JD.
- Do not invent technologies or tools.
- Avoid duplicates and avoid asking the same thing in different wording.
- Do not include model answers, scoring or explanations.
- Return ONLY valid JSON.

REQUIRED JSON SHAPE:

{
  "questions": [
    {
      "question": "Tell me about yourself.",
      "stage": "introduction",
      "stage_label": "Introduction",
      "candidate_branch": "all",
      "competency": "Introduction",
      "difficulty": "easy",
      "expected_concepts": [
        "Communication",
        "Professional background"
      ],
      "estimated_time_seconds": 60
    }
  ]
}
"""

        user_prompt = f"""
JOB ROLE:
{job_role.strip()}

JOB DESCRIPTION:
{job_description.strip()}

EXTRACTED JOB REQUIREMENTS:
{json.dumps(jd_analysis, ensure_ascii=False, indent=2)}

RESUME ANALYSIS:
{json.dumps(resume_analysis, ensure_ascii=False, indent=2)}

SELECTED CANDIDATE BRANCH: {candidate_type}

Generate exactly 10 questions following the mandatory sequence
and stage distribution.

The two candidate_background questions must follow
SELECTED CANDIDATE BRANCH.

TECHNICAL QUESTION REQUIREMENTS:

Generate all four technical questions using the actual
JOB DESCRIPTION and EXTRACTED JOB REQUIREMENTS.

Every technical competency must be directly traceable to
a requirement in the provided JD.

Prefer the original terminology used in the JD.

Do not infer additional skills merely because they are
commonly associated with the job title.

Do not introduce technologies, tools, or competencies
that are absent from the JD.

The question wording must assess the competency assigned
to that question.

Use relevant resume evidence only for personalization.
Do not introduce requirements absent from the JD.

Distribute the four questions across different JD requirements
where possible.

Return only the JSON object.
"""

        response = await self.client.generate_json_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=8000,
            temperature=0.2,
        )

        data = self._parse_response(response)

        raw_questions = data.get("questions")

        if not isinstance(raw_questions, list):
            raise ValueError(
                "Question generator returned no question list."
            )

        questions: list[dict] = []
        seen: set[str] = set()

        for item in raw_questions:

            if not isinstance(item, dict):
                continue

            question_text = item.get("question")

            if (
                not isinstance(question_text, str)
                or len(question_text.strip()) < 15
            ):
                continue

            question_text = question_text.strip()
            normalized = self._normalize(question_text)

            if normalized in seen:
                continue

            stage = str(
                item.get("stage", "")
            ).strip().lower()

            if stage not in self.STAGES:
                continue

            branch = str(
                item.get("candidate_branch", "")
            ).strip().lower()

            if branch not in {
                "all",
                "fresher",
                "experienced",
                "uncertain",
            }:
                continue

            competency = item.get("competency")

            if (
                not isinstance(competency, str)
                or not competency.strip()
            ):
                continue

            concepts = item.get("expected_concepts", [])

            if not isinstance(concepts, list):
                continue

            concepts = list(dict.fromkeys(
                value.strip()
                for value in concepts
                if isinstance(value, str) and value.strip()
            ))

            if not 2 <= len(concepts) <= 5:
                continue

            difficulty = str(
                item.get("difficulty", "medium")
            ).lower().strip()

            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"

            try:
                duration = int(
                    item.get("estimated_time_seconds", 120)
                )
            except (TypeError, ValueError):
                duration = 120

            duration = max(30, min(300, duration))

            questions.append({
                "question": question_text,
                "stage": stage,
                "stage_label": self.STAGES[stage],
                "candidate_branch": branch,
                "competency": competency.strip(),
                "difficulty": difficulty,
                "expected_concepts": concepts,
                "estimated_time_seconds": duration,
                "sequence_number": len(questions) + 1,
                "question_type": "primary",
            })

            seen.add(normalized)

        if len(questions) != count:
            raise ValueError(
                f"Expected {count} valid staged questions, "
                f"received {len(questions)}."
            )

        # Enforce order and branch invariants independently
        # of the LLM output.

        expected_stages = (
            ["introduction"]
            + ["candidate_background"] * 2
            + ["technical_interview"] * 4
            + ["behavioral_interview"] * 2
            + ["closing"]
        )

        for index, (question, expected_stage) in enumerate(
            zip(questions, expected_stages), 1
        ):

            if question["stage"] != expected_stage:
                raise ValueError(
                    f"Question {index} must belong to stage "
                    f"'{expected_stage}', not '{question['stage']}'."
                )

            expected_branch = (
                candidate_type
                if expected_stage == "candidate_background"
                else "all"
            )

            if question["candidate_branch"] != expected_branch:
                raise ValueError(
                    f"Question {index} must use candidate branch "
                    f"'{expected_branch}'."
                )

        return questions

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():
            raise ValueError(
                "Question generator returned an empty response."
            )

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            response.strip(),
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            result = repair_json(
                cleaned,
                return_objects=True,
            )

        if not isinstance(result, dict):
            raise ValueError(
                "Question generator returned invalid JSON."
            )

        return result

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())
