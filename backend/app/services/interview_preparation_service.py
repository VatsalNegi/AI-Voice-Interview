
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import Interview, InterviewQuestion
from app.db.session import get_db_context

from app.services.jd_analyzer import JDAnalyzer
from app.services.jd_question_generator import JDQuestionGenerator
from app.services.resume_analyzer import ResumeAnalyzer
from app.services.question_quality_validator import (
    QuestionQualityValidator,
)


logger = logging.getLogger(__name__)


class InterviewPreparationService:
    """Prepare and persist a complete staged interview before it starts."""

    DEFAULT_QUESTION_COUNT = 10

    ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}

    EXPECTED_STAGES = (
        ["introduction"]
        + ["candidate_background"] * 2
        + ["technical_interview"] * 4
        + ["behavioral_interview"] * 2
        + ["closing"]
    )

    JD_REQUIREMENT_FIELDS = (
        "required_skills",
        "preferred_skills",
        "technical_competencies",
        "soft_skills",
        "responsibilities",
        "interview_focus_areas",
    )

    # Equivalent terminology for competency grounding.
    # An alias is accepted only when its equivalent appears in the JD.

    JD_COMPETENCY_ALIASES = {
        "version control": {
            "version control",
            "source control",
            "git",
            "github",
            "gitlab",
            "bitbucket",
        },
        "api development": {
            "api development",
            "rest api",
            "restful api",
            "web api",
            "api integration",
        },
        "database management": {
            "database management",
            "database design",
            "sql",
            "mysql",
            "postgresql",
            "mongodb",
        },
        "frontend development": {
            "frontend development",
            "front end development",
            "html",
            "css",
            "javascript",
            "react",
        },
        "backend development": {
            "backend development",
            "back end development",
            "server side development",
            "node.js",
            "express",
            "fastapi",
            "django",
            "flask",
        },
        "cloud computing": {
            "cloud computing",
            "aws",
            "azure",
            "google cloud",
            "gcp",
        },
        "containerization": {
            "containerization",
            "docker",
            "kubernetes",
            "containers",
        },
        "ci cd": {
            "ci cd",
            "continuous integration",
            "continuous deployment",
            "continuous delivery",
            "github actions",
            "jenkins",
        },
    }

    # ==================================================
    # MAIN PREPARATION WORKFLOW
    # ==================================================

    @classmethod
    async def run(cls, session_id: str) -> None:

        try:

            # ==========================================
            # 1. LOAD INTERVIEW AND MARK PROCESSING
            # ==========================================

            with get_db_context() as db:

                interview = (
                    db.query(Interview)
                    .filter(
                        Interview.session_id == session_id
                    )
                    .first()
                )

                if interview is None:
                    logger.error(
                        "Interview not found: %s",
                        session_id,
                    )
                    return

                if interview.status != "not_started":
                    logger.warning(
                        "Preparation skipped for %s: status=%s",
                        session_id,
                        interview.status,
                    )
                    return

                if interview.preparation_status == "ready":
                    logger.info(
                        "Interview already prepared: %s",
                        session_id,
                    )
                    return

                candidate = interview.candidate

                candidate_name = (
                    candidate.candidate_name
                    if candidate
                    else "Candidate"
                )

                resume_text = (
                    (candidate.resume_text or "")
                    if candidate
                    else ""
                )

                job_role = interview.job_role
                job_description = interview.job_description or ""

                interview.preparation_status = "processing"
                interview.preparation_error = None
                interview.prepared_at = None
                interview.total_questions = 0
                interview.blueprint_metadata = None

                # Remove stale unasked questions only.
                # Preserve any question that has an answer.

                stale = (
                    db.query(InterviewQuestion)
                    .filter(
                        InterviewQuestion.interview_id == interview.id,
                        InterviewQuestion.question_type == "primary",
                        InterviewQuestion.asked_at.is_(None),
                    )
                    .all()
                )

                for record in stale:
                    if not record.answers:
                        db.delete(record)

                db.flush()

            # Database connection is released before LLM calls.

            if (
                not isinstance(job_role, str)
                or not job_role.strip()
            ):
                raise ValueError("Job role is missing.")

            if (
                not isinstance(job_description, str)
                or not job_description.strip()
            ):
                raise ValueError("Job description is missing.")

            # ==========================================
            # 2. ANALYZE CANDIDATE RESUME
            # ==========================================

            if resume_text.strip():

                logger.info(
                    "Starting resume analysis for session %s",
                    session_id,
                )

                resume_analyzer = ResumeAnalyzer()

                resume_analysis = await resume_analyzer.analyze(
                    candidate_name=candidate_name,
                    resume_text=resume_text,
                    job_role=job_role,
                    job_description=job_description,
                )

                resume_analysis_provider = (
                    resume_analyzer.client.last_provider or "unknown"
                )

            else:

                logger.warning(
                    "No resume supplied for session %s; "
                    "using uncertain branch",
                    session_id,
                )

                resume_analysis = cls._uncertain_resume_analysis()
                resume_analysis_provider = "not_applicable"

            if not isinstance(resume_analysis, dict):
                raise ValueError(
                    "Resume analyzer returned an invalid result."
                )

            candidate_type = resume_analysis.get(
                "candidate_type",
                "uncertain",
            )

            if candidate_type not in {
                "fresher",
                "experienced",
                "uncertain",
            }:
                raise ValueError(
                    "Resume analysis returned an unsupported "
                    "candidate classification."
                )

            logger.info(
                "Resume analysis completed: session=%s branch=%s provider=%s",
                session_id,
                candidate_type,
                resume_analysis_provider,
            )

            # ==========================================
            # 3. ANALYZE JOB DESCRIPTION
            # ==========================================

            logger.info(
                "Starting JD analysis for session %s",
                session_id,
            )

            jd_analyzer = JDAnalyzer()

            jd_analysis = await jd_analyzer.analyze(
                job_role=job_role,
                job_description=job_description,
            )

            jd_analysis_provider = (
                jd_analyzer.client.last_provider or "unknown"
            )

            if not isinstance(jd_analysis, dict):
                raise ValueError(
                    "JD analyzer returned an invalid result."
                )

            logger.info(
                "JD analysis completed for session %s provider=%s",
                session_id,
                jd_analysis_provider,
            )

            # ==========================================
            # 4. GENERATE COMPLETE STAGED BLUEPRINT
            # ==========================================

            logger.info(
                "Generating %s staged questions for session %s",
                cls.DEFAULT_QUESTION_COUNT,
                session_id,
            )

            question_generator = JDQuestionGenerator()

            questions = await question_generator.generate_questions(
                job_role=job_role,
                job_description=job_description,
                jd_analysis=jd_analysis,
                resume_analysis=resume_analysis,
                count=cls.DEFAULT_QUESTION_COUNT,
            )

            # Normalize generated text without changing
            # technical identifiers such as FastAPI or Node.js.

            questions = cls._normalize_generated_questions(
                questions
            )

            logger.info(
                "Generated question text normalization completed: "
                "session=%s",
                session_id,
            )

            question_generation_provider = (
                question_generator.client.last_provider or "unknown"
            )

            logger.info(
                "Question generation completed: session=%s provider=%s",
                session_id,
                question_generation_provider,
            )

            # ==========================================
            # 5. STRUCTURAL AND JD VALIDATION
            # ==========================================

            logger.info(
                "Validating generated questions: session=%s",
                session_id,
            )

            cls._validate_question_set(
                questions=questions,
                jd_analysis=jd_analysis,
                candidate_type=candidate_type,
                job_description=job_description,
            )

            logger.info(
                "Staged question validation passed for session %s",
                session_id,
            )

            # ==========================================
            # 5.1. QUESTION QUALITY VALIDATION
            # ==========================================

            logger.info(
                "Running question quality validation: session=%s",
                session_id,
            )

            quality_report = QuestionQualityValidator.validate(
                questions=questions,
                jd_analysis=jd_analysis,
            )

            logger.info(
                "Question quality validation passed: "
                "session=%s report=%s",
                session_id,
                quality_report,
            )

            # ==========================================
            # 6. PERSIST COMPLETE BLUEPRINT
            # ==========================================

            with get_db_context() as db:

                interview = (
                    db.query(Interview)
                    .filter(
                        Interview.session_id == session_id
                    )
                    .first()
                )

                if interview is None:
                    raise ValueError(
                        "Interview session was not found during persistence."
                    )

                if interview.status != "not_started":
                    raise ValueError(
                        "Interview status changed during preparation."
                    )

                if interview.preparation_status != "processing":
                    raise ValueError(
                        "Interview preparation state changed unexpectedly."
                    )

                active_question = (
                    db.query(InterviewQuestion)
                    .filter(
                        InterviewQuestion.interview_id == interview.id,
                        InterviewQuestion.asked_at.isnot(None),
                    )
                    .first()
                )

                if active_question is not None:
                    raise ValueError(
                        "Cannot replace questions after a question "
                        "has been activated."
                    )

                answered_question = (
                    db.query(InterviewQuestion)
                    .join(InterviewQuestion.answers)
                    .filter(
                        InterviewQuestion.interview_id == interview.id
                    )
                    .first()
                )

                if answered_question is not None:
                    raise ValueError(
                        "Cannot replace questions after an answer exists."
                    )

                old_questions = (
                    db.query(InterviewQuestion)
                    .filter(
                        InterviewQuestion.interview_id == interview.id,
                        InterviewQuestion.question_type == "primary",
                        InterviewQuestion.asked_at.is_(None),
                    )
                    .all()
                )

                for old in old_questions:
                    if not old.answers:
                        db.delete(old)

                # Save all validated questions.

                for question in questions:

                    question_record = InterviewQuestion(
                        interview_id=interview.id,
                        question_id=str(uuid4()),
                        question_text=question["question"],
                        competency=question["competency"],
                        difficulty=question["difficulty"],
                        question_type="primary",
                        sequence_number=question["sequence_number"],
                        expected_concepts=question["expected_concepts"],
                        estimated_time_seconds=question[
                            "estimated_time_seconds"
                        ],
                        asked_at=None,

                        metadata_snapshot={
                            "source": (
                                f"{question_generation_provider.lower()}"
                                "_staged_generation"
                            ),
                            "generation_provider": question_generation_provider,
                            "generation_strategy": (
                                "pre_generated_staged_branching"
                            ),
                            "stage": question["stage"],
                            "stage_label": question["stage_label"],
                            "candidate_branch": question[
                                "candidate_branch"
                            ],
                            "jd_competency": question["competency"],
                        },
                    )

                    db.add(question_record)

                prepared_at = datetime.now(timezone.utc)

                interview.total_questions = len(questions)

                interview.blueprint_metadata = {
                    "resume_analysis": resume_analysis,
                    "candidate_type": candidate_type,
                    "classification_confidence": (
                        resume_analysis.get(
                            "classification_confidence",
                            "low",
                        )
                    ),
                    "jd_analysis": jd_analysis,
                    "question_count": len(questions),
                    "stage_sequence": cls.EXPECTED_STAGES,

                    "provider_usage": {
                        "resume_analysis": resume_analysis_provider,
                        "jd_analysis": jd_analysis_provider,
                        "question_generation": question_generation_provider,
                    },

                    "generation_source": question_generation_provider,

                    "question_generation_strategy": (
                        "pre_generated_staged_branching"
                    ),

                    "live_llm_question_generation": False,

                    # New quality report.
                    "question_quality_report": quality_report,

                    "prepared_at": prepared_at.isoformat(),
                }

                interview.preparation_status = "ready"
                interview.preparation_error = None
                interview.prepared_at = prepared_at

                db.flush()

            logger.info(
                "Interview preparation successful: "
                "session=%s questions=%s branch=%s provider=%s",
                session_id,
                len(questions),
                candidate_type,
                question_generation_provider,
            )

        except Exception as error:

            logger.exception(
                "Interview preparation failed for session %s",
                session_id,
            )

            # ==========================================
            # 7. RECORD PREPARATION FAILURE
            # ==========================================

            try:

                with get_db_context() as db:

                    interview = (
                        db.query(Interview)
                        .filter(
                            Interview.session_id == session_id
                        )
                        .first()
                    )

                    if (
                        interview is not None
                        and interview.status == "not_started"
                    ):

                        interview.preparation_status = "failed"
                        interview.preparation_error = str(error)[:2000]
                        interview.prepared_at = None
                        interview.total_questions = 0
                        interview.blueprint_metadata = None

                        partial = (
                            db.query(InterviewQuestion)
                            .filter(
                                InterviewQuestion.interview_id == interview.id,
                                InterviewQuestion.question_type == "primary",
                                InterviewQuestion.asked_at.is_(None),
                            )
                            .all()
                        )

                        for question in partial:
                            if not question.answers:
                                db.delete(question)

            except Exception:

                logger.exception(
                    "Unable to persist preparation failure "
                    "for session %s",
                    session_id,
                )

    # ==================================================
    # FALLBACK FOR MISSING RESUME
    # ==================================================

    @staticmethod
    def _uncertain_resume_analysis() -> dict:

        return {
            "candidate_type": "uncertain",
            "classification_confidence": "low",
            "classification_reason": (
                "No resume was supplied; employment background "
                "cannot be determined."
            ),
            "total_professional_experience": "Not available",
            "professional_experience": [],
            "internships": [],
            "projects": [],
            "education": [],
            "technical_skills": [],
            "soft_skills": [],
            "relevant_resume_highlights": [],
            "interview_personalization": {
                "background_focus": "clarification_required",
                "project_topics": [],
                "experience_topics": [],
                "technical_topics": [],
            },
        }

    # ==================================================
    # GENERATED QUESTION TEXT NORMALIZATION
    # ==================================================

    @staticmethod
    def _clean_generated_text(value: str) -> str:

        if not isinstance(value, str):
            return value

        value = value.replace("\u00a0", " ")

        # Collapse whitespace and line breaks.
        value = re.sub(r"\s+", " ", value).strip()

        # Remove spaces before punctuation.
        value = re.sub(r"\s+([,;:!?])", r"\1", value)

        # Insert missing spaces after punctuation.
        value = re.sub(
            r"([,;:!?])(?=[A-Za-z0-9])",
            r"\1 ",
            value,
        )

        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _normalize_generated_questions(
        cls,
        questions: list[dict],
    ) -> list[dict]:

        if not isinstance(questions, list):
            return questions

        normalized_questions = []

        for question in questions:

            if not isinstance(question, dict):
                normalized_questions.append(question)
                continue

            normalized_question = dict(question)

            if isinstance(
                normalized_question.get("question"),
                str,
            ):
                normalized_question["question"] = (
                    cls._clean_generated_text(
                        normalized_question["question"]
                    )
                )

            concepts = normalized_question.get(
                "expected_concepts"
            )

            if isinstance(concepts, list):

                normalized_question["expected_concepts"] = [
                    cls._clean_generated_text(value)
                    if isinstance(value, str)
                    else value
                    for value in concepts
                ]

            normalized_questions.append(
                normalized_question
            )

        return normalized_questions

    # ==================================================
    # STRUCTURAL QUESTION VALIDATION
    # ==================================================

    @classmethod
    def _validate_question_set(
        cls,
        questions: list[dict],
        jd_analysis: dict,
        candidate_type: str,
        job_description: str = "",
    ) -> None:

        if (
            not isinstance(questions, list)
            or len(questions) != cls.DEFAULT_QUESTION_COUNT
        ):
            raise ValueError(
                f"Expected exactly {cls.DEFAULT_QUESTION_COUNT} "
                "staged questions."
            )

        if not isinstance(jd_analysis, dict):
            raise ValueError(
                "JD analysis must be a valid dictionary."
            )

        if candidate_type not in {
            "fresher",
            "experienced",
            "uncertain",
        }:
            raise ValueError("Invalid candidate branch.")

        # Collect JD requirements.

        jd_terms = []

        for field in cls.JD_REQUIREMENT_FIELDS:

            values = jd_analysis.get(field, [])

            jd_terms.extend(
                cls._collect_text_values(values)
            )

        if (
            isinstance(job_description, str)
            and job_description.strip()
        ):
            jd_terms.append(job_description.strip())

        jd_tokens = set()

        for term in jd_terms:
            jd_tokens.update(
                cls._meaningful_tokens(term)
            )

        logger.info(
            "JD grounding prepared: requirement_terms=%s meaningful_tokens=%s",
            len(jd_terms),
            len(jd_tokens),
        )

        if not jd_tokens:
            raise ValueError(
                "No usable JD requirements or meaningful JD tokens "
                "were found for competency validation."
            )

        seen_questions = set()

        for index, (question, expected_stage) in enumerate(
            zip(questions, cls.EXPECTED_STAGES),
            1,
        ):

            if not isinstance(question, dict):
                raise ValueError(
                    f"Question {index} is not a valid dictionary."
                )

            question_text = question.get("question")

            if (
                not isinstance(question_text, str)
                or len(question_text.strip()) < 15
            ):
                raise ValueError(
                    f"Question {index} has invalid question text."
                )

            normalized = cls._normalize(question_text)

            if normalized in seen_questions:
                raise ValueError(
                    f"Duplicate question detected at position {index}."
                )

            seen_questions.add(normalized)

            # Validate sequence.

            if question.get("sequence_number") != index:
                raise ValueError(
                    f"Question {index} has an invalid sequence number."
                )

            # Validate stage.

            if question.get("stage") != expected_stage:
                raise ValueError(
                    f"Question {index} must be in stage "
                    f"'{expected_stage}'."
                )

            # Validate candidate branch.

            branch = question.get("candidate_branch")

            required_branch = (
                candidate_type
                if expected_stage == "candidate_background"
                else "all"
            )

            if branch != required_branch:
                raise ValueError(
                    f"Question {index} must use candidate branch "
                    f"'{required_branch}'."
                )

            # Validate stage label.

            if (
                question.get("stage_label")
                != JDQuestionGenerator.STAGES[expected_stage]
            ):
                raise ValueError(
                    f"Question {index} has an invalid stage label."
                )

            # Validate competency.

            competency = question.get("competency")

            if (
                not isinstance(competency, str)
                or not competency.strip()
            ):
                raise ValueError(
                    f"Question {index} has no valid competency."
                )

            # Only technical questions must map to JD requirements.

            if expected_stage == "technical_interview":

                grounded = cls._is_competency_grounded(
                    competency=competency,
                    jd_terms=jd_terms,
                    jd_tokens=jd_tokens,
                )

                if not grounded:

                    logger.warning(
                        "JD competency mismatch: question=%s "
                        "competency=%r competency_tokens=%s",
                        index,
                        competency,
                        sorted(cls._meaningful_tokens(competency)),
                    )

                    raise ValueError(
                        f"Technical question {index} competency "
                        f"'{competency}' is not grounded in the JD."
                    )

            # Validate expected concepts.

            concepts = question.get("expected_concepts")

            if not isinstance(concepts, list):
                raise ValueError(
                    f"Question {index} has invalid expected concepts."
                )

            clean_concepts = [
                value.strip()
                for value in concepts
                if isinstance(value, str) and value.strip()
            ]

            if (
                not 2 <= len(clean_concepts) <= 5
                or len({
                    value.casefold()
                    for value in clean_concepts
                }) != len(clean_concepts)
            ):
                raise ValueError(
                    f"Question {index} must contain "
                    "2 to 5 unique expected concepts."
                )

            # Validate difficulty.

            if (
                question.get("difficulty")
                not in cls.ALLOWED_DIFFICULTIES
            ):
                raise ValueError(
                    f"Question {index} has invalid difficulty."
                )

            # Validate estimated time.

            duration = question.get("estimated_time_seconds")

            if (
                isinstance(duration, bool)
                or not isinstance(duration, int)
                or not 30 <= duration <= 300
            ):
                raise ValueError(
                    f"Question {index} has invalid estimated time."
                )

            # Validate question type.

            if question.get("question_type") != "primary":
                raise ValueError(
                    f"Question {index} must be a primary question."
                )

    # ==================================================
    # COMPETENCY GROUNDING
    # ==================================================

    @classmethod
    def _is_competency_grounded(
        cls,
        competency: str,
        jd_terms: list[str],
        jd_tokens: set[str],
    ) -> bool:
        """
        Check competency grounding using direct phrases,
        configured aliases and meaningful token overlap.
        """

        normalized_competency = cls._normalize(competency)

        if not normalized_competency:
            return False

        normalized_jd_terms = [
            cls._normalize(term)
            for term in jd_terms
            if isinstance(term, str) and term.strip()
        ]

        # 1. Direct phrase matching.

        for term in normalized_jd_terms:

            if cls._contains_phrase(
                term,
                normalized_competency,
            ):
                return True

        # 2. Alias matching.

        for canonical_name, aliases in cls.JD_COMPETENCY_ALIASES.items():

            normalized_aliases = {
                cls._normalize(alias)
                for alias in aliases
            }

            competency_belongs_to_group = (
                normalized_competency
                == cls._normalize(canonical_name)
                or normalized_competency in normalized_aliases
            )

            if not competency_belongs_to_group:
                continue

            for term in normalized_jd_terms:

                for alias in normalized_aliases:

                    if cls._contains_phrase(term, alias):
                        logger.debug(
                            "Competency alias matched: competency=%s "
                            "alias=%s",
                            competency,
                            alias,
                        )
                        return True

        # 3. Meaningful token overlap fallback.

        competency_tokens = cls._meaningful_tokens(
            normalized_competency
        )

        matched_tokens = competency_tokens.intersection(jd_tokens)

        if not matched_tokens:
            return False

        # Require at least half the competency's meaningful tokens.
        # For a one-token competency, one exact token is sufficient.

        required_matches = max(
            1,
            (len(competency_tokens) + 1) // 2,
        )

        return len(matched_tokens) >= required_matches

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

    # ==================================================
    # JD REQUIREMENT EXTRACTION
    # ==================================================

    @classmethod
    def _collect_text_values(cls, value) -> list[str]:
        """
        Recursively collect non-empty strings from JD JSON values.
        Supports strings, lists, tuples, sets and dictionaries.
        """

        collected = []

        if isinstance(value, str):

            if value.strip():
                collected.append(value.strip())

        elif isinstance(value, dict):

            for nested_value in value.values():
                collected.extend(
                    cls._collect_text_values(nested_value)
                )

        elif isinstance(value, (list, tuple, set)):

            for nested_value in value:
                collected.extend(
                    cls._collect_text_values(nested_value)
                )

        return collected

    # ==================================================
    # TEXT NORMALIZATION
    # ==================================================

    @staticmethod
    def _normalize(value: str) -> str:

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
    def _meaningful_tokens(cls, value: str) -> set[str]:

        stop_words = {
            "a", "an", "and", "or", "the", "of", "for",
            "in", "to", "with", "on", "by", "from",
            "as", "at", "is", "are", "be", "being",
            "basic", "understanding", "knowledge",
            "related", "strong", "good", "ability", "skills",
        }

        tokens = set()

        for word in cls._normalize(value).split():

            if len(word) <= 1 or word in stop_words:
                continue

            if len(word) > 4 and word.endswith("ies"):
                word = word[:-3] + "y"

            elif (
                len(word) > 4
                and word.endswith("s")
                and not word.endswith("ss")
            ):
                word = word[:-1]

            tokens.add(word)

        return tokens
