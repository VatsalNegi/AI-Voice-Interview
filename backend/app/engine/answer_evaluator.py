
import re


class AnswerEvaluator:

    STOP_WORDS = {
        "is", "are", "the", "a", "an", "and", "or",
        "to", "of", "for", "in", "on", "with", "does",
        "do", "can", "be", "it", "that", "this",
        "i", "my", "me", "have", "has", "had",
        "was", "were", "been", "being", "we", "our",
        "they", "their", "he", "she", "you", "your",
        "from", "by", "as", "at", "after", "before"
    }

    CONCEPT_ALIASES = {

        # ==========================================
        # EXPERIENCE STAGE
        # ==========================================

        "responsibilities": [
            "responsibilities",
            "responsible for",
            "job duties",
            "tasks assigned",
            "my role involved",
            "my tasks included",
            "handled the responsibility",
            "managed the development",
            "worked on"
        ],

        
"technologies_used": [
    "technology stack",
    "tech stack",
    "technologies used",
    "technologies i used",
    "main technologies i used",
    "technology i used",
    "worked with python",
    "worked with fastapi",
    "used python",
    "used fastapi",
    "used react",
    "used javascript",
    "used sql",
    "used postgresql",
    "used mongodb",
    "developed using python",
    "built using fastapi",
    "python for backend development",
    "fastapi for building rest apis",
    "postgresql for database management",
    "using python and fastapi"
],


        
"contribution": [
    "my contribution",
    "my personal contribution",
    "personal contribution",
    "my contribution was",
    "i contributed",
    "i implemented",
    "i developed",
    "i built",
    "i created",
    "i designed",
    "i integrated",
    "i was responsible for developing",
    "i personally developed",
    "personally developed",
    "designing and implementing",
    "developing the answer evaluation logic",
    "integrating the decision engine"
],


        "challenges": [
            "challenges",
            "main challenge",
            "biggest challenge",
            "technical challenge",
            "challenges faced",
            "problem i faced",
            "problems i faced",
            "difficulty i faced",
            "issue i encountered",
            "obstacle i encountered",
            "the challenge was",
            "one challenge was"
        ],

        "outcomes": [
            "outcomes",
            "results",
            "achievements",
            "improvements",
            "the outcome was",
            "as a result",
            "the result was",
            "resulting in",
            "this improved",
            "this helped",
            "successfully completed",
            "successfully developed",
            "delivered the project",
            "achieved the result",
            "reduced processing time"
        ],

        # ==========================================
        # INTRODUCTION STAGE
        # ==========================================

        "education": [
            "MCA",
            "BCA",
            "BTech",
            "B Tech",
            "MTech",
            "bachelor degree",
            "master degree",
            "graduation",
            "post graduation",
            "computer science degree",
            "university",
            "college",
            "studied",
            "completed my degree",
            "pursuing my degree"
        ],

        "technical_skills": [
            "Python",
            "Java",
            "JavaScript",
            "C++",
            "C",
            "React",
            "FastAPI",
            "Django",
            "Flask",
            "Node.js",
            "Express",
            "SQL",
            "MySQL",
            "PostgreSQL",
            "MongoDB",
            "machine learning",
            "artificial intelligence",
            "HTML",
            "CSS",
            "programming",
            "backend development",
            "frontend development",
            "REST API"
        ],

        "experience": [
            "professional experience",
            "technical experience",
            "have experience with",
            "experience in",
            "worked on a project",
            "worked with",
            "internship",
            "hands on experience",
            "practical experience",
            "developed applications"
        ],

        "projects": [
            "project",
            "projects",
            "application",
            "software system",
            "developed a system",
            "built an application",
            "created an application"
        ],

        "career_interests": [
            "interested in",
            "career goal",
            "career goals",
            "career interest",
            "want to work",
            "want to become",
            "passionate about",
            "looking to",
            "focused on",
            "focus on",
            "aspire to"
        ],

        # ==========================================
        # PROJECT UNDERSTANDING
        # ==========================================

        "problem_statement": [
            "problem statement",
            "problem it solves",
            "problem being solved",
            "issue it addresses",
            "main problem",
            "purpose of the project",
            "objective of the project",
            "problem it addresses"
        ],

        "architecture": [
            "architecture",
            "system architecture",
            "application architecture",
            "overall design",
            "system design",
            "frontend and backend",
            "client server architecture",
            "frontend communicates with backend",
            "components communicate"
        ],

        "technology_stack": [
            "technology stack",
            "tech stack",
            "technologies used",
            "built using",
            "developed using",
            "implemented using",
            "python",
            "fastapi",
            "react",
            "javascript",
            "postgresql",
            "mongodb"
        ],

        
"personal_contribution": [
    "personal contribution",
    "my contribution",
    "my personal contribution",
    "my role",
    "my role was",
    "i was responsible for",
    "i personally designed",
    "i personally developed",
    "i personally implemented",
    "i designed",
    "i developed",
    "i implemented",
    "i built",
    "i created",
    "i integrated",
    "my responsibility was",
    "my responsibilities included"
],


        "implementation": [
            "implementation",
            "implemented",
            "how it works",
            "development process",
            "developed the system",
            "integrated",
            "built the application",
            "workflow",
            "document chunking",
            "embedding generation",
            "semantic search"
        ],

        # ==========================================
        # PYTHON FUNDAMENTALS
        # ==========================================

        "list is mutable": [
            "list is mutable",
            "lists are mutable",
            "list can be modified",
            "list can be changed",
            "mutable list"
        ],

        "tuple is immutable": [
            "tuple is immutable",
            "tuples are immutable",
            "tuple cannot be modified",
            "tuple cannot be changed",
            "immutable tuple"
        ],

        
"list supports modification": [
    "list supports modification",
    "list can be modified",
    "list can be changed",
    "lists can be modified",
    "can modify a list",
    "can update list elements",
    "change an existing element",
    "append new elements",
    "remove elements from a list",
    "add remove or modify elements",
    "mutable and can be modified",
    "mutable meaning it can be modified",
    "we can modify it",
    "modify it after creation",
    "adding removing or updating elements",
    "adding removing and updating elements",
    "add remove or update elements",
    "modify list elements"
],


        "tuple does not support item reassignment": [
            "tuple does not support item reassignment",
            "cannot reassign tuple items",
            "cannot change tuple elements",
            "tuple items cannot be reassigned",
            "tuple is immutable",
            "raises a typeerror"
        ],

        "square brackets for lists": [
            "square brackets for lists",
            "lists use square brackets",
            "list uses square brackets",
            "square brackets",
            "list is written using brackets"
        ],

        "parentheses for tuples": [
            "parentheses for tuples",
            "tuples use parentheses",
            "tuple uses parentheses",
            "tuple is written using parentheses"
        ],

        # ==========================================
        # FASTAPI / BACKEND DEVELOPMENT
        # ==========================================

        "HTTP methods": [
            "http methods",
            "get request",
            "post request",
            "put request",
            "delete request",
            "request method"
        ],

        "route matching": [
            "route matching",
            "matches the request",
            "matches the route",
            "url to the appropriate route",
            "endpoint routing",
            "request url"
        ],

        "request validation": [
            "request validation",
            "validates incoming data",
            "validating request data",
            "validates the request",
            "input validation"
        ],

        "Pydantic": [
            "pydantic",
            "pydantic model",
            "pydantic models"
        ],

        "response serialization": [
            "response serialization",
            "serializes the response",
            "serialize the response",
            "converts the response into json",
            "response into json"
        ],

        # ==========================================
        # PROBLEM SOLVING
        # ==========================================

        "identify bottleneck": [
            "identify the bottleneck",
            "find the bottleneck",
            "identify performance issues",
            "find the performance bottleneck",
            "locate the bottleneck"
        ],

        "logging and monitoring": [
            "logging and monitoring",
            "application monitoring",
            "monitoring tools",
            "application logs",
            "performance metrics",
            "logs and metrics"
        ],

        "database query optimization": [
            "database query optimization",
            "optimize database queries",
            "slow database queries",
            "database indexing",
            "add database indexes",
            "query optimization"
        ],

        "caching": [
            "caching",
            "redis cache",
            "cache frequently accessed data",
            "cache repeated requests",
            "redis caching"
        ],

        "asynchronous processing": [
            "asynchronous processing",
            "async processing",
            "async operations",
            "asynchronous operations",
            "async programming"
        ],

        "load balancing": [
            "load balancing",
            "load balancer",
            "distribute traffic",
            "distribute incoming requests",
            "traffic distribution"
        ],

        "scaling": [
            "horizontal scaling",
            "vertical scaling",
            "scale horizontally",
            "scale vertically",
            "add more application instances",
            "scale the application"
        ]
    }

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text before matching."""

        text = text.lower()
        text = re.sub(r"[^a-z0-9+#]+", " ", text)

        return " ".join(text.split())

    @staticmethod
    def split_sentences(text: str) -> list:
        """Split an answer into individual sentences."""

        sentences = re.split(
            r"(?<=[.!?])\s+",
            text.strip()
        )

        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]

    @staticmethod
    def contains_phrase(text: str, phrase: str) -> bool:
        """Match a complete normalized phrase."""

        normalized_text = AnswerEvaluator.normalize(text)
        normalized_phrase = AnswerEvaluator.normalize(phrase)

        if not normalized_phrase:
            return False

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_phrase)
            + r"(?![a-z0-9])"
        )

        return re.search(pattern, normalized_text) is not None

    @staticmethod
    def extract_evidence(answer_text: str, aliases: list) -> list:
        """Return sentences containing matching aliases."""

        sentences = AnswerEvaluator.split_sentences(
            answer_text
        )

        evidence = []

        for sentence in sentences:

            for alias in aliases:

                if AnswerEvaluator.contains_phrase(
                    sentence,
                    alias
                ):
                    evidence.append(sentence)
                    break

        return evidence

    @staticmethod
    def evaluate(answer_text: str, question: dict) -> dict:
        """
        Evaluate expected concept coverage using local
        phrase matching and supporting sentence extraction.

        This is not a semantic or correctness assessment.
        """

        expected_concepts = question.get(
            "expected_concepts",
            []
        )

        matched_concepts = []
        missing_concepts = []
        matched_evidence = {}
        evidence_confidence = {}

        for concept in expected_concepts:

            concept_key = concept.lower().strip()

            aliases = AnswerEvaluator.CONCEPT_ALIASES.get(
                concept_key,
                [concept]
            )

            evidence = AnswerEvaluator.extract_evidence(
                answer_text,
                aliases
            )

            if evidence:

                matched_concepts.append(concept)

                matched_evidence[concept] = evidence

                evidence_confidence[concept] = (
                    "strong"
                    if len(evidence) >= 2
                    else "moderate"
                )

            else:

                missing_concepts.append(concept)

        total_concepts = len(expected_concepts)

        coverage = (
            round(
                len(matched_concepts) / total_concepts * 100,
                2
            )
            if total_concepts
            else 0
        )

        return {
            "question_id": question.get("question_id"),
            "concept_coverage": coverage,
            "matched_concepts": matched_concepts,
            "missing_concepts": missing_concepts,
            "matched_evidence": matched_evidence,
            "evidence_confidence": evidence_confidence,
            "evaluation_method": "local_phrase_matching_with_evidence"
        }
