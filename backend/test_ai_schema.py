from app.schemas.ai_evaluation import AIEvaluation

evaluation = AIEvaluation(
    technical_correctness=90,
    concept_coverage=85,
    reasoning_quality=80,
    communication_clarity=90,
    matched_concepts=["List is mutable"],
    missing_concepts=["Tuple is immutable"],
    incorrect_statements=[],
    evidence=["Lists can be modified after creation."],
    strengths=["Clear explanation"],
    improvement_areas=["Explain tuple immutability"],
    overall_feedback="Good answer with one missing concept.",
    confidence="high"
)

print(evaluation.model_dump_json(indent=4))