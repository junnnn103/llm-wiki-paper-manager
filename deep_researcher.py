"""
Deep Research Agent - 논문 심층 분석

현재 구현:
  - citation_tracking: 핵심 인용 논문 추적 및 읽기 추천
  - related_research: Semantic Scholar로 후속 연구 검색

TODO (vault가 50개 이상 쌓이면 구현):
  - vault_comparison: 노트 임베딩 기반 RAG로 vault 내 논문과 비교 분석
    (현재는 파일명 목록만 GPT에 넘기지만, 규모 커지면 벡터 DB 필요)
"""

import json
import urllib.request
import urllib.parse
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL


def run_deep_research(paper: dict, analysis: dict) -> dict:
    print("  [deep] 핵심 인용 논문 추적 중...")
    citations = citation_tracking(paper, analysis)

    print("  [deep] 관련 후속 연구 검색 중...")
    related = related_research(analysis)

    return {"citations": citations, "related": related}


def citation_tracking(paper: dict, analysis: dict) -> list[dict]:
    """논문의 레퍼런스에서 핵심 인용 논문을 추출하고 읽기 우선순위를 매긴다."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    references_block = paper.get("references_text", "")
    references_section = f"\n## References 원문 (제목은 반드시 여기서 그대로 복사)\n{references_block}" if references_block else ""

    prompt = f"""다음 논문의 본문을 분석하여, 이 논문을 제대로 이해하기 위해 읽어야 할 핵심 인용 논문 5개를 선별해주세요.

## 논문 제목
{analysis.get('title', '')}

## 본문 (일부)
{paper.get('full_text', '')}
{references_section}
---

**중요**: title 필드에는 반드시 위 References 원문에 적힌 논문 제목을 한 글자도 바꾸지 말고 그대로 복사하세요. 절대 요약하거나 다르게 표현하지 마세요.

다음 JSON 형식으로 반환하세요. JSON 외 텍스트는 쓰지 마세요:

{{
  "key_citations": [
    {{
      "title": "References 원문에서 복사한 정확한 제목",
      "concept": "이 논문과 연관된 핵심 개념/정리 이름 (예: Hong-Page Theorem, Transformer, RLHF). 없으면 빈 문자열",
      "authors": "저자명 (et al. 형식 가능)",
      "year": 2020,
      "reason": "이 논문을 읽어야 하는 이유 (한국어, 1-2문장)"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1500,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )

    result = json.loads(response.choices[0].message.content)
    citations = result.get("key_citations", [])

    for citation in citations:
        citation["url"] = _search_semantic_scholar(citation.get("title", "")) or ""

    return citations


def related_research(analysis: dict) -> list[dict]:
    """Semantic Scholar에서 이 논문을 인용한 후속 연구를 찾고 GPT로 요약한다."""
    title = analysis.get("title", "")
    year = analysis.get("year") or 0

    # 1. 논문의 Semantic Scholar paper_id 획득
    paper_id = _get_paper_id(title)
    if not paper_id:
        return []

    # 2. 이 논문을 인용한 논문 목록 가져오기
    citing_papers = _get_citing_papers(paper_id)
    if not citing_papers:
        return []

    # 3. GPT로 가장 관련 있는 후속 연구 선별 및 요약
    client = OpenAI(api_key=OPENAI_API_KEY)
    papers_list = "\n".join(
        f"- {p['title']} ({p.get('year', '?')}) — {p.get('abstract', '')[:200]}"
        for p in citing_papers[:20]
    )

    prompt = f"""다음은 "{title}" 논문을 인용한 후속 연구 목록입니다.
이 중 가장 주목할 만한 논문 3개를 선별하고, 왜 중요한지 설명해주세요.

{papers_list}

다음 JSON 형식으로 반환하세요. JSON 외 텍스트는 쓰지 마세요:

{{
  "related_papers": [
    {{
      "title": "논문 제목",
      "year": 2024,
      "significance": "이 후속 연구가 중요한 이유 (한국어, 1-2문장)"
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1000,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )

    result = json.loads(response.choices[0].message.content)
    related = result.get("related_papers", [])

    # URL 보강
    citing_by_title = {p["title"].lower(): p for p in citing_papers}
    for r in related:
        match = citing_by_title.get(r["title"].lower())
        r["url"] = match.get("url", "") if match else ""

    return related


def _get_paper_id(title: str) -> str | None:
    try:
        query = urllib.parse.quote(title)
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=1&fields=title,paperId"
        req = urllib.request.Request(url, headers={"User-Agent": "PaperManager/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        papers = data.get("data", [])
        return papers[0].get("paperId") if papers else None
    except Exception:
        return None


def _get_citing_papers(paper_id: str) -> list[dict]:
    try:
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
            f"?fields=title,year,externalIds,abstract&limit=20"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "PaperManager/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        results = []
        for item in data.get("data", []):
            p = item.get("citingPaper", {})
            ids = p.get("externalIds", {})
            if ids.get("ArXiv"):
                url_str = f"https://arxiv.org/abs/{ids['ArXiv']}"
            else:
                pid = p.get("paperId", "")
                url_str = f"https://www.semanticscholar.org/paper/{pid}" if pid else ""
            results.append({
                "title": p.get("title", ""),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "url": url_str,
            })
        return results
    except Exception:
        return []


def _search_semantic_scholar(title: str) -> str | None:
    try:
        query = urllib.parse.quote(title)
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=1&fields=title,externalIds"
        req = urllib.request.Request(url, headers={"User-Agent": "PaperManager/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        papers = data.get("data", [])
        if not papers:
            return None
        ids = papers[0].get("externalIds", {})
        if ids.get("ArXiv"):
            return f"https://arxiv.org/abs/{ids['ArXiv']}"
        paper_id = papers[0].get("paperId", "")
        return f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None
    except Exception:
        return None
