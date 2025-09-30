# Policy Chatbot Backend (MVP)

임산부, 임신 예정자, 영유아 관련 정책 PDF를 읽고 답변하는 챗봇의 백엔드
MVP입니다. CLI를 통해 로컬 PDF를 Supabase(pgvector)에 업서트하고 OpenAI
`gpt-4.1` 모델로 질의를 수행하며, 필요하면 FastAPI HTTP API도 제공합니다.

## 구현된 기능

- PDF 텍스트 추출 및 슬라이딩 윈도우 방식 청크 분할 (`prec/pdf_loader.py`)
- OpenAI 임베딩/챗 API 래퍼 (`prec/openai_client.py`)
- Supabase(pgvector) 기반 벡터 스토어 연동 (`prec/vector_store.py`)
- 정책 특화 시스템 프롬프트 및 답변 파이프라인 (`prec/service.py`)
- CLI 서브커맨드: `ingest`, `ask`, `serve` (`prec/cli.py`, `main.py`)
- FastAPI 앱(`/ingest`, `/query`) 생성 팩토리 (`prec/app.py`)

## 사전 준비

- Python 3.12+
- OpenAI API 키 (`gpt-4.1-mini`, `text-embedding-3-small` 접근 필요)
- Supabase 프로젝트 (pgvector 확장 가능)
- 저장소의 `.venv` 가상환경 권장 (`source .venv/bin/activate`)

> **참고**: 오프라인 환경일 경우 네트워크 허용 전에는 필요한 휠을 미리
> 준비해야 합니다.

## 설치 방법

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

### macOS / Linux (bash/zsh)

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

> **주의 (requirements 공유 시)**
> 로컬 개발 편의를 위해 `pip install -e .` 명령을 사용하며, `pip freeze`
> 출력에는 `-e file:///...` 형태가 나타납니다. 이 경로는 개인 디렉터리를
> 가리키므로 다른 사용자가 그대로 설치하면 실패합니다. 공유용
> `requirements.txt`가 필요하다면 별도로 패키지 목록을 정리하거나
> `pip install .` 후 생성된 의존성 목록을 사용하세요.

## 환경 변수

| 변수                           | 필수 | 기본값                 | 설명                                                  |
| ------------------------------ | ---- | ---------------------- | ----------------------------------------------------- |
| `OPENAI_API_KEY`               | ✅   | 없음                   | OpenAI API 키                                         |
| `OPENAI_CHAT_MODEL`            | ❌   | `gpt-4.1`              | 답변 생성 모델                                        |
| `OPENAI_EMBEDDING_MODEL`       | ❌   | `upskyy/bge-m3-korean` | 임베딩 모델 (1024차원, sentence-transformers 필요)    |
| `SUPABASE_URL`                 | ✅   | 없음                   | Supabase 프로젝트 URL                                 |
| `SUPABASE_SERVICE_ROLE_KEY`    | ✅   | 없음                   | Supabase 서비스 롤 키 (`SUPABASE_ANON_KEY` 대체 가능) |
| `SUPABASE_TABLE`               | ❌   | `policy_chunks`        | 임베딩 저장 테이블                                    |
| `SUPABASE_QUERY_FUNCTION`      | ❌   | `match_policy_chunks`  | 벡터 검색 RPC 함수                                    |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | ❌   | `1200` / `200`         | PDF 청크 크기와 중첩                                  |
| `HOST` / `PORT`                | ❌   | `0.0.0.0` / `8000`     | `serve` 커맨드/HTTP 서버 바인딩                       |
| `ENABLE_EVALUATION`            | ❌   | `false`                | 기본적으로 LLM 평가를 수행할지 여부                   |
| `EVALUATION_MODEL`             | ❌   | `gpt-4.1`              | 평가에 사용할 챗 모델                                 |
| `EVALUATION_QUALITY_WEIGHT`    | ❌   | `0.7`                  | 품질 점수 가중치                                      |
| `EVALUATION_SPEED_WEIGHT`      | ❌   | `0.3`                  | 속도 점수 가중치                                      |
| `EVALUATION_TARGET_LATENCY`    | ❌   | `5.0`                  | 속도 점수 1.0을 기대하는 기준 응답 시간(초)           |
| `ENABLE_RERANKING`             | ❌   | `false`                | 기본적으로 리랭킹을 수행할지 여부                     |
| `RERANKER_MODEL`               | ❌   | `BAAI/bge-reranker-large` | SentenceTransformer 교차 인코더 모델 이름             |
| `RERANK_TOP_N`                 | ❌   | `5`                    | 리랭킹 후 유지할 후보 수                              |

루트 디렉터리에 `.env` 파일을 두면 자동으로 로드됩니다.

## Supabase 설정 요약

1. pgvector 확장
   ```sql
   create extension if not exists vector;
   ```
2. 테이블 생성 (이미 존재하면 `alter table`로 타입을 맞춰 주세요)
   ```sql
   create table if not exists policy_chunks (
     id text primary key,
     doc_id text not null,
     chunk_index int not null,
     content text,
     metadata jsonb,
     embedding vector(1024)
   );
   ```
3. (선택) ivfflat 인덱스 생성
   ```sql
   drop index if exists policy_chunks_embedding_ivfflat;
   create index policy_chunks_embedding_ivfflat
     on policy_chunks using ivfflat (embedding vector_cosine_ops)
     with (lists = 100);
   ```
4. RPC 함수 정리 및 재생성 (기존 버전이 있다면 삭제 후 생성)

   ```sql
   drop function if exists match_policy_chunks(vector, int, jsonb);
   drop function if exists match_policy_chunks(vector, int);

   create function match_policy_chunks(
     query_embedding vector(1024),
     match_count int
   ) returns table (
     id text,
     doc_id text,
     chunk_index int,
     content text,
     metadata jsonb,
     embedding vector(1024),
     similarity float
   ) language plpgsql as $$
   begin
     return query
     select
       pc.id,
       pc.doc_id,
       pc.chunk_index,
       pc.content,
       pc.metadata,
       pc.embedding,
       1 - (pc.embedding <-> query_embedding) as similarity
     from policy_chunks as pc
     order by pc.embedding <-> query_embedding
     limit match_count;
   end;
   $$;
   ```

추가적인 데이터베이스 설정 및 히스토리는 `USAGE_AND_NOTES.md`를 참고하세요.

## CLI 사용법

1. **PDF 업서트**

   ```bash
   # macOS / Linux
   python main.py ingest /path/to/pdf_dir --recursive

   # Windows PowerShell(경로에 공백/한글 포함 시 따옴표로 감싸기)
   python main.py ingest "C:\\경로\\정책자료" --recursive
   ```

   - 파일과 디렉터리를 혼합해 지정 가능
   - `--recursive`로 하위 디렉터리까지 탐색
   - 처리된 문서 수와 생성된 청크 수를 출력
   - 새 임베딩 모델을 사용하면 기존 레코드를 `delete from policy_chunks;`로
     비우고 다시 업서트해야 합니다.

2. **질문하기**

```bash
# macOS / Linux
python main.py ask "임산부 의료비 지원 정책은 어떤 것이 있나요?" --top-k 8

# Windows PowerShell
python main.py ask "사업 기간은 언제까지인가?" --top-k 8

# 평가까지 함께 실행하고 싶다면 --with-eval 플래그 사용
python main.py ask "사업 기간은 언제까지인가?" --top-k 8 --with-eval

# 리랭킹을 적용해 보다 관련성 높은 근거를 가져오려면 --with-rerank 추가
python main.py ask "나는 장애가 있는데 지원금이 있어?" --top-k 8 --with-rerank
```

- 답변과 함께 참조된 청크의 파일 경로, 페이지, 유사도, 텍스트를 출력
- `--with-eval` 사용 시 LLM 자가평가 기반 품질/속도/최종 점수가 함께 표시됩니다.
- `--with-rerank` 사용 시 교차 인코더가 후보 문단을 다시 정렬하고, 출력에
  리랭크 점수와 원래 벡터 점수가 함께 나타납니다. (미리 `ENABLE_RERANKING=true`
  로 설정하면 서비스 기동 시 모델이 로드됩니다.)

3. **(선택) API 서버 실행**

   ```bash
   # macOS / Linux
   python main.py serve --host 0.0.0.0 --port 8000

   # Windows PowerShell
   python main.py serve --host 0.0.0.0 --port 8000
   ```

   - `HOST`, `PORT` 환경변수를 설정하면 인자 없이도 실행 가능
   - FastAPI `/ingest`, `/query` 엔드포인트를 노출

HTTP API를 직접 호출하려면 `serve` 커맨드로 서버를 띄운 뒤 기존 엔드포인트를
사용하면 됩니다.

## 평가 지표 설명

- `Quality` (품질 점수): LLM 자가평가가 질문·답변·문맥을 비교해 0.0~1.0 범위로
  산출한 정확도 점수입니다. 구현은 `prec/eval.py:71-104` (`ResponseEvaluator.evaluate`
  및 `_score_quality`)에 정의되어 있습니다.
- `Speed` (속도 점수): 실제 응답 지연 시간과 목표 지연 시간(`EVALUATION_TARGET_LATENCY`)
  을 비교해 0.0~1.0 범위로 환산한 값입니다. 계산 공식은
  `prec/eval.py:106-114`의 `_score_speed`에 있습니다.
- `Final` (최종 점수): 품질과 속도 점수를 7:3 비율(환경 변수로 조절 가능)로
  가중 평균한 결과입니다. `prec/eval.py:85-104`에서 합산합니다.
- `Latency` (지연 시간): 답변을 생성하는 데 걸린 전체 시간을 초 단위로 기록한
  값이며, CLI에서는 밀리초로 표시합니다. 측정은 `prec/service.py:100-118`에서 이뤄집니다.
- `Reason` (평가 사유): LLM이 산출한 품질 점수에 대한 요약 근거로,
  `prec/eval.py:71-104`에서 응답 JSON의 `reasoning` 값을 추출합니다.

## 추가 참고 사항

- Supabase 테이블은 동일한 `id`에 대해 업서트(덮어쓰기) 동작을 수행합니다.
- `doc_id`에는 원본 PDF 경로가 저장되며, 필요 시 사용자 정의 식별자로
  교체할 수 있습니다.
- `chunk_index`는 페이지 내 청크 순서를 나타냅니다. 다른 기준이 필요하면
  `prec/pdf_loader.py`를 수정하세요.
- 임베딩 모델의 차원이 테이블 정의와 다르면 업서트가 실패합니다. 오류
  메시지를 확인해 테이블 스키마 또는 `OPENAI_EMBEDDING_MODEL`을 조정하세요.
- PDF가 이미지 기반이면 `pypdf`가 텍스트를 추출하지 못하므로 별도의 OCR
  파이프라인이 필요할 수 있습니다.
- 평가 기능을 활성화하면 OpenAI API 호출이 한 번 더 발생하므로 응답 시간이
  증가할 수 있습니다. 필요에 따라 `ENABLE_EVALUATION` 환경 변수나
  `--with-eval` 옵션을 선택적으로 사용하세요.
- 리랭킹은 추가 교차 인코더 추론을 수행하므로 응답 지연이 늘어날 수 있고,
  SentenceTransformer 모델이 설치되어 있어야 합니다. 필요 시
  `ENABLE_RERANKING` 또는 `--with-rerank` 옵션으로 제어하세요.
- 상세 사용법과 개발 히스토리는 `USAGE_AND_NOTES.md`에서 확인할 수 있습니다.

Updated: 2025-02-15 19:20 KST
Updated: 2025-09-28 20:48 KST — 테이블 벡터 컬럼과 RPC 함수를 1024차원으로 맞추는
SQL 예시(위 Supabase 설정 절차 참고)를 실행한 뒤 `delete from policy_chunks;`
로 기존 레코드를 비우고 `python main.py ingest <PDF>` 명령으로 재임베딩하세요.
Updated: 2025-09-29 15:45 KST — 교차 인코더 리랭킹(`--with-rerank`) 및 환경 변수
(`ENABLE_RERANKING`, `RERANKER_MODEL`, `RERANK_TOP_N`) 사용법을 추가하고 CLI/문서에
반영했습니다.

## Supabase upskyy/bge-m3-korean 업데이트

1. 테이블 벡터 컬럼을 1024차원으로 변경

```sql
alter table policy_chunks
  alter column embedding type vector(1024);
```

2. 기존 ivfflat 인덱스가 있다면 삭제 후 1024차원으로 재생성

```sql
drop index if exists policy_chunks_embedding_ivfflat;
create index policy_chunks_embedding_ivfflat
  on policy_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
```

3. RPC 함수도 동일 차원으로 교체

```sql
drop function if exists match_policy_chunks(vector, int, jsonb);
drop function if exists match_policy_chunks(vector, int);

create function match_policy_chunks(
  query_embedding vector(1024),
  match_count int
) returns table (
  id text,
  doc_id text,
  chunk_index int,
  content text,
  metadata jsonb,
  embedding vector(1024),
  similarity float
) language plpgsql as $$
begin
  return query
  select
    pc.id,
    pc.doc_id,
    pc.chunk_index,
    pc.content,
    pc.metadata,
    pc.embedding,
    1 - (pc.embedding <-> query_embedding) as similarity
  from policy_chunks as pc
  order by pc.embedding <-> query_embedding
  limit match_count;
end;
$$;
```
