
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


class SemanticEvaluator:

    def __init__(self):
        print("Loading semantic model...")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        print("Semantic model loaded successfully!")

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in text.replace("!", ".").replace("?", ".").split(".")
            if sentence.strip()
        ]

    def evaluate_concepts(
        self,
        candidate_answer: str,
        expected_concepts: list[str],
        threshold: float = 0.45
    ):

        sentences = self.split_sentences(candidate_answer)

        if not sentences:
            return {
                "matched_concepts": [],
                "missing_concepts": expected_concepts,
                "similarities": {},
                "evidence": {},
                "uncertain_concepts": []
            }

        sentence_embeddings = self.model.encode(
            sentences,
            convert_to_tensor=True
        )

        concept_embeddings = self.model.encode(
            expected_concepts,
            convert_to_tensor=True
        )

        similarity_matrix = cos_sim(
            sentence_embeddings,
            concept_embeddings
        )

        matched = []
        missing = []
        uncertain = []
        similarities = {}
        evidence = {}

        for concept_index, concept in enumerate(expected_concepts):

            scores = similarity_matrix[:, concept_index]

            best_index = int(scores.argmax())
            best_score = float(scores[best_index])

            best_sentence = sentences[best_index]

            similarities[concept] = round(best_score, 4)

            # Direct phrase matching is stronger evidence.
            normalized_sentence = best_sentence.lower()
            normalized_concept = concept.lower()

            if normalized_concept in normalized_sentence:
                matched.append(concept)
                evidence[concept] = best_sentence

            elif best_score >= threshold:
                # Semantic similarity alone is not proof.
                # Mark this concept for further validation.
                uncertain.append(concept)
                evidence[concept] = best_sentence

            else:
                missing.append(concept)

        return {
            "matched_concepts": matched,
            "missing_concepts": missing,
            "uncertain_concepts": uncertain,
            "similarities": similarities,
            "evidence": evidence
        }
