import json
import re
from datetime import date
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, TOPICS_FOLDER


def update_topic_pages(analysis: dict) -> list[str]:
    """논문 분석 결과를 바탕으로 관련 토픽 페이지 생성/업데이트. 업데이트된 토픽명 반환."""
    TOPICS_FOLDER.mkdir(exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)

    existing_topics = _get_existing_topics()
    topics = _decide_topics(analysis, existing_topics, client)

    updated = []
    for topic in topics:
        papers = _load_topic_papers(topic)

        new_entry = {
            "title": analysis["title"],
            "year": analysis.get("year", ""),
            "contribution": (analysis.get("key_contributions") or [""])[0][:80],
        }
        if not any(_safe_filename(p["title"]) == _safe_filename(new_entry["title"]) for p in papers):
            papers.append(new_entry)

        flow = _synthesize_flow(topic, papers, client)
        _save_topic_page(topic, papers, flow)
        updated.append(topic)

    return updated


def _get_existing_topics() -> list[str]:
    if not TOPICS_FOLDER.exists():
        return []
    return [f.stem for f in TOPICS_FOLDER.glob("*.md")]


def _decide_topics(analysis: dict, existing_topics: list[str], client: OpenAI) -> list[str]:
    """이 논문이 속하는 토픽 2-3개 결정. 기존 토픽 우선 재사용."""
    existing_str = "\n".join(f"- {t}" for t in existing_topics) if existing_topics else "(없음)"

    prompt = f"""다음 논문을 분류할 토픽 2-3개를 결정하세요.

## 논문 정보
제목: {analysis.get('title', '')}
키워드: {', '.join(analysis.get('keywords', []))}
태스크: {', '.join(analysis.get('tasks', []))}
핵심 기여: {', '.join(analysis.get('key_contributions', []))}

## 기존 토픽 목록
{existing_str}

규칙:
- 기존 토픽과 같은 개념이면 정확히 그 이름 사용
- 새 토픽은 간결하고 일반적인 영어 이름 (예: "Multi-Agent Systems", "LLM Reasoning", "Decision Making")
- 2-3개만 선택

JSON으로 반환:
{{"topics": ["토픽1", "토픽2"]}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=200,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("topics", [])[:3]


def _load_topic_papers(topic: str) -> list[dict]:
    """기존 토픽 페이지에서 논문 목록 파싱."""
    filepath = TOPICS_FOLDER / f"{_safe_filename(topic)}.md"
    if not filepath.exists():
        return []

    content = filepath.read_text(encoding="utf-8")
    papers = []
    for line in content.splitlines():
        m = re.match(r'\|\s*\[\[(.+?)\]\]\s*\|\s*(\d*)\s*\|\s*(.+?)\s*\|', line)
        if m:
            papers.append({
                "title": m.group(1),
                "year": m.group(2),
                "contribution": m.group(3).strip(),
            })
    return papers


def _synthesize_flow(topic: str, papers: list[dict], client: OpenAI) -> str:
    """GPT로 토픽 내 연구 흐름 요약 생성."""
    if len(papers) == 1:
        return papers[0].get("contribution", "")

    papers_str = "\n".join(
        f"- ({p.get('year', '?')}) {p['title']}: {p['contribution']}"
        for p in sorted(papers, key=lambda x: str(x.get("year", "")))
    )

    prompt = f"""다음은 "{topic}" 토픽의 논문 목록입니다.
이 논문들의 연구 흐름을 3-4문장으로 요약하세요. (한국어)
어떤 문제에서 시작해서 어떻게 발전했는지, 현재 주요 방향은 무엇인지 중심으로.

{papers_str}

흐름 요약 텍스트만 반환하세요."""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def _save_topic_page(topic: str, papers: list[dict], flow_summary: str):
    today = date.today().isoformat()
    sorted_papers = sorted(papers, key=lambda x: str(x.get("year", "")))

    rows = "\n".join(
        f"| [[{_safe_filename(p['title'])}]] | {p.get('year', '')} | {p['contribution']} |"
        for p in sorted_papers
    )
    table = f"| 논문 | 연도 | 핵심 기여 |\n|------|------|----------|\n{rows}"

    content = f"""---
topic: "{topic}"
updated: {today}
paper_count: {len(papers)}
---

# {topic}

## 논문 목록
{table}

## 흐름 요약
{flow_summary}
"""
    filepath = TOPICS_FOLDER / f"{_safe_filename(topic)}.md"
    filepath.write_text(content, encoding="utf-8")


def _safe_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', "", title)
    return title.strip()[:100]
