import json
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL


def analyze_paper(paper: dict, existing_notes: list[str] | None = None) -> dict:
    """Agent 1: 논문 텍스트를 분석해서 노벨티, 키워드, 요약 반환."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    notes_section = ""
    if existing_notes:
        notes_list = "\n".join(f"- {n}" for n in existing_notes)
        notes_section = f"""
## 내 Obsidian vault에 있는 기존 노트 목록
{notes_list}

위 목록 중 이 논문과 관련 있는 노트를 `related_notes` 필드에 **정확한 파일명 그대로** 넣어주세요.
"""

    prompt = f"""당신은 AI/ML 논문 분석 전문가입니다. 다음 논문을 분석하여 JSON 형식으로 반환하세요.

## 논문 정보
제목: {paper.get('title', '(PDF에서 추출 필요)')}
저자: {', '.join(paper.get('authors', [])) or '(PDF에서 추출 필요)'}
연도: {paper.get('year', '(PDF에서 추출 필요)')}

## Abstract
{paper.get('abstract', '')}

## 본문 (일부)
{paper.get('full_text', '')}
{notes_section}
---

다음 JSON 형식으로 분석 결과를 반환하세요. JSON 외에 다른 텍스트는 쓰지 마세요:

{{
  "title": "논문 제목",
  "authors": ["저자1", "저자2"],
  "year": 2024,
  "one_line_summary": "한 문장으로 이 논문의 핵심을 설명 (한국어)",
  "novelty": "기존 연구와 비교해서 무엇이 새로운지 2-3문장으로 설명 (한국어)",
  "key_contributions": ["핵심 기여 1", "핵심 기여 2", "핵심 기여 3"],
  "methodology": "사용된 방법론/아키텍처를 2-3문장으로 설명 (한국어)",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "tasks": ["task1", "task2"],
  "datasets": ["dataset1"],
  "metrics": ["metric1", "metric2"],
  "venue": "EMNLP 2024",
  "related_notes": ["기존 노트명1", "기존 노트명2"]
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=2000,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()
    analysis = json.loads(raw)

    # arXiv 정보 우선 사용 (메타데이터가 더 정확)
    if paper.get("title"):
        analysis["title"] = paper["title"]
    if paper.get("authors"):
        analysis["authors"] = paper["authors"]
    if paper.get("year"):
        analysis["year"] = paper["year"]
    if paper.get("arxiv_url"):
        analysis["arxiv_url"] = paper["arxiv_url"]

    return analysis
