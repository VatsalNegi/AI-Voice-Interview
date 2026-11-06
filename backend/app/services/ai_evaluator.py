
import json
import re

from json_repair import repair_json

from app.services.openrouter_client import OpenRouterClient
from app.schemas.ai_evaluation import AIEvaluation


class AIEvaluator:

    def __init__(self):
        self.client = OpenRouterClient()

    # --------------------------------------------------
    # DETECT EXPLICIT NO-KNOWLEDGE ANSWERS
    # --------------------------------------------------

    @staticmethod
    def detect_no_knowledge(answer: str) -> bool:

        if not answer or not answer.strip():
            return True

        normalized = answer.lower().strip()
        normalized = re.sub(r"[.!?,;]+", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)

        # Exact or near-exact responses indicating that
        # the candidate cannot or does not want to answer.
        no_knowledge_patterns = [
            r"i don't know",
            r"i do not know",
            r"i have no idea",
            r"no idea",
            r"not sure",
            r"i am not sure",
            r"i'm not sure",
            r"i cannot answer",
            r"i can't answer",
            r"i don't remember",
            r"i do not remember",
            r"don't remember",
            r"do not remember",
            r"skip",
            r"pass",
            r"i will skip",
            r"i want to skip",
            r"unable to answer",
            r"i have no knowledge",
            r"no knowledge"
        ]

        for pattern in no_knowledge_patterns:

            if re.fullmatch(pattern, normalized):
                return True

        # Short responses such as:
        # "I don't know this topic"
        # "I have absolutely no idea about it"
        if len(normalized.split()) <= 7:

            extended_patterns = [
                r"i don't know (this|that|anything|the answer)",
                r"i do not know (this|that|anything|the answer)",
                r"i have no idea about (this|that|it)",
                r"i am not sure about (this|that|it)",
                r"i'm not sure about (this|that|it)",
                r"i cannot answer (this|that)",
                r"i can't answer (this|that)"
            ]

            for pattern in extended_patterns:

                if re.fullmatch(pattern, normalized):
                    return True

        return False

    # --------------------------------------------------
    # BUILD NO-KNOWLEDGE EVALUATION WITHOUT LLM
    # --------------------------------------------------

    @staticmethod
    def _build_no_knowledge_evaluation(
        expected_concepts: list[str]
    ) -> AIEvaluation:

        return AIEvaluation(
            technical_correctness=0,
            concept_coverage=0,
            reasoning_quality=0,
            communication_clarity=0,
            answer_classification="NO_KNOWLEDGE",
            matched_concepts=[],
            missing_concepts=expected_concepts,
            incorrect_statements=[],
            evidence=[],
            strengths=[],
            improvement_areas=[
                "Candidate was unable to provide an answer."
            ],
            overall_feedback=(
                "The candidate explicitly indicated that "
                "they did not know the answer or wanted to skip."
            ),
            confidence="high"
        )

    # --------------------------------------------------
    # EVALUATE ANSWER
    # --------------------------------------------------

    async def evaluate_answer(
        self,
        question: str,
        expected_concepts: list[str],
        candidate_answer: str,
        candidate_evidence: dict | None = None
    ) -> AIEvaluation:

        # Check explicit no-knowledge responses first.
        # No unnecessary OpenRouter request is made.
        if self.detect_no_knowledge(candidate_answer):

            print(
                "Candidate explicitly skipped or did not know "
                "the answer. Skipping LLM evaluation."
            )

            return self._build_no_knowledge_evaluation(
                expected_concepts
            )

        evidence_context = json.dumps(
            candidate_evidence or {},
            indent=2
        )

        system_prompt = """
You are an expert technical interviewer.

Evaluate candidate answers objectively and independently.

Return ONLY one valid JSON object.

Required fields:
- technical_correctness
- concept_coverage
- reasoning_quality
- communication_clarity
- answer_classification
- matched_concepts
- missing_concepts
- incorrect_statements
- evidence
- strengths
- improvement_areas
- overall_feedback
- confidence

ANSWER CLASSIFICATION:

Classify every answer into exactly one category:

1. GOOD:
   The answer correctly and meaningfully addresses the question.
   A concise but technically correct answer can be GOOD.
   Do not classify an answer as PARTIAL merely because
   the candidate did not mention every expected concept.
   Minor omissions should not automatically reduce a GOOD answer
   to PARTIAL.

2. PARTIAL:
   The answer is relevant to the question and demonstrates
   some genuine understanding, but contains important gaps,
   incomplete reasoning, or requires clarification.
   A useful follow-up could help assess the candidate further.

3. IRRELEVANT:
   The answer does not meaningfully address the question.
   It may be unrelated, vague, evasive, or demonstrate no
   meaningful understanding of the asked topic.
   Do not classify a relevant but incomplete answer as IRRELEVANT.

4. NO_KNOWLEDGE:
   The candidate explicitly says they do not know,
   cannot answer, have no idea, or want to skip.
   Use this only when the answer clearly communicates
   inability or unwillingness to answer.

CLASSIFICATION GUIDELINES:

- Focus on the actual meaning of the answer, not exact keywords.
- Recognize technically correct paraphrases.
- Do not demand every expected concept if the answer
  correctly answers the main question.
- Do not confuse communication mistakes with technical mistakes.
- Do not classify a correct short answer as PARTIAL just
  because it lacks unnecessary details.
- An unrelated answer must be IRRELEVANT.
- A relevant answer with significant gaps should be PARTIAL.
- If the answer is technically incorrect, evaluate the
  incorrect statements and classify appropriately.
- Never invent evidence or facts.
- If the candidate provides a substantive answer after saying
  they are unsure, evaluate the substantive answer normally.

SCORING RULES:

1. All four scores must be integers between 0 and 100.
2. All list fields must contain strings.
3. overall_feedback must be a non-empty string.
4. confidence must be low, medium, or high.
5. Evidence must be exact excerpts from the candidate answer.
6. Do not invent evidence.
7. Include expected concepts in matched_concepts or
   missing_concepts as appropriate.
8. Do not make hiring or rejection decisions.

Return this exact JSON structure:

{
  "technical_correctness": 0,
  "concept_coverage": 0,
  "reasoning_quality": 0,
  "communication_clarity": 0,
  "answer_classification": "PARTIAL",
  "matched_concepts": [],
  "missing_concepts": [],
  "incorrect_statements": [],
  "evidence": [],
  "strengths": [],
  "improvement_areas": [],
  "overall_feedback": "Evaluation feedback",
  "confidence": "medium"
}
"""

        user_prompt = f"""
Evaluate this interview answer.

QUESTION:
{question}

EXPECTED CONCEPTS:
{json.dumps(expected_concepts, indent=2)}

CANDIDATE ANSWER:
{candidate_answer}

POTENTIAL EVIDENCE:
{evidence_context}

Independently verify the evidence.

Determine whether the answer is GOOD, PARTIAL,
IRRELEVANT, or NO_KNOWLEDGE.

Pay special attention to whether the candidate has
actually answered the question.

Do not blindly accept semantic matches.

Return every required field.

Return only valid JSON.
"""

        response = await self.client.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        evaluation_data = self._parse_response(response)

        if not isinstance(evaluation_data, dict):
            raise ValueError(
                "AI response must be a JSON object."
            )

        evaluation_data = self._normalize_response(
            evaluation_data
        )

        evaluation_data["evidence"] = self.validate_evidence(
            evaluation_data["evidence"],
            candidate_answer
        )

        try:

            return AIEvaluation.model_validate(
                evaluation_data
            )

        except Exception as error:

            raise ValueError(
                f"AI evaluation validation failed: {error}"
            ) from error

    # --------------------------------------------------
    # NORMALIZE AI RESPONSE
    # --------------------------------------------------

    @staticmethod
    def _normalize_response(data: dict) -> dict:

        score_fields = [
            "technical_correctness",
            "concept_coverage",
            "reasoning_quality",
            "communication_clarity"
        ]

        for field in score_fields:

            value = data.get(field)

            if value is None or value == "":
                data[field] = None
                continue

            try:

                if isinstance(value, bool):
                    raise ValueError(
                        "Boolean is not a score"
                    )

                score = int(value)

                if not 0 <= score <= 100:
                    raise ValueError(
                        "Score outside 0-100"
                    )

                data[field] = score

            except (ValueError, TypeError):

                data[field] = None

        # Normalize answer classification.
        classification = data.get(
            "answer_classification",
            "PARTIAL"
        )

        if isinstance(classification, str):
            classification = classification.strip().upper()
        else:
            classification = "PARTIAL"

        allowed_classifications = {
            "GOOD",
            "PARTIAL",
            "IRRELEVANT",
            "NO_KNOWLEDGE"
        }

        if classification not in allowed_classifications:
            classification = "PARTIAL"

        data["answer_classification"] = classification

        # Normalize list fields.
        list_fields = [
            "matched_concepts",
            "missing_concepts",
            "incorrect_statements",
            "evidence",
            "strengths",
            "improvement_areas"
        ]

        for field in list_fields:

            value = data.get(field, [])

            if not isinstance(value, list):
                value = []

            data[field] = [
                str(item)
                for item in value
                if isinstance(item, (str, int, float))
                and not isinstance(item, bool)
            ]

        # Normalize feedback.
        feedback = data.get("overall_feedback")

        if not isinstance(feedback, str) or not feedback.strip():

            data["overall_feedback"] = (
                "AI evaluation was incomplete. "
                "Manual review is recommended."
            )

        # Normalize confidence.
        confidence = data.get("confidence")

        if confidence not in ["low", "medium", "high"]:
            data["confidence"] = "low"

        return data

    # --------------------------------------------------
    # PARSE AI JSON RESPONSE
    # --------------------------------------------------

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():

            raise ValueError(
                "AI returned an empty response."
            )

        cleaned = response.strip()

        if cleaned.startswith("```"):

            cleaned = cleaned.replace(
                "```json", "", 1
            )

            cleaned = cleaned.replace(
                "```", ""
            )

        try:

            result = json.loads(cleaned)

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            pass

        print("Warning: Attempting JSON repair...")

        try:

            result = repair_json(
                cleaned,
                return_objects=True
            )

            if isinstance(result, dict):
                return result

        except Exception as error:

            raise ValueError(
                f"Unable to repair AI response: {error}"
            ) from error

        raise ValueError(
            "AI response could not be converted into JSON."
        )

    # --------------------------------------------------
    # VALIDATE EVIDENCE
    # --------------------------------------------------

    @staticmethod
    def validate_evidence(
        evidence: list[str],
        candidate_answer: str
    ) -> list[str]:

        validated = []

        normalized_answer = " ".join(
            candidate_answer.split()
        ).casefold()

        for item in evidence:

            normalized_quote = " ".join(
                item.split()
            ).casefold()

            if (
                normalized_quote
                and normalized_quote in normalized_answer
            ):

                validated.append(item)

        return validated
