
import asyncio
import json

from app.services.jd_analyzer import JDAnalyzer
from app.services.jd_question_generator import JDQuestionGenerator


async def main():

    job_role = "Python Full Stack Developer Intern"

    job_description = """
We are hiring a Python Full Stack Developer Intern.

Required skills:
Python, FastAPI, React.js, JavaScript,
PostgreSQL and REST APIs.

Responsibilities:
Develop backend APIs, create frontend components,
integrate APIs with React, work with PostgreSQL,
debug and test applications.

Preferred skills:
Docker, Git, AWS and basic Generative AI.

Good communication and problem-solving skills required.
"""

    analyzer = JDAnalyzer()
    generator = JDQuestionGenerator()

    print("Analyzing job description...")

    analysis = await analyzer.analyze(
        job_role=job_role,
        job_description=job_description,
    )

    print("Generating interview questions...")

    questions = await generator.generate_questions(
        job_role=job_role,
        job_description=job_description,
        jd_analysis=analysis,
        count=8,
    )

    print("\n========== GENERATED QUESTIONS ==========\n")

    for question in questions:
        print(json.dumps(question, indent=2))
        print("-" * 60)

    assert len(questions) == 8
    assert all(
        question["sequence_number"] == index
        for index, question in enumerate(questions, start=1)
    )

    print("\nJD question generation test passed!")


if __name__ == "__main__":
    asyncio.run(main())
