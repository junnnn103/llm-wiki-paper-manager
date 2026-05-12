# PaperManager

AI/ML 논문을 분석하고 Obsidian vault에 구조화된 지식으로 저장하는 CLI 도구.

논문을 추가할 때마다 개별 노트, 토픽 페이지, 인용 링크가 자동으로 생성/업데이트되어 시간이 지날수록 연구 흐름을 한눈에 파악할 수 있는 위키가 쌓인다.

## 주요 기능

- **논문 노트 자동 생성** — arXiv URL, arXiv ID, 로컬 PDF 모두 지원. 제목/저자/노벨티/키워드/방법론 등을 GPT-4o로 분석해 Obsidian 마크다운 노트로 저장
- **심층 분석 (`--deep`)** — 논문의 핵심 인용 논문 5개 추출 (References 원문 기반, 정확한 제목 사용) + Semantic Scholar로 후속 연구 검색
- **Obsidian 위키링크 자동 연결** — 인용된 논문을 나중에 처리하면 `[[논문 제목]]` 링크가 자동으로 연결됨
- **토픽 페이지 자동 업데이트** — 논문 추가 시 관련 토픽 페이지(Multi-Agent Systems, LLM Reasoning 등)에 논문이 쌓이고 연구 흐름 요약이 갱신됨
- **Inbox 워크플로우 (`--inbox`)** — `Papers/Inbox/`에 PDF를 쌓아두고 한 번에 처리. 완료된 파일은 자동으로 `Papers/`로 이동
- **Lens 페이지 생성 (`--lens`)** — 특정 토픽의 논문들을 새로운 분류 축(topology, reasoning method 등)으로 재분석해 wiki 페이지 생성

## Obsidian Vault 구조

```
LLM Vault/
  Papers/     논문 노트 (PaperManager 자동 생성)
  Topics/     토픽 페이지 (논문 추가 시 자동 업데이트)
  Lens/       Lens 페이지 (--lens 명령 실행 시 생성)
  Notes/      개인 공부 노트 (수동 관리)
```

## 설치

```bash
pip install openai arxiv pymupdf python-dotenv
```

`.env` 파일을 프로젝트 루트에 생성:

```
OPENAI_API_KEY=sk-...
```

`config.py`에서 Obsidian vault 경로 확인:

```python
OBSIDIAN_VAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/LLM Vault"
```

## 사용법

### 논문 한 편 분석

```bash
# arXiv URL
python main.py https://arxiv.org/abs/2312.00752

# arXiv ID
python main.py 2312.00752

# 로컬 PDF
python main.py Papers/ChatDev.pdf

# 심층 분석 (인용 논문 추적 + 후속 연구 검색)
python main.py --deep Papers/ChatDev.pdf
```

### Inbox 일괄 처리 (추천 워크플로우)

```bash
# 1. PDF를 Papers/Inbox/ 에 복붙
# 2. 실행
python main.py --inbox --deep

# 처리 완료된 PDF는 자동으로 Papers/로 이동, Inbox는 비워짐
```

### Lens — 새로운 시각으로 재분석

특정 토픽의 논문들을 원하는 분류 축으로 재분석해 wiki 페이지를 생성한다.
논문이 쌓인 후 "이 논문들을 X 기준으로 분류하고 싶다"는 상황에서 사용.

```bash
python main.py --lens "Multi-Agent Systems" "topology"
python main.py --lens "Multi-Agent Systems" "communication protocol"
python main.py --lens "LLM Reasoning" "evaluation method"
```

결과: `Lens/Lens - Multi-Agent Systems × topology.md` 생성

논문 추가 후 같은 명령을 다시 실행하면 페이지가 업데이트된다.

## 프로젝트 구조

```
PaperManager/
  main.py             CLI 진입점
  config.py           API 키, vault 경로, 모델 설정
  fetcher.py          PDF/arXiv 텍스트 추출 (References 섹션 별도 추출 포함)
  analyzer.py         GPT-4o 논문 분석 (노벨티, 키워드, 요약 등)
  deep_researcher.py  핵심 인용 논문 추출 + Semantic Scholar 후속 연구 검색
  obsidian_writer.py  Obsidian 마크다운 노트 생성
  topic_writer.py     토픽 페이지 생성/업데이트
  lens_writer.py      Lens 페이지 생성 (2단계 추출: md → PDF)
  Papers/
    Inbox/            처리 대기 PDF 보관함
    *.pdf             처리 완료된 원본 PDF
```

## 설계 원칙

- **Raw sources와 wiki 분리** — PDF는 `Papers/`에, 지식은 Obsidian vault에
- **정확한 제목 기반 링크** — 인용 논문 제목은 References 원문에서 그대로 복사해 위키링크 자동 연결 보장
- **점진적 지식 축적** — 논문이 쌓일수록 토픽 페이지의 흐름 요약과 Lens 분류가 더 풍부해짐
- **토큰 효율** — Lens 실행 시 논문 수 20개 미만이면 전체 PDF, 이상이면 md 1차 필터링 후 필요한 PDF만 재읽기
