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
