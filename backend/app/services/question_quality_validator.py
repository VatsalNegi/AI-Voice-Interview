
import re
import logging
from itertools import combinations


logger = logging.getLogger(__name__)


class QuestionQualityValidator:
    """
    Lightweight quality validation for generated interview questions.

    Checks:
    1. Technical question count.
    2. Competency diversity.
    3. Excessive lexical similarity.
    4. Question detail and clarity.
    5. JD competency coverage.

    This is a heuristic validator, not an embedding-based
    semantic similarity model.
    """

    EXPECTED_TECHNICAL_QUESTIONS = 4

    MIN_DISTINCT_COMPETENCIES = 3

    MAX_QUESTION_SIMILARITY = 0.82

    MIN_QUESTION_WORDS = 8

    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were",
        "be", "been", "being", "and", "or", "but",
        "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "as", "about", "into", "through",
        "your", "you", "we", "they", "their", "it",
        "this", "that", "these", "those", "what",
        "which", "when", "where", "why", "how",
        "can", "could", "would", "should", "will",
        "do", "does", "did", "have", "has", "had",
        "explain", "describe", "tell", "me",
        "please", "give", "example", "examples",
    }

    COMPETENCY_ALIASES = {
        "python": {
            "python",
            "python programming",
        },
        "backend": {
            "backend",
            "backend development",
            "server side development",
            "fastapi",
            "django",
            "flask",
            "node.js",
            "express",
        },
        "frontend": {
            "frontend",
            "frontend development",
            "front end development",
            "react",
            "javascript",
            "html",
            "css",
        },
        "database": {
            "database",
            "database management",
            "database design",
            "sql",
            "mysql",
            "postgresql",
            "mongodb",
        },
        "api": {
            "api",
            "api development",
            "rest api",
            "restful api",
            "web api",
            "api integration",
        },
        "authentication": {
            "authentication",
            "authorization",
            "jwt",
            "oauth",
            "security",
        },
        "version control": {
            "version control",
            "source control",
            "git",
            "github",
            "gitlab",
            "bitbucket",
        },
        "containerization": {
            "containerization",
            "docker",
            "kubernetes",
            "containers",
        },
        "cloud": {
            "cloud",
            "cloud computing",
            "aws",
            "azure",
            "gcp",
            "google cloud",
        },
        "ci/cd": {
            "ci cd",
            "continuous integration",
            "continuous deployment",
            "continuous delivery",
            "github actions",
            "jenkins",
        },
    }

    # --------------------------------------------------
    # PUBLIC VALIDATION METHOD
    # --------------------------------------------------

    @classmethod
    def validate(
        cls,
        questions: list[dict],
        jd_analysis: dict,
    ) -> dict:
        """
        Validate the technical portion of a generated
        interview question set.

        Returns a quality report when validation succeeds.

        Raises ValueError when critical quality checks fail.
        """

        if not isinstance(questions, list):
            raise ValueError(
                "Question quality validation received invalid input."
            )

        if not isinstance(jd_analysis, dict):
            raise ValueError(
                "JD analysis is invalid for quality validation."
            )

        technical_questions = [
            question
            for question in questions
            if isinstance(question, dict)
            and question.get("stage") == "technical_interview"
        ]

        if len(technical_questions) != cls.EXPECTED_TECHNICAL_QUESTIONS:
            raise ValueError(
                "Expected exactly "
                f"{cls.EXPECTED_TECHNICAL_QUESTIONS} technical questions, "
                f"but received {len(technical_questions)}."
            )

        # 1. Validate question detail.

        cls._validate_question_detail(
            technical_questions
        )

        # 2. Validate competency diversity.

        competencies = [
            question.get("competency", "")
            for question in technical_questions
        ]

        competency_groups = {
            cls._canonical_competency(value)
            for value in competencies
            if isinstance(value, str) and value.strip()
        }

        if len(competency_groups) < cls.MIN_DISTINCT_COMPETENCIES:
            raise ValueError(
                "Technical questions do not cover enough distinct "
                "competencies. Expected at least "
                f"{cls.MIN_DISTINCT_COMPETENCIES}, "
                f"received {len(competency_groups)}."
            )

        # 3. Validate lexical similarity between questions.

        similarity_report = cls._validate_similarity(
            technical_questions
        )

        # 4. Validate technical competency coverage.

        jd_coverage = cls._validate_jd_coverage(
            competencies,
            jd_analysis,
        )

        report = {
            "status": "passed",
            "technical_question_count": len(technical_questions),
            "distinct_competencies": sorted(competency_groups),
            "distinct_competency_count": len(competency_groups),
            "similarity_checks": similarity_report,
            "jd_competency_coverage": jd_coverage,
        }

        logger.info(
            "Question quality validation passed: "
            "technical_questions=%s distinct_competencies=%s",
            len(technical_questions),
            len(competency_groups),
        )

        return report

    # --------------------------------------------------
    # QUESTION DETAIL
    # --------------------------------------------------

    @classmethod
    def _validate_question_detail(
        cls,
        questions: list[dict],
    ) -> None:

        for index, question in enumerate(questions, 1):

            text = question.get("question", "")

            if not isinstance(text, str):
                raise ValueError(
                    f"Technical question {index} has invalid text."
                )

            words = cls._tokenize(text)

            if len(words) < cls.MIN_QUESTION_WORDS:
                raise ValueError(
                    f"Technical question {index} is too short "
                    "to assess technical knowledge properly."
                )

            competency = question.get("competency")

            if (
                not isinstance(competency, str)
                or not competency.strip()
            ):
                raise ValueError(
                    f"Technical question {index} has no competency."
                )

            concepts = question.get("expected_concepts")

            if not isinstance(concepts, list) or len(concepts) < 2:
                raise ValueError(
                    f"Technical question {index} has insufficient "
                    "expected concepts."
                )

    # --------------------------------------------------
    # COMPETENCY NORMALIZATION
    # --------------------------------------------------

    @classmethod
    def _canonical_competency(
        cls,
        competency: str,
    ) -> str:

        normalized = cls._normalize(competency)

        for canonical, aliases in cls.COMPETENCY_ALIASES.items():

            normalized_aliases = {
                cls._normalize(alias)
                for alias in aliases
            }

            if normalized == cls._normalize(canonical):
                return canonical

            if normalized in normalized_aliases:
                return canonical

        return normalized

    # --------------------------------------------------
    # QUESTION SIMILARITY
    # --------------------------------------------------

    @classmethod
    def _validate_similarity(
        cls,
        questions: list[dict],
    ) -> list[dict]:

        results = []

        for (index_a, question_a), (index_b, question_b) in combinations(
            enumerate(questions, 1),
            2,
        ):

            tokens_a = cls._tokenize(
                question_a.get("question", "")
            )

            tokens_b = cls._tokenize(
                question_b.get("question", "")
            )

            similarity = cls._jaccard_similarity(
                tokens_a,
                tokens_b,
            )

            results.append({
                "question_a": index_a,
                "question_b": index_b,
                "similarity": round(similarity, 3),
            })

            if similarity >= cls.MAX_QUESTION_SIMILARITY:

                raise ValueError(
                    "Technical questions "
                    f"{index_a} and {index_b} are excessively similar. "
                    f"Similarity score: {similarity:.3f}"
                )

        return results

    @staticmethod
    def _jaccard_similarity(
        tokens_a: set[str],
        tokens_b: set[str],
    ) -> float:

        if not tokens_a or not tokens_b:
            return 0.0

        union = tokens_a | tokens_b
        intersection = tokens_a & tokens_b

        return len(intersection) / len(union)

    # --------------------------------------------------
    # JD COMPETENCY COVERAGE
    # --------------------------------------------------

    @classmethod
    def _validate_jd_coverage(
        cls,
        competencies: list[str],
        jd_analysis: dict,
    ) -> dict:

        jd_text = []

        fields = (
            "required_skills",
            "preferred_skills",
            "technical_competencies",
            "responsibilities",
            "interview_focus_areas",
        )

        for field in fields:

            value = jd_analysis.get(field, [])

            jd_text.extend(
                cls._collect_strings(value)
            )

        jd_normalized = cls._normalize(
            " ".join(jd_text)
        )

        matched = []
        unmatched = []

        for competency in competencies:

            canonical = cls._canonical_competency(
                competency
            )

            aliases = cls.COMPETENCY_ALIASES.get(
                canonical,
                {competency},
            )

            found = any(
                cls._contains_phrase(
                    jd_normalized,
                    cls._normalize(alias),
                )
                for alias in aliases
            )

            if found:
                matched.append(competency)
            else:
                unmatched.append(competency)

        # The existing InterviewPreparationService performs
        # stricter JD grounding validation. This report is an
        # additional quality signal, not a replacement for it.

        return {
            "matched": matched,
            "unmatched": unmatched,
            "matched_count": len(matched),
            "total_count": len(competencies),
        }

    # --------------------------------------------------
    # TEXT UTILITIES
    # --------------------------------------------------

    @classmethod
    def _tokenize(
        cls,
        value: str,
    ) -> set[str]:

        if not isinstance(value, str):
            return set()

        tokens = set(
            re.findall(
                r"[a-z0-9+#.]+",
                value.casefold(),
            )
        )

        return {
            token
            for token in tokens
            if len(token) > 1
            and token not in cls.STOP_WORDS
        }

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        if not isinstance(value, str):
            return ""

        return " ".join(
            re.sub(
                r"[^a-z0-9+#.]",
                " ",
                value.casefold(),
            ).split()
        )

    @classmethod
    def _contains_phrase(
        cls,
        text: str,
        phrase: str,
    ) -> bool:

        if not text or not phrase:
            return False

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(phrase)
            + r"(?![a-z0-9])"
        )

        return re.search(pattern, text) is not None

    @classmethod
    def _collect_strings(
        cls,
        value,
    ) -> list[str]:

        results = []

        if isinstance(value, str):

            if value.strip():
                results.append(value.strip())

        elif isinstance(value, dict):

            for nested in value.values():
                results.extend(
                    cls._collect_strings(nested)
                )

        elif isinstance(value, (list, tuple, set)):

            for nested in value:
                results.extend(
                    cls._collect_strings(nested)
                )

        return results
