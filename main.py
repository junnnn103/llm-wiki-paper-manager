#!/usr/bin/env python3
"""
PaperManager - 논문을 분석하고 Obsidian vault에 저장하는 CLI 도구

Usage:
    python main.py <pdf_or_arxiv>                기본 분석
    python main.py --deep <pdf_or_arxiv>         심층 분석 (핵심 인용 논문 추적 포함)
    python main.py --inbox                       Papers/Inbox/ 안의 PDF 전부 처리
    python main.py --inbox --deep                Papers/Inbox/ 안의 PDF 전부 심층 분석
    python main.py --lens <topic> <axis>         토픽을 새 축으로 분류해서 lens 페이지 생성
"""

import sys
from config import OPENAI_API_KEY, INBOX_DIR
from fetcher import fetch_paper
from analyzer import analyze_paper
from obsidian_writer import write_to_obsidian, get_existing_notes
from deep_researcher import run_deep_research
from topic_writer import update_topic_pages, get_topic_lenses
from lens_writer import run_lens


def process_paper(source: str, deep: bool, source_pdf_override: str = ""):
    print(f"\n[1/3] 논문 가져오는 중... {source}")
    paper = fetch_paper(source)
    print(f"      제목: {paper.get('title') or '(PDF에서 추출)'}")

    print("[2/3] 노벨티 및 키워드 분석 중...")
    existing_notes = get_existing_notes()
    analysis = analyze_paper(paper, existing_notes)
    analysis["source_pdf"] = source_pdf_override or paper.get("source_pdf", "")
    print(f"      키워드: {', '.join(analysis.get('keywords', []))}")

    deep_research = None
    if deep:
        print("[+] 심층 분석 중...")
        deep_research = run_deep_research(paper, analysis)
        print(f"      핵심 인용 논문 {len(deep_research.get('citations', []))}개 추출")

    print("[3/3] Obsidian vault에 저장 중...")
    filepath = write_to_obsidian(analysis, deep_research)
    print(f"      저장 완료: {filepath}")

    print("[+] 토픽 페이지 업데이트 중...")
    updated_topics = update_topic_pages(analysis)
    print(f"      토픽: {', '.join(updated_topics)}")

    lenses = get_topic_lenses(updated_topics)
    if lenses:
        print(f"[+] 연관 Lens 페이지 업데이트 중... ({len(lenses)}개)")
        for topic, axis in lenses:
            try:
                run_lens(topic, axis)
                print(f"      ✓ {topic} × {axis}")
            except Exception as e:
                print(f"      ✗ {topic} × {axis}: {e}")

    print(f"\n--- 분석 결과 ---")
    print(f"제목: {analysis['title']}")
    print(f"한 줄 요약: {analysis.get('one_line_summary', '')}")
    print(f"Novelty: {analysis.get('novelty', '')}")

    return analysis


def run_inbox(deep: bool):
    pdfs = sorted(INBOX_DIR.glob("*.pdf"))
    if not pdfs:
        print("Inbox가 비어있습니다.")
        return

    print(f"Inbox에서 PDF {len(pdfs)}개 발견\n{'='*50}")
    success, failed = [], []

    for pdf in pdfs:
        try:
            dest = pdf.parent.parent / pdf.name
            process_paper(str(pdf), deep, source_pdf_override=str(dest))
            pdf.rename(dest)
            success.append(pdf.name)
        except Exception as e:
            print(f"  오류: {e}")
            failed.append(pdf.name)

    print(f"\n{'='*50}")
    print(f"완료: {len(success)}개 처리, {len(failed)}개 실패")
    if failed:
        print(f"실패 (Inbox에 남김): {', '.join(failed)}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if not OPENAI_API_KEY:
        print("오류: OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")
        sys.exit(1)

    deep = "--deep" in sys.argv

    if "--inbox" in sys.argv:
        run_inbox(deep)
        return

    if "--lens" in sys.argv:
        idx = sys.argv.index("--lens")
        if len(sys.argv) < idx + 3:
            print("사용법: python main.py --lens <topic> <axis>")
            sys.exit(1)
        topic, axis = sys.argv[idx + 1], sys.argv[idx + 2]
        print(f"[Lens] '{topic}' × '{axis}' 분석 중...")
        filepath = run_lens(topic, axis)
        print(f"      저장 완료: {filepath}")
        return

    source = next(a for a in sys.argv[1:] if a not in ("--deep",))
    process_paper(source, deep)


if __name__ == "__main__":
    main()
