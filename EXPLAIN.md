# 평가 지표 구현 설명

## 개요
이 문서는 `Quality`, `Speed`, `Final`, `Latency`, `Reason` 지표가 어떤 방식으로
구현되어 있으며, 어떤 파일의 몇 번째 줄에서 확인할 수 있는지 정리합니다.

## 세부 항목
- **Quality (품질 점수)**
  - 위치: `prec/eval.py:93-119`
  - 내용: `ResponseEvaluator._score_quality`가 LLM 자가평가 프롬프트를 구성하고
    OpenAI Chat API를 호출해 0.0~1.0 범위의 점수를 추출합니다. 응답 JSON의
    `score`, `reasoning` 필드가 각각 품질 점수와 사유에 매핑됩니다.

- **Speed (속도 점수)**
  - 위치: `prec/eval.py:121-126`
  - 내용: 실제 응답 지연 시간(`latency_seconds`)을 목표 지연 시간
    (`EVALUATION_TARGET_LATENCY`)과 비교해 `1 - latency/target` 공식을 적용합니다.
    0.0~1.0 범위로 클램핑하며 음수는 0으로 처리합니다.

- **Final (최종 점수)**
  - 위치: `prec/eval.py:70-91`
  - 내용: `ResponseEvaluator.evaluate`가 품질·속도 점수를 받아 가중치 비율
    (기본 0.7:0.3)을 적용해 최종 점수를 계산합니다. 가중치는 환경 변수로
    조정할 수 있습니다.

- **Latency (지연 시간)**
  - 위치: `prec/service.py:95-138`
  - 내용: `ChatbotService.answer`에서 질문에 대한 답변을 생성하기 직전에
    `perf_counter()`로 타이머를 시작하고, 완료 후 초 단위 지연 시간을 계산해
    응답에 포함시킵니다. CLI에서는 밀리초로 변환해 보여줍니다 (`prec/cli.py:83-111`).

- **Reason (평가 사유)**
  - 위치: `prec/eval.py:108-119`
  - 내용: LLM 평가 응답에서 `reasoning` 필드를 추출해 사용자가 품질 점수를
    이해할 수 있도록 텍스트 형태로 제공합니다.

## 임베딩 백엔드 전환
- `prec/settings.py:11` — 기본 임베딩 모델을 `upskyy/bge-m3-korean`으로 변경했습니다.
- `prec/openai_client.py:11-63` — SentenceTransformer 기반 로컬 임베딩 백엔드를
  자동 감지하고, Hugging Face 모델을 사용할 때 `sentence-transformers`를 통해
  벡터를 생성하도록 확장했습니다.
- `pyproject.toml:8-14` — `sentence-transformers` 의존성을 추가했습니다.
- README/USAGE 문서의 Supabase 테이블·RPC 예제를 1024차원으로 업데이트했습니다.
- Supabase 측에서는 `alter table ... vector(1024)`와 RPC 재정의를 진행해야 하며,
  기존 레코드는 `delete from policy_chunks;`로 비운 뒤 `python main.py ingest ...`
  를 다시 실행해야 합니다 (`README.md` 최신 업데이트 시간 참고).

## 리랭킹 추가 (2025-09-29)
- `prec/reranker.py:1-54` — SentenceTransformer `CrossEncoder`를 이용한 리랭커 구현.
- `prec/service.py:22-166` — `ChatbotService`에 리랭킹 옵션과 벡터/리랭크 점수 병행
  노출 로직 추가.
- `prec/app.py:1-138` — FastAPI 요청/응답에 `with_rerank`, `rerank_applied`,
  `vector_score` 필드를 확장.
- `prec/cli.py:80-135` — CLI에 `--with-rerank` 플래그를 추가하고 리랭크 점수 출력.
- `prec/settings.py:1-84` — `ENABLE_RERANKING`, `RERANKER_MODEL`, `RERANK_TOP_N`
  환경 변수를 읽어 서비스에 전달.
- `README.md`, `USAGE_AND_NOTES.md` — 사용법 및 Supabase 설정 지침 업데이트.

## 추가 참고
- FastAPI `/query` 응답에 평가 결과를 포함하는 로직은 `prec/app.py:33-118`에서
  확인할 수 있습니다.
- CLI `--with-eval` 옵션을 통해 평가를 실행할 때 출력 포맷은
  `prec/cli.py:83-111`에 정의되어 있습니다.
