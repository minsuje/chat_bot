# Evaluation Feature Checklist

## 설계
- [x] LLM 자가평가 프롬프트 및 출력 포맷 정의
- [x] 속도 점수 산정 방식과 목표 응답 시간 결정
- [x] 품질/속도 가중치(7:3) 검증 및 예외 처리 전략 수립

## 구현
- [x] `prec/eval.py` 모듈에 평가 로직(품질, 속도, 통합 점수) 추가
- [x] `ChatbotService.answer`에서 평가 선택적 실행 및 결과 반환
- [x] CLI `ask` 명령에 `--with-eval` 플래그 추가 및 출력 포맷 정리
- [x] FastAPI `/query` 요청/응답 스키마에 평가 옵션과 결과 반영

## 검증
- [ ] 다양한 질문으로 품질 평가 결과와 속도 측정 확인
- [ ] 평가 호출 실패 시 graceful fallback 여부 확인

## 문서화
- [x] README 환경 변수 및 CLI 설명에 평가 기능 추가
- [x] `USAGE_AND_NOTES.md`에 평가 사용 가이드와 주의사항 기록
- [x] README에 평가 지표(Quality/Speed/Final/Latency/Reason) 설명 추가

## 변경 이력
- [x] README.md:141-158 — 평가 지표 상세 설명 및 관련 소스 위치 표기
- [x] EXPLAIN.md:1-41 — 평가 지표 구현 위치와 역할 설명 문서 추가
- [x] pyproject.toml:7-14 — sentence-transformers 의존성 추가
- [x] prec/openai_client.py:1-63 — Hugging Face 임베딩 백엔드 지원
- [x] prec/settings.py:7-75 — 기본 임베딩 모델을 bge-m3-korean으로 변경
- [x] README.md:46-168 — 임베딩 모델/차원, 재임베딩 안내, 갱신 일시 추가
- [x] USAGE_AND_NOTES.md:40-110 — Supabase 차원 및 과정 업데이트

## 임베딩 모델 교체 (upskyy/bge-m3-korean)
- [x] `.env` 예시 및 README 기본값을 `upskyy/bge-m3-korean`으로 수정 계획 수립
- [x] `prec/settings.py`에서 기본 임베딩 모델 상수 업데이트 및 관련 주석 점검
- [x] Supabase 테이블 벡터 차원 확인 및 필요한 경우 스키마 변경(SQL 문서화 포함)
- [x] 모델 변경 후 재임베딩 절차 안내 (README/USAGE 업데이트)
- [ ] 변경 사항에 대한 테스트(재인덱싱/질의) 수행 및 결과 기록

## 리랭킹 기능 도입
- [x] 리랭킹 전략 및 모델 선택 (SentenceTransformer Cross-Encoder) 결정
- [x] `prec/reranker.py`에 리랭커 클래스 구현 및 의존성 확인
- [x] `prec/service.py`에서 리랭킹 통합 (옵션 처리 포함)
- [x] CLI/HTTP API에 리랭킹 토글(`--with-rerank`, `with_rerank`) 추가
- [x] 환경 변수 및 설정(`ENABLE_RERANKING`, `RERANKER_MODEL`, `RERANK_TOP_N`) 반영
- [x] README/USAGE/EXPLAIN 문서에 리랭킹 사용법과 변경 내역 기록
- [ ] 리랭킹 적용 후 응답 품질/속도 체감 테스트 및 결과 메모
