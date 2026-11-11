
import asyncio
import json

from app.services.resume_analyzer import ResumeAnalyzer


RESUME = """
MCA graduate specializing in Data Science and Analytics.

Skills:
Python, SQL, Excel, Power BI, Pandas, NumPy.

Internships:
Python Intern at Nainital Institute of Technology.
Web Development Intern at Anonic Technologies.

Projects:
AI Data Analyst Web Application using Django and Pandas.
GitPro - GitHub Analytics Platform using GitHub APIs.
CareerSphere AI 2.0 - AI-powered career recommendation platform.

Education:
Master of Computer Applications.
"""


async def main():

    analyzer = ResumeAnalyzer()

    result = await analyzer.analyze(
        candidate_name="Test Candidate",
        resume_text=RESUME,
        job_role="Business Analyst",
        job_description="""
        We are hiring a Business Analyst.

        Required skills:
        SQL, Excel, Power BI, business reporting,
        data analysis, stakeholder communication.
        """,
    )

    print("\nRESUME ANALYSIS RESULT\n")
    print(json.dumps(result, indent=4))

    print("\nCLASSIFICATION:")
    print(result["candidate_type"])

    print("\nBACKGROUND FOCUS:")
    print(
        result["interview_personalization"]["background_focus"]
    )


if __name__ == "__main__":
    asyncio.run(main())
