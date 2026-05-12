import re
from datetime import date
from pathlib import Path
from config import OBSIDIAN_VAULT, PAPERS_FOLDER


def get_existing_notes() -> list[str]:
    return _get_existing_notes()


def write_to_obsidian(analysis: dict, deep_research: dict | None = None) -> Path:
    """Agent 2: 분석 결과를 Obsidian vault에 마크다운 노트로 저장."""
    PAPERS_FOLDER.mkdir(exist_ok=True)

    wikilinks = analysis.get("related_notes", [])
    content = _build_note(analysis, wikilinks, deep_research)

    filename = _safe_filename(analysis["title"]) + ".md"
    filepath = PAPERS_FOLDER / filename

    filepath.write_text(content, encoding="utf-8")
    return filepath


def _get_existing_notes() -> list[str]:
    notes = []
    for md_file in OBSIDIAN_VAULT.rglob("*.md"):
        if md_file.parent == PAPERS_FOLDER:
            continue
        if md_file.suffix == ".bak.md" or ".bak" in md_file.stem:
            continue
        notes.append(md_file.stem)
    return notes



def _build_note(analysis: dict, wikilinks: list[str], deep_research: dict | None = None) -> str:
    today = date.today().isoformat()
    authors = analysis.get("authors", [])
    authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    keywords_yaml = ", ".join(f'"{k}"' for k in analysis.get("keywords", []))
    tasks_yaml = ", ".join(f'"{t}"' for t in analysis.get("tasks", []))
    metrics_yaml = ", ".join(f'"{m}"' for m in analysis.get("metrics", []))

    contributions = "\n".join(f"- {c}" for c in analysis.get("key_contributions", []))
    wikilinks_str = " ".join(f"[[{w}]]" for w in wikilinks) if wikilinks else "(없음)"
    datasets = ", ".join(analysis.get("datasets", [])) or "없음"
    metrics = ", ".join(analysis.get("metrics", [])) or "없음"
    arxiv_url = analysis.get("arxiv_url", "")
    venue = analysis.get("venue", "")

    source_pdf = analysis.get("source_pdf", "")

    note = f"""---
title: "{analysis['title']}"
authors: [{authors_str}]
year: {analysis.get('year', '')}
venue: "{venue}"
arxiv: "{arxiv_url}"
source_pdf: "{source_pdf}"
keywords: [{keywords_yaml}]
tasks: [{tasks_yaml}]
metrics: [{metrics_yaml}]
added: {today}
---

{arxiv_url}
# Summary
"{analysis.get('one_line_summary', '')}"

# Novelty
{analysis.get('novelty', '')}

# Key Contributions
{contributions}

# Methodology
{analysis.get('methodology', '')}

# Datasets
{datasets}

# Metrics
{metrics}

# Related
{wikilinks_str}
{_build_citations_section(deep_research)}"""
    return note


def _build_citations_section(deep_research: dict | None) -> str:
    if not deep_research:
        return ""

    lines = []

    citations = deep_research.get("citations", [])
    if citations:
        lines.append("\n# Key Citations")
        for c in citations:
            url = c.get("url", "")
            link = f" ([link]({url}))" if url else ""
            title = _safe_filename(c.get("title", ""))
            concept = c.get("concept", "")
            concept_str = f" *({concept})*" if concept else ""
            lines.append(f"- [[{title}]]{concept_str} ({c.get('authors', '')}, {c.get('year', '')}){link}")
            lines.append(f"  - {c.get('reason', '')}")

    related = deep_research.get("related", [])
    lines.append("\n# Related Research")
    if related:
        for r in related:
            url = r.get("url", "")
            link = f" ([link]({url}))" if url else ""
            lines.append(f"- **{r.get('title', '')}** ({r.get('year', '')}){link}")
            lines.append(f"  - {r.get('significance', '')}")
    else:
        lines.append("(없음)")

    return "\n".join(lines) + "\n" if lines else ""


def _safe_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', "", title)
    title = title.strip()
    return title[:100]
