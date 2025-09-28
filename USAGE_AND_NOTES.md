# Usage & Development Notes

## 주요 파일과 역할

- `main.py` — CLI 엔트리포인트. `python main.py <command>` 형태로 실행합니다.
- `prec/cli.py` — `ingest`, `ask`, `serve` 서브커맨드를 정의하며 Supabase와 상호작용합니다.
- `prec/service.py` — PDF 청크 생성, 임베딩, Supabase 검색을 아우르는 비즈니스 로직.
- `prec/pdf_loader.py` — PDF 텍스트 추출 및 청크 분할 로직. 페이지별 `chunk_index` 메타데이터를 추가합니다.
- `prec/vector_store.py` — Supabase 테이블에 업서트하고 RPC 함수를 호출해 유사도를 계산합니다.
- `prec/settings.py` — `.env` 자동 로드 및 환경 변수 기반 설정을 제공합니다.
- `prec/app.py` — FastAPI 앱과 동일한 서비스 구성을 재사용할 수 있게 팩토리를 제공합니다.

## 사용 방법 요약

1. 가상환경 및 의존성
   ```bash
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```
2. 환경 변수 (`.env` 지원)
   - `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`(또는 `SUPABASE_ANON_KEY`)
   - 선택 사항: `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `SUPABASE_TABLE`,
     `SUPABASE_QUERY_FUNCTION`, `HOST`, `PORT`, `CHUNK_SIZE`, `CHUNK_OVERLAP`
3. Supabase 초기화 (pgvector 확장, `policy_chunks` 테이블, `match_policy_chunks` RPC 생성)
4. PDF 업서트
   ```bash
   python main.py ingest /path/to/pdf_dir --recursive
   ```
5. 질의
   ```bash
   python main.py ask "임산부 의료비 지원 정책은 어떤 것이 있나요?" --top-k 8
   python main.py ask "사업 기간은 언제까지인가?" --top-k 8 --with-eval  # 평가 포함
   ```
6. API 서버 (선택)
   ```bash
   python main.py serve --host 0.0.0.0 --port 8000
   ```

## Supabase 데이터베이스 초기화 단계

Supabase SQL 콘솔 또는 psql에서 아래 순서를 따라 데이터베이스를 준비합니다.

1. **pgvector 확장 활성화**
   ```sql
   create extension if not exists vector;
   ```
2. **벡터 테이블 생성**
   ```sql
   create table if not exists policy_chunks (
     id text primary key,
     doc_id text not null,
     chunk_index int not null,
     content text,
     metadata jsonb,
     embedding vector(1536)
   );
   ```
   - 기존 테이블과 충돌할 경우 `alter table ...`로 컬럼 타입을 `text`, `int`,
     `vector(1536)` 등에 맞춰 조정합니다.
3. **(선택) IVF 인덱스 생성** — 검색 성능 향상을 위해 pgvector 인덱스를
   구축합니다.
   ```sql
   drop index if exists policy_chunks_embedding_ivfflat;
   create index policy_chunks_embedding_ivfflat
     on policy_chunks using ivfflat (embedding vector_cosine_ops)
     with (lists = 100);
   ```
   - 1536차원 모델(`text-embedding-3-small`) 기준이며, 다른 모델을 쓰면 해당
     차수에 맞춰 테이블과 인덱스를 다시 생성해야 합니다.
4. **RPC 함수 정리 및 생성**
   ```sql
   drop function if exists match_policy_chunks(vector, int, jsonb);
   drop function if exists match_policy_chunks(vector, int);

   create function match_policy_chunks(
     query_embedding vector(1536),
     match_count int
   ) returns table (
     id text,
     doc_id text,
     chunk_index int,
     content text,
     metadata jsonb,
     embedding vector(1536),
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
5. **(선택) 기존 데이터 업데이트** — 이미 존재하는 레코드가 있다면 `doc_id`
   및 `chunk_index` 컬럼에 적절한 값을 채운 뒤 `alter table ... set not null`
   제약을 적용합니다.

## Supabase 테이블 스키마 예시

```sql
create table if not exists policy_chunks (
  id text primary key,
  doc_id text not null,
  chunk_index int not null,
  content text,
  metadata jsonb,
  embedding vector(1536)
);
```

중복되는 RPC가 있다면 삭제한 뒤 아래 함수를 사용합니다.

```sql
drop function if exists match_policy_chunks(vector, int, jsonb);

drop function if exists match_policy_chunks(vector, int);

create function match_policy_chunks(
  query_embedding vector(1536),
  match_count int
) returns table (
  id text,
  doc_id text,
  chunk_index int,
  content text,
  metadata jsonb,
  embedding vector(1536),
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

## 평가 기능 메모

- 평가 활성화는 `ENABLE_EVALUATION=true` 환경 변수나 CLI `--with-eval` 플래그로
  제어할 수 있습니다.
- 품질 점수는 LLM 자가평가(질문/답변/컨텍스트 기반) 결과를 0~1 범위로 환산합니다.
- 속도 점수는 `EVALUATION_TARGET_LATENCY` 대비 실제 지연 시간을 사용해 0~1 범위로
  계산합니다.
- 통합 점수 = `0.7 * 품질 + 0.3 * 속도` (가중치는 환경 변수로 조정 가능).
- 평가 호출 실패 시 품질 점수는 0으로, 사유(reasoning)에 오류 메시지가 기록됩니다.

## 개발 히스토리 (순서)

1. FastAPI 기반 MVP 구조와 PDF 파이프라인 초안 작성 (`prec/app.py`, `prec/service.py`, `prec/pdf_loader.py`).
2. OpenAI 임베딩/챗 클라이언트 래퍼 추가 (`prec/openai_client.py`) 후 로컬 JSON 벡터 스토어 프로토타입 구현.
3. Supabase(pgvector) 기반 벡터 스토어로 전환하고 설정 클래스에 Supabase 구성요소 추가 (`prec/vector_store.py`, `prec/settings.py`).
4. `.env` 자동 로드 및 README 초기 설명 업데이트.
5. CLI 서브커맨드 도입(`ingest`, `ask`, `serve`) 및 `main.py`를 CLI 엔트리포인트로 변경.
6. Supabase 테이블 업서트 시 필요한 필드(`doc_id`, `chunk_index`)를 반영하고 PDF 청크 메타데이터를 확장.
7. `text-embedding-3-small`(1536차원) 모델로 기본값 변경 후 README, 설정, Supabase RPC 예제를 최신화.
8. Supabase 함수/스키마 충돌 시나리오에 대응하기 위한 예외 처리와 문서 보강.

필요 시 이 문서를 참조하여 환경 재구성, 추가 개발, 배포 자동화 등을 진행할 수 있습니다.
