from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from chatbot_pacch.config import Settings
from chatbot_pacch.database import Database
from chatbot_pacch.rag.retrieval import HybridRetriever, has_sufficient_evidence


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    total: int
    passed: int
    retrieval_recall: float
    refusal_accuracy: float
    failures: tuple[str, ...]


async def evaluate_retrieval(
    settings: Settings, dataset_path: Path
) -> EvaluationSummary:
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    retriever = HybridRetriever(settings, Database(settings.database_path))
    passed = 0
    answerable_total = 0
    answerable_passed = 0
    refusal_total = 0
    refusal_passed = 0
    failures: list[str] = []

    for case in cases:
        results = await retriever.search(case["question"], 5)
        sufficient = has_sufficient_evidence(results, case["question"])
        if case["should_answer"]:
            answerable_total += 1
            expected = case["expected_url_contains"]
            success = sufficient and any(expected in result.url for result in results)
            answerable_passed += int(success)
        else:
            refusal_total += 1
            success = not sufficient
            refusal_passed += int(success)
        passed += int(success)
        if not success:
            best = results[0] if results else None
            failures.append(
                f"{case['question']} -> "
                f"{best.url if best else 'sin resultados'} "
                f"(sim={best.semantic_score if best else None}, suficiente={sufficient})"
            )

    return EvaluationSummary(
        total=len(cases),
        passed=passed,
        retrieval_recall=(answerable_passed / answerable_total if answerable_total else 0.0),
        refusal_accuracy=(refusal_passed / refusal_total if refusal_total else 0.0),
        failures=tuple(failures),
    )
