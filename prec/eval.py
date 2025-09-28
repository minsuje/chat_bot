from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Optional

from .openai_client import OpenAIChatClient


EVALUATION_SYSTEM_PROMPT = (
    "You are a strict evaluator that judges how well an assistant answer "
    "addresses a user question using the provided context. Score the answer "
    "between 0.0 (completely incorrect) and 1.0 (perfect). Return concise "
    "reasoning in Korean."
)

EVALUATION_USER_PROMPT_TEMPLATE = (
    "평가 항목:\n"
    "1. 사용자의 질문에 정확히 답했는가?\n"
    "2. 불필요한 추론이나 허위 정보가 있는가?\n"
    "3. 문맥(Context)에 근거한 답변인가?\n\n"
    "질문: {question}\n"
    "답변: {answer}\n"
    "문맥: {context}\n\n"
    "0.0부터 1.0 사이의 'score'와 간단한 'reasoning'을 JSON으로만 응답하세요."
)


@dataclass
class EvaluationResult:
    quality_score: float
    speed_score: float
    final_score: float
    latency_seconds: float
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "quality_score": self.quality_score,
            "speed_score": self.speed_score,
            "final_score": self.final_score,
            "latency_seconds": self.latency_seconds,
            "reasoning": self.reasoning,
        }


class ResponseEvaluator:
    def __init__(
        self,
        chat_client: OpenAIChatClient,
        *,
        quality_weight: float = 0.7,
        speed_weight: float = 0.3,
        target_latency: float = 5.0,
    ) -> None:
        if quality_weight < 0 or speed_weight < 0:
            raise ValueError("Weights must be non-negative")
        if quality_weight == 0 and speed_weight == 0:
            raise ValueError("At least one weight must be positive")
        self._chat_client = chat_client
        self._quality_weight = quality_weight
        self._speed_weight = speed_weight
        total = quality_weight + speed_weight
        self._quality_factor = quality_weight / total
        self._speed_factor = speed_weight / total
        self._target_latency = max(target_latency, 0.1)

    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        context: str,
        latency_seconds: float,
    ) -> EvaluationResult:
        quality_score, reasoning = self._score_quality(
            question=question, answer=answer, context=context
        )
        speed_score = self._score_speed(latency_seconds)
        final_score = (self._quality_factor * quality_score) + (
            self._speed_factor * speed_score
        )
        return EvaluationResult(
            quality_score=quality_score,
            speed_score=speed_score,
            final_score=final_score,
            latency_seconds=latency_seconds,
            reasoning=reasoning,
        )

    def _score_quality(self, *, question: str, answer: str, context: str) -> tuple[float, str]:
        user_prompt = EVALUATION_USER_PROMPT_TEMPLATE.format(
            question=question.strip(),
            answer=answer.strip(),
            context=context.strip() or "(문맥 없음)",
        )
        messages = [
            {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            raw = self._chat_client.complete(messages, temperature=0.0)
        except Exception as exc:  # pragma: no cover - network/SDK failures
            return 0.0, f"LLM 평가 실패: {exc}"

        payload = self._extract_json(raw)
        if not isinstance(payload, dict):
            return 0.0, "LLM 평가 응답 파싱 실패"

        score = payload.get("score")
        reasoning = str(payload.get("reasoning", "평가 사유를 가져올 수 없습니다.")).strip()
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            score_value = 0.0
        score_value = min(1.0, max(0.0, score_value))
        return score_value, reasoning

    def _score_speed(self, latency_seconds: float) -> float:
        if not math.isfinite(latency_seconds) or latency_seconds <= 0:
            return 1.0
        ratio = latency_seconds / self._target_latency
        score = 1.0 - ratio
        return min(1.0, max(0.0, score))

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        text = text.strip()
        # Attempt direct JSON parsing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Search for JSON object within text (e.g., fenced code blocks)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None
