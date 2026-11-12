
import json
import re
from typing import Any

from json_repair import repair_json

from app.services.ai_provider_manager import AIProviderManager as OpenRouterClient

class ResumeAnalyzer:
    """
    Analyzes a candidate's resume during interview preparation.

    Determines whether the candidate is a fresher or experienced
    and extracts evidence about internships, projects, employment,
    education, and technical skills.

    This analysis is performed before the interview starts.
    """

    def __init__(self):
        self.client = OpenRouterClient()

    async def analyze(
        self,
        candidate_name: str,
        resume_text: str,
        job_role: str,
        job_description: str,
    ) -> dict[str, Any]:

        # Only reject a genuinely missing resume.
        # Short resumes are still sent for analysis.
        if not isinstance(resume_text, str) or not resume_text.strip():
            raise ValueError("Candidate resume is missing.")

        system_prompt = """
You are an expert technical recruiter and resume analyst.

Analyze the candidate's resume for the purpose of preparing
a personalized job interview.

Your analysis must be based ONLY on evidence explicitly present
in the supplied resume.

CANDIDATE CLASSIFICATION:

1. fresher:
   - No substantial full-time professional employment is evident.
   - May have academic projects, personal projects, or internships.
   - Internships alone do not automatically make someone experienced.
   - Use this classification when the available resume evidence
     reasonably supports a fresher profile.

2. experienced:
   - The resume provides evidence of professional employment
     in a full-time, contractual, or equivalent professional role.
   - Identify the actual roles, companies, responsibilities,
     and durations where available.

3. uncertain:
   - Use this when the available information is insufficient
     to reliably determine the candidate's background.
   - Do not assume that missing employment information means
     the candidate is a fresher.

IMPORTANT RULES:

- Distinguish internships from full-time employment.
- Distinguish academic projects from professional work.
- Extract only skills actually mentioned in the resume.
- Do not assume a candidate has a skill merely because it is
  required by the job description.
- Identify relevant projects and internships.
- Preserve meaningful project and employment details.
- Do not invent company names, dates, job titles, or achievements.
- Do not evaluate the candidate's answers; there are no answers yet.
- Return only valid JSON.

INSUFFICIENT RESUME INFORMATION:

- A short resume is not automatically invalid.
- Analyze whatever information is available, even if the resume
  contains only a few words or sentences.
- If the supplied information is insufficient to determine
  employment history, classify the candidate as "uncertain".
- Use low classification confidence when evidence is insufficient.
- Do not assume the candidate is a fresher simply because
  professional experience is not mentioned.
- Do not invent projects, internships, employment, or skills.
- Empty sections must remain empty when no evidence is available.
- If the resume only mentions a technical skill or job title
  without supporting employment evidence, do not infer
  professional experience from that information alone.

REQUIRED JSON STRUCTURE:

{
  "candidate_type": "fresher",
  "classification_confidence": "high",
  "classification_reason": "Evidence-based explanation",
  "total_professional_experience": "No professional experience stated",
  "professional_experience": [
    {
      "job_title": "",
      "company": "",
      "duration": "",
      "responsibilities": []
    }
  ],
  "internships": [
    {
      "role": "",
      "company": "",
      "duration": "",
      "responsibilities": []
    }
  ],
  "projects": [
    {
      "name": "",
      "description": "",
      "technologies": [],
      "contributions": []
    }
  ],
  "education": [],
  "technical_skills": [],
  "soft_skills": [],
  "relevant_resume_highlights": [],
  "interview_personalization": {
    "background_focus": "internships_and_projects",
    "project_topics": [],
    "experience_topics": [],
    "technical_topics": []
  }
}

Allowed candidate_type:
- fresher
- experienced
- uncertain

Allowed classification_confidence:
- high
- medium
- low

For background_focus use:
- internships_and_projects
- professional_experience
- clarification_required

If a section has no evidence, return an empty array.
Do not fabricate information to fill the structure.
"""

        user_prompt = f"""
CANDIDATE NAME:
{candidate_name}

JOB ROLE:
{job_role}

JOB DESCRIPTION:
{job_description}

CANDIDATE RESUME:
{resume_text}

Analyze the resume and prepare structured information
for generating a personalized interview.

Determine whether the candidate is a fresher or experienced
based on the resume evidence, not the job description.

If the resume contains insufficient information, classify
the candidate as uncertain instead of inventing details.

Return only the JSON object.
"""

        response = await self.client.generate_json_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4500,
            temperature=0.1,
        )

        data = self._parse_response(response)

        return self._validate_analysis(data)

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():
            raise ValueError(
                "Resume analyzer returned an empty response."
            )

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
            raise ValueError(
                "Resume analyzer returned invalid JSON."
            )

        return result

    @staticmethod
    def _clean_list(value: Any) -> list:

        if not isinstance(value, list):
            return []

        cleaned = []

        for item in value:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())

            elif isinstance(item, dict):
                cleaned.append(item)

        return cleaned

    @classmethod
    def _validate_analysis(cls, data: dict) -> dict:

        candidate_type = str(
            data.get("candidate_type", "uncertain")
        ).lower().strip()

        if candidate_type not in {
            "fresher",
            "experienced",
            "uncertain",
        }:
            candidate_type = "uncertain"

        confidence = str(
            data.get("classification_confidence", "low")
        ).lower().strip()

        if confidence not in {"high", "medium", "low"}:
            confidence = "low"

        background = data.get(
            "interview_personalization",
            {},
        )

        if not isinstance(background, dict):
            background = {}

        background_focus = background.get("background_focus")

        allowed_focus = {
            "internships_and_projects",
            "professional_experience",
            "clarification_required",
        }

        if background_focus not in allowed_focus:
            background_focus = "clarification_required"

        # Do not allow an unsupported classification to drive
        # a specific candidate interview branch.
        if candidate_type == "uncertain":
            background_focus = "clarification_required"

        elif candidate_type == "fresher":
            background_focus = "internships_and_projects"

        elif candidate_type == "experienced":
            background_focus = "professional_experience"

        total_experience = data.get(
            "total_professional_experience",
            "Not specified",
        )

        if not isinstance(total_experience, str):
            total_experience = "Not specified"

        professional_experience = cls._clean_list(
            data.get("professional_experience")
        )

        internships = cls._clean_list(
            data.get("internships")
        )

        projects = cls._clean_list(
            data.get("projects")
        )

        education = cls._clean_list(
            data.get("education")
        )

        technical_skills = cls._clean_list(
            data.get("technical_skills")
        )

        soft_skills = cls._clean_list(
            data.get("soft_skills")
        )

        highlights = cls._clean_list(
            data.get("relevant_resume_highlights")
        )

        project_topics = cls._clean_list(
            background.get("project_topics")
        )

        experience_topics = cls._clean_list(
            background.get("experience_topics")
        )

        technical_topics = cls._clean_list(
            background.get("technical_topics")
        )

        return {
            "candidate_type": candidate_type,
            "classification_confidence": confidence,
            "classification_reason": str(
                data.get("classification_reason", "")
            ),
            "total_professional_experience": total_experience,
            "professional_experience": professional_experience,
            "internships": internships,
            "projects": projects,
            "education": education,
            "technical_skills": technical_skills,
            "soft_skills": soft_skills,
            "relevant_resume_highlights": highlights,
            "interview_personalization": {
                "background_focus": background_focus,
                "project_topics": project_topics,
                "experience_topics": experience_topics,
                "technical_topics": technical_topics,
            },
        }
