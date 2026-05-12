"""
Lens - 특정 토픽의 논문들을 새로운 분류 축으로 분석해서 wiki 페이지 생성

Usage:
    python main.py --lens <topic> <axis>
    예: python main.py --lens "Multi-Agent Systems" "topology"
"""

import json
import re
import fitz
from datetime import date
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OBSIDIAN_VAULT, TOPICS_FOLDER

PAPERS_FOLDER = OBSIDIAN_VAULT / "Papers"
LENS_FOLDER = OBSIDIAN_VAULT / "Lens"


def run_lens(topic: str, axis: str) -> Path:
    """토픽 내 논문들을 axis 기준으로 분류해서 lens 페이지 생성."""
    LENS_FOLDER.mkdir(exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)

    # 1. 토픽 페이지에서 논문 목록 가져오기
    papers = _get_papers_in_topic(topic)
    if not papers:
        raise ValueError(f"토픽 '{topic}'에 논문이 없거나 토픽 페이지를 찾을 수 없습니다.")

    print(f"  {len(papers)}개 논문 발견")

    # 2. Stage 1: md로 pre-screening (논문 20개 이상일 때 효과적, 이하면 전부 PDF로)
    if len(papers) >= 20:
        print(f"  [Stage 1] md 파일로 '{axis}' 관련 논문 선별 중...")
        candidates = _stage1_filter(papers, axis, client)
        print(f"  → {len(candidates)}개 논문 선별됨 (전체 {len(papers)}개 중)")
    else:
        candidates = papers
        print(f"  [Stage 1] 논문 수 적음 — 전체 {len(papers)}개 PDF 직접 확인")

    # 3. Stage 2: PDF 재읽기
    print(f"  [Stage 2] PDF에서 '{axis}' 정보 추출 중...")
    enriched = _stage2_extract(candidates, axis, client)

    # 4. 분류 및 페이지 생성
    print(f"  분류 및 페이지 생성 중...")
    filepath = _build_lens_page(topic, axis, enriched, client)
    return filepath


def _get_papers_in_topic(topic: str) -> list[dict]:
    """토픽 페이지에서 논문 목록과 source_pdf 경로 수집."""
    topic_file = TOPICS_FOLDER / f"{_safe_filename(topic)}.md"
    if not topic_file.exists():
        return []

    content = topic_file.read_text(encoding="utf-8")
    papers = []

    for line in content.splitlines():
        m = re.match(r'\|\s*\[\[(.+?)\]\]\s*\|', line)
        if not m:
            continue
        note_title = m.group(1)

        # Papers 폴더에서 해당 md 파일 찾기
        note_path = PAPERS_FOLDER / f"{note_title}.md"
        if not note_path.exists():
            # 100자 truncation 고려해서 prefix 매칭
            matches = list(PAPERS_FOLDER.glob(f"{note_title[:80]}*.md"))
            note_path = matches[0] if matches else None

        if note_path and note_path.exists():
            note_content = note_path.read_text(encoding="utf-8")
            source_pdf = _parse_frontmatter_field(note_content, "source_pdf")
            papers.append({
                "title": note_title,
                "note_content": note_content,
                "source_pdf": source_pdf,
            })

    return papers


def _stage1_filter(papers: list[dict], axis: str, client: OpenAI) -> list[dict]:
    """md 파일의 methodology/contributions만 보고 axis 관련 정보가 있을지 판단."""
    candidates = []
    for p in papers:
        # md에서 핵심 섹션만 추출
        snippet = _extract_md_snippet(p["note_content"])

        prompt = f"""다음 논문 요약을 보고, 이 논문이 "{axis}"와 완전히 무관한지 판단하세요.
확실히 무관한 경우에만 false로 표시하고, 조금이라도 관련 있을 가능성이 있으면 true로 표시하세요.

{snippet}

JSON으로 반환:
{{"relevant": true/false, "reason": "한 줄 이유", "md_evidence": "md에서 찾은 관련 내용 (없으면 빈 문자열)"}}"""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=200,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(response.choices[0].message.content)
        if result.get("relevant", True):  # 불확실하면 포함
            p["md_evidence"] = result.get("md_evidence", "")
            candidates.append(p)

    return candidates


def _stage2_extract(candidates: list[dict], axis: str, client: OpenAI) -> list[dict]:
    """PDF를 재읽어서 axis 관련 정보를 정밀하게 추출. md만으로 충분하면 PDF 스킵."""
    enriched = []
    for p in candidates:
        # md 근거가 충분하면 PDF 스킵
        if len(p.get("md_evidence", "")) > 50:
            p["extracted"] = p["md_evidence"]
            p["source"] = "md"
            enriched.append(p)
            continue

        # PDF 재읽기
        source_pdf = p.get("source_pdf", "")
        if source_pdf and Path(source_pdf).exists():
            pdf_text = _read_pdf_text(source_pdf, max_chars=12000)
            prompt = f"""다음 논문 본문에서 "{axis}"와 관련된 내용을 찾아 추출하세요.
"{axis}"라는 단어가 직접 등장하지 않아도 됩니다. 관련 개념, 구조, 패턴을 넓게 해석해서 찾으세요.
예를 들어 "topology"라면 에이전트 간 연결 구조, centralized/decentralized, 역할 분배 방식 등도 포함합니다.

논문 본문:
{pdf_text}

이 논문에서 "{axis}" 관점에서 설명할 수 있는 내용을 반드시 찾아 요약하세요.
JSON으로 반환:
{{"extracted": "추출한 내용 (한국어 2-3문장, 반드시 작성)"}}"""

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=300,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            result = json.loads(response.choices[0].message.content)
            p["extracted"] = result.get("extracted", "")
            p["source"] = "pdf"
            enriched.append(p)
        else:
            p["extracted"] = p.get("md_evidence", "")
            p["source"] = "md"
            if p["extracted"]:
                enriched.append(p)

    return enriched


def _build_lens_page(topic: str, axis: str, papers: list[dict], client: OpenAI) -> Path:
    """추출한 정보를 분류해서 lens 페이지 생성."""
    if not papers:
        raise ValueError(f"'{axis}' 관련 정보를 찾은 논문이 없습니다.")

    papers_info = "\n\n".join(
        f"논문: {p['title']}\n내용: {p['extracted']}"
        for p in papers
    )

    prompt = f"""다음 논문들에서 추출한 "{axis}" 관련 정보를 분류해서 정리하세요.

{papers_info}

결과를 JSON으로 반환하세요:
{{
  "categories": [
    {{
      "name": "분류명",
      "papers": [
        {{"title": "논문 제목 (원문 그대로)", "detail": "이 논문에서 해당 분류가 어떻게 사용됐는지 1-2문장"}}
      ]
    }}
  ],
  "summary": "전체적인 흐름 요약 (한국어, 3-4문장)"
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1000,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    result = json.loads(response.choices[0].message.content)

    content = _render_lens_page(topic, axis, result)
    filename = f"Lens - {_safe_filename(topic)} × {_safe_filename(axis)}.md"
    filepath = LENS_FOLDER / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _render_lens_page(topic: str, axis: str, result: dict) -> str:
    today = date.today().isoformat()
    categories = result.get("categories", [])

    sections = []
    for cat in categories:
        rows = "\n".join(
            f"| [[{_safe_filename(p['title'])}]] | {p['detail']} |"
            for p in cat.get("papers", [])
        )
        sections.append(
            f"## {cat['name']}\n| 논문 | 설명 |\n|------|------|\n{rows}"
        )

    return f"""---
topic: "{topic}"
axis: "{axis}"
updated: {today}
---

# {topic} × {axis}

{chr(10).join(sections)}

## 종합
{result.get('summary', '')}
"""


def _extract_md_snippet(content: str) -> str:
    """md에서 Methodology, Key Contributions, Summary 섹션만 추출."""
    sections = []
    for heading in ["# Summary", "# Key Contributions", "# Methodology"]:
        m = re.search(rf'{re.escape(heading)}\n(.*?)(?=\n#|\Z)', content, re.DOTALL)
        if m:
            sections.append(f"{heading}\n{m.group(1).strip()}")
    return "\n\n".join(sections)[:3000]


def _parse_frontmatter_field(content: str, field: str) -> str:
    m = re.search(rf'^{field}:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _read_pdf_text(path: str, max_chars: int = 12000) -> str:
    doc = fitz.open(path)
    pages = []
    total = 0
    for page in doc:
        t = page.get_text()
        pages.append(t)
        total += len(t)
        if total >= max_chars:
            break
    doc.close()
    return "\n".join(pages)[:max_chars]


def _safe_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', "", title)
    return title.strip()[:80]
