
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import Interview, InterviewQuestion
from app.db.session import get_db_context
from app.services.jd_analyzer import JDAnalyzer
from app.services.jd_question_generator import JDQuestionGenerator
from app.services.resume_analyzer import ResumeAnalyzer


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

                resume_analysis = await ResumeAnalyzer().analyze(
                    candidate_name=candidate_name,
                    resume_text=resume_text,
                    job_role=job_role,
                    job_description=job_description,
                )

            else:

                # Missing resume is not silently classified
                # as fresher or experienced.

                logger.warning(
                    "No resume supplied for session %s; "
                    "using uncertain branch",
                    session_id,
                )

                resume_analysis = cls._uncertain_resume_analysis()

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
                "Resume analysis completed: session=%s branch=%s",
                session_id,
                candidate_type,
            )

            # ==========================================
            # 3. ANALYZE JOB DESCRIPTION
            # ==========================================

            logger.info(
                "Starting JD analysis for session %s",
                session_id,
            )

            jd_analysis = await JDAnalyzer().analyze(
                job_role=job_role,
                job_description=job_description,
            )

            if not isinstance(jd_analysis, dict):
                raise ValueError(
                    "JD analyzer returned an invalid result."
                )

            logger.info(
                "JD analysis completed for session %s",
                session_id,
            )

            # ==========================================
            # 4. GENERATE COMPLETE STAGED BLUEPRINT
            # ==========================================

            logger.info(
                "Generating %s staged questions for session %s",
                cls.DEFAULT_QUESTION_COUNT,
                session_id,
            )

            questions = await JDQuestionGenerator().generate_questions(
                job_role=job_role,
                job_description=job_description,
                jd_analysis=jd_analysis,
                resume_analysis=resume_analysis,
                count=cls.DEFAULT_QUESTION_COUNT,
            )

            # ==========================================
            # 5. VALIDATE GENERATED QUESTIONS
            # ==========================================

            cls._validate_question_set(
                questions=questions,
                jd_analysis=jd_analysis,
                candidate_type=candidate_type,
            )

            logger.info(
                "Staged question validation passed for session %s",
                session_id,
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

                # Do not overwrite questions if the interview
                # has already activated or answered a question.

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

                # Save all generated questions.

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
                            "source": "gemini_staged_generation",

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

                # Store the complete preparation analysis.
                # This is useful for later evaluation and reporting.

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
                    "generation_source": "gemini",
                    "question_generation_strategy": (
                        "pre_generated_staged_branching"
                    ),
                    "live_llm_question_generation": False,
                    "prepared_at": prepared_at.isoformat(),
                }

                interview.preparation_status = "ready"
                interview.preparation_error = None
                interview.prepared_at = prepared_at

                db.flush()

            logger.info(
                "Interview preparation successful: "
                "session=%s questions=%s branch=%s",
                session_id,
                len(questions),
                candidate_type,
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

    # ==============================================
    # FALLBACK FOR MISSING RESUME
    # ==============================================

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

    # ==============================================
    # QUESTION VALIDATION
    # ==============================================

    @classmethod
    def _validate_question_set(
        cls,
        questions: list[dict],
        jd_analysis: dict,
        candidate_type: str,
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

            if isinstance(values, list):

                jd_terms.extend(
                    cls._normalize(value)
                    for value in values
                    if isinstance(value, str) and value.strip()
                )

        jd_tokens = (
            set().union(
                *(
                    cls._meaningful_tokens(term)
                    for term in jd_terms
                )
            )
            if jd_terms
            else set()
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

                competency_tokens = cls._meaningful_tokens(
                    competency
                )

                if (
                    not jd_tokens
                    or not competency_tokens.intersection(jd_tokens)
                ):
                    raise ValueError(
                        f"Technical question {index} competency "
                        "is not grounded in the JD."
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

    # ==============================================
    # TEXT NORMALIZATION
    # ==============================================

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
