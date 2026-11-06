from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship
from app.db.session import Base


class Recruiter(Base):
    __tablename__ = "recruiters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String(100), index=True, nullable=False)
    candidate_name = Column(String(255), nullable=False)
    email = Column(String(255), index=True, nullable=False)
    resume_text = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    interviews = relationship(
        "Interview",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    candidate_id = Column(
        Integer,
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_role = Column(String(255), nullable=False)
    job_description = Column(Text, nullable=True)
    interview_duration = Column(Integer, default=30, nullable=False)
    language = Column(String(50), default="English", nullable=False)
    status = Column(String(50), default="not_started", nullable=False, index=True)
    current_stage = Column(String(50), default="introduction", nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    overall_score = Column(Float, nullable=True)

    # Persistent runtime session state
    consecutive_unsuccessful_answers = Column(Integer, default=0, nullable=False)
    resume_mode = Column(Boolean, default=False, nullable=False)
    resume_questions_generated = Column(Integer, default=0, nullable=False)
    standard_stage_before_resume = Column(
        String(50), default="introduction", nullable=False
    )
    current_question_id = Column(String(100), nullable=True)
    current_question_metadata = Column(JSON, nullable=True)
    current_followup = Column(Text, nullable=True)
    followup_count = Column(Integer, default=0, nullable=False)
    current_question_answers = Column(JSON, default=list, nullable=False)
    resume_question_queue = Column(JSON, default=list, nullable=False)
    transcript = Column(JSON, default=list, nullable=False)
    final_report = Column(JSON, nullable=True)
    recommendation = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")
    questions = relationship(
        "InterviewQuestion",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.sequence_number",
    )
    evaluations = relationship(
        "Evaluation",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="Evaluation.created_at",
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(String(100), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    competency = Column(String(100), nullable=True)
    difficulty = Column(String(50), nullable=True)
    question_type = Column(
        String(50), default="primary", nullable=False
    )  # "primary" or "follow-up"
    sequence_number = Column(Integer, default=1, nullable=False)
    expected_concepts = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    interview = relationship("Interview", back_populates="questions")
    answers = relationship(
        "CandidateAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="CandidateAnswer.created_at",
    )
    evaluations = relationship(
        "Evaluation",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question_id = Column(
        Integer,
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_text = Column(Text, nullable=False)
    answer_type = Column(
        String(50), default="initial", nullable=False
    )  # "initial" or "follow-up"
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    question = relationship("InterviewQuestion", back_populates="answers")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(
        Integer,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id = Column(
        Integer,
        ForeignKey("interview_questions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    technical_correctness = Column(Integer, nullable=True)
    concept_coverage = Column(Float, nullable=True)
    reasoning_quality = Column(Integer, nullable=True)
    communication_clarity = Column(Integer, nullable=True)
    answer_classification = Column(String(50), nullable=True)
    matched_concepts = Column(JSON, default=list, nullable=True)
    missing_concepts = Column(JSON, default=list, nullable=True)
    incorrect_statements = Column(JSON, default=list, nullable=True)
    overall_feedback = Column(Text, nullable=True)
    confidence = Column(String(50), nullable=True)
    complete_evaluation_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    interview = relationship("Interview", back_populates="evaluations")
    question = relationship("InterviewQuestion", back_populates="evaluations")
