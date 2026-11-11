
import asyncio
import json

from app.services.jd_analyzer import JDAnalyzer


async def main():

    analyzer = JDAnalyzer()

    job_role = "Python Full Stack Developer Intern"

    job_description = """
We are looking for a Python Full Stack Developer Intern.

Required skills:
- Python
- FastAPI
- React.js
- JavaScript
- PostgreSQL
- REST API development

Responsibilities:
- Develop backend APIs using FastAPI.
- Build frontend components using React.
- Integrate frontend and backend services.
- Work with PostgreSQL databases.
- Debug and test application functionality.

Preferred:
- Docker
- Git
- AWS
- Basic understanding of Generative AI.

Candidates should have good communication skills
and problem-solving abilities.
"""

    result = await analyzer.analyze(
        job_role=job_role,
        job_description=job_description,
    )

    print("\n========== JD ANALYSIS ==========\n")
    print(json.dumps(result, indent=4))

    print("\n========== VALIDATION ==========\n")

    assert isinstance(result["required_skills"], list)
    assert isinstance(result["technical_competencies"], list)
    assert isinstance(result["responsibilities"], list)

    print("JD analysis test passed!")


if __name__ == "__main__":
    asyncio.run(main())
