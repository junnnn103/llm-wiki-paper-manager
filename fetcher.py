import re
import arxiv
import fitz  # PyMuPDF
import urllib.request
import tempfile
from pathlib import Path


def fetch_paper(source: str) -> dict:
    """arXiv URL, arXiv ID, or local PDF path를 받아서 paper 텍스트와 메타데이터 반환."""
    if source.endswith(".pdf") and Path(source).exists():
        return _from_pdf(source)

    arxiv_id = _extract_arxiv_id(source)
    if arxiv_id:
        return _from_arxiv(arxiv_id)

    raise ValueError(f"지원하지 않는 입력 형식: {source}\narXiv URL, arXiv ID, 또는 로컬 PDF 경로를 입력하세요.")





def _extract_arxiv_id(source: str) -> str | None:
    patterns = [
        r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)",
        r"^([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1)
    return None


def _from_arxiv(arxiv_id: str) -> dict:
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    results = list(client.results(search))
    if not results:
        raise ValueError(f"arXiv에서 논문을 찾을 수 없습니다: {arxiv_id}")

    paper = results[0]

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    paper.download_pdf(filename=tmp_path)
    text = _extract_text_from_pdf(tmp_path, max_chars=15000)
    references = _extract_references_section(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    return {
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "year": paper.published.year,
        "abstract": paper.summary,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
        "full_text": text,
        "references_text": references,
        "source_pdf": "",
    }


def _from_pdf(path: str) -> dict:
    text = _extract_text_from_pdf(path, max_chars=15000)
    references = _extract_references_section(path)
    return {
        "title": "",
        "authors": [],
        "year": None,
        "abstract": "",
        "arxiv_url": "",
        "full_text": text,
        "references_text": references,
        "source_pdf": str(Path(path).resolve()),
    }


def _extract_text_from_pdf(path: str, max_chars: int = 15000) -> str:
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


def _extract_references_section(path: str) -> str:
    """PDF 끝부분에서 References 섹션을 추출."""
    doc = fitz.open(path)
    # 마지막 페이지부터 역순으로 텍스트 수집
    pages_text = [page.get_text() for page in doc]
    doc.close()

    full_text = "\n".join(pages_text)

    # "References" 헤딩 이후 텍스트 추출 (대소문자 무관)
    import re
    match = re.search(r'\nReferences\s*\n', full_text, re.IGNORECASE)
    if match:
        return full_text[match.start():match.start() + 8000]

    # 못 찾으면 마지막 5000자 (references가 끝부분에 있을 가능성)
    return full_text[-5000:]
