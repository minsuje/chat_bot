from __future__ import annotations

from typing import Iterable, List, Sequence

from openai import OpenAI


class OpenAIEmbeddingClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, inputs: Sequence[str]) -> List[List[float]]:
        # OpenAI API only accepts non-empty inputs
        batched = [item for item in inputs if item.strip()]
        if not batched:
            return [[] for _ in inputs]
        response = self._client.embeddings.create(model=self._model, input=batched)
        embeddings = [item.embedding for item in response.data]

        iterator = iter(embeddings)
        result: List[List[float]] = []
        for text in inputs:
            if text.strip():
                result.append(next(iterator))
            else:
                result.append([])
        return result


class OpenAIChatClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, messages: Iterable[dict], *, temperature: float = 0.0) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=temperature,
        )
        message = response.choices[0].message
        return message.content or ""
