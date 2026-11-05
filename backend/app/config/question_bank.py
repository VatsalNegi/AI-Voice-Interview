
QUESTION_BANK = {

    "introduction": [
        {
            "question_id": "INTRO_001",
            "question": "Tell me about yourself and your technical background.",
            "competency": "communication",
            "difficulty": "easy",
            "expected_concepts": [
                "education",
                "technical_skills",
                "projects",
                "experience",
                "career_interests"
            ],
            "rubric": {
                "relevance": 30,
                "communication": 30,
                "technical_exposure": 40
            },
            "max_followups": 2
        }
    ],

    "experience": [
        {
            "question_id": "EXP_001",
            "question": "Can you describe your most recent technical experience or internship?",
            "competency": "practical_experience",
            "difficulty": "medium",
            "expected_concepts": [
                "responsibilities",
                "technologies_used",
                "contribution",
                "challenges",
                "outcomes"
            ],
            "rubric": {
                "ownership": 30,
                "technical_understanding": 40,
                "communication": 30
            },
            "max_followups": 3
        }
    ],

    "projects": [
        {
            "question_id": "PROJ_001",
            "question": "Walk me through one of your most important technical projects. What problem does it solve?",
            "competency": "project_understanding",
            "difficulty": "medium",
            "expected_concepts": [
                "problem_statement",
                "architecture",
                "technology_stack",
                "personal_contribution",
                "implementation"
            ],
            "rubric": {
                "problem_understanding": 25,
                "technical_depth": 35,
                "ownership": 25,
                "communication": 15
            },
            "max_followups": 3
        }
    ],

    "technical": [
        {
            "question_id": "PY_001",
            "question": "What is the difference between a list and a tuple in Python?",
            "competency": "python_fundamentals",
            "difficulty": "easy",
            "expected_concepts": [
                "list is mutable",
                "tuple is immutable",
                "list supports modification",
                "tuple does not support item reassignment",
                "square brackets for lists",
                "parentheses for tuples"
            ],
            "rubric": {
                "technical_accuracy": 50,
                "conceptual_understanding": 30,
                "examples": 20
            },
            "max_followups": 2
        },
        {
            "question_id": "PY_002",
            "question": "Explain how FastAPI handles incoming HTTP requests.",
            "competency": "backend_development",
            "difficulty": "medium",
            "expected_concepts": [
                "HTTP methods",
                "route matching",
                "request validation",
                "Pydantic",
                "response serialization"
            ],
            "rubric": {
                "technical_accuracy": 40,
                "conceptual_understanding": 35,
                "practical_application": 25
            },
            "max_followups": 2
        }
    ],

    "problem_solving": [
        {
            "question_id": "PS_001",
            "question": "Suppose your API starts receiving thousands of requests simultaneously and response times increase significantly. How would you investigate and improve its performance?",
            "competency": "problem_solving",
            "difficulty": "hard",
            "expected_concepts": [
                "identify bottleneck",
                "logging and monitoring",
                "database query optimization",
                "caching",
                "asynchronous processing",
                "load balancing",
                "scaling"
            ],
            "rubric": {
                "problem_analysis": 30,
                "technical_reasoning": 30,
                "practical_solutions": 25,
                "tradeoff_awareness": 15
            },
            "max_followups": 3
        }
    ]
}
