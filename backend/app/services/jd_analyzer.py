
import json
import re
from typing import Any

from json_repair import repair_json

from app.services.openrouter_client import OpenRouterClient


class JDAnalyzer:
    """
    Analyzes a job description using OpenRouter.

    Extracts:
    - Job title and seniority
    - Required and preferred skills
    - Technical competencies
    - Responsibilities
    - Experience requirements
    - Interview focus areas

    All extracted information must be grounded in the
    supplied job description.
    """

    def __init__(self):
        self.client = OpenRouterClient()

    async def analyze(
        self,
        job_role: str,
        job_description: str,
    ) -> dict[str, Any]:

        if not job_role or not job_role.strip():
            raise ValueError("Job role cannot be empty.")

        if not job_description or not job_description.strip():
            raise ValueError("Job description cannot be empty.")

        system_prompt = """
You are an expert technical recruiter and job description analyst.

Your task is to analyze the supplied job description and extract
structured interview requirements.

STRICT RULES:

1. Use only information supported by the supplied job description.
2. Do not invent technologies, skills, responsibilities or experience.
3. Separate explicitly required skills from preferred skills.
4. Identify technical and non-technical competencies.
5. Extract responsibilities as concise statements.
6. Identify seniority only when supported by the description.
7. If experience requirements are missing, return null.
8. If a category is not mentioned, return an empty array.
9. Do not infer requirements merely from the job title.
10. Return only a valid JSON object.

REQUIRED JSON STRUCTURE:

{
    "job_title": "Job title",
    "seniority": "entry-level",
    "experience_requirement": null,
    "required_skills": [],
    "preferred_skills": [],
    "technical_competencies": [],
    "soft_skills": [],
    "responsibilities": [],
    "interview_focus_areas": [],
    "job_summary": "Short summary of the job description"
}

For seniority, use one of:
- intern
- entry-level
- junior
- mid-level
- senior
- lead
- manager
- unknown

Each array must contain concise strings.

Do not include markdown fences or explanations.
"""

        user_prompt = f"""
Analyze this job description.

JOB ROLE:
{job_role.strip()}

JOB DESCRIPTION:
{job_description.strip()}

Return the structured JSON object only.
"""

        response = await self.client.generate_json_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2500,
            temperature=0.1,
        )

        data = self._parse_response(response)

        return self._validate_analysis(data, job_role)

    # ========================================================
    # JSON PARSING
    # ========================================================

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():
            raise ValueError("JD analyzer returned an empty response.")

        cleaned = response.strip()

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
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
            raise ValueError("JD analyzer returned invalid JSON.")

        return result

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_analysis(
        data: dict,
        job_role: str,
    ) -> dict:

        allowed_seniority = {
            "intern",
            "entry-level",
            "junior",
            "mid-level",
            "senior",
            "lead",
            "manager",
            "unknown",
        }

        seniority = str(
            data.get("seniority", "unknown")
        ).lower().strip()

        if seniority not in allowed_seniority:
            seniority = "unknown"

        def clean_list(key: str) -> list[str]:
            value = data.get(key, [])

            if not isinstance(value, list):
                return []

            return list(dict.fromkeys(
                item.strip()
                for item in value
                if isinstance(item, str) and item.strip()
            ))

        experience = data.get("experience_requirement")

        if not isinstance(experience, str):
            experience = None
        else:
            experience = experience.strip() or None

        summary = data.get("job_summary", "")

        if not isinstance(summary, str):
            summary = ""

        job_title = data.get("job_title", job_role)

        if not isinstance(job_title, str) or not job_title.strip():
            job_title = job_role

        analysis = {
            "job_title": job_title.strip(),
            "seniority": seniority,
            "experience_requirement": experience,
            "required_skills": clean_list("required_skills"),
            "preferred_skills": clean_list("preferred_skills"),
            "technical_competencies": clean_list(
                "technical_competencies"
            ),
            "soft_skills": clean_list("soft_skills"),
            "responsibilities": clean_list("responsibilities"),
            "interview_focus_areas": clean_list(
                "interview_focus_areas"
            ),
            "job_summary": summary.strip(),
        }

        if not (
            analysis["required_skills"]
            or analysis["preferred_skills"]
            or analysis["technical_competencies"]
            or analysis["responsibilities"]
        ):
            raise ValueError(
                "JD analysis did not identify sufficient job requirements."
            )

        return analysis
