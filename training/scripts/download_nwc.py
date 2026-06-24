"""
risen.runean.com에서 새찬송가 1~645장 NWC 파일 자동 다운로드.

사용법:
    python training/scripts/download_nwc.py --out data/nwc --start 1 --end 645
    python training/scripts/download_nwc.py --out data/nwc --hymns 1,101,200  # 특정 장만
    python training/scripts/download_nwc.py --out data/nwc --dry-run          # URL만 출력

동작:
    1. 목록 페이지(risen.runean.com/entry/찬송가-목록) → 각 장 URL 수집
    2. 각 장 페이지 → NWC 파일 URL(blog.kakaocdn.net) 추출
    3. 파일 다운로드 (새찬송가_{N}_4부.nwc / 새찬송가_{N}_합부.nwc)
    4. 요청 간격: 2~4초 (사이트 부하 배려)
"""

import argparse
import re
import time
import random
import logging
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE = "https://risen.runean.com"
LIST_URL = f"{BASE}/entry/%EC%B0%AC%EC%86%A1%EA%B0%80-%EB%AA%A9%EB%A1%9D"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": BASE,
    "Connection": "keep-alive",
}
DELAY_MIN, DELAY_MAX = 2.0, 4.0   # 요청 간격(초)


# ── 목록 페이지에서 각 장 URL 수집 ────────────────────────────────────────

def fetch_hymn_urls() -> dict[int, str]:
    """목록 페이지 → {장번호: 페이지URL} 딕셔너리 반환."""
    log.info("목록 페이지 로딩: %s", LIST_URL)
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    hymn_urls: dict[int, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        decoded = unquote(href)
        # /entry/찬송가-101장-... 또는 /entry/새찬송가-1장-...
        m = re.search(r"/entry/새?찬송가-(\d+)장-", decoded)
        if m:
            num = int(m.group(1))
            full = urljoin(BASE, href)
            if num not in hymn_urls:
                hymn_urls[num] = full

    log.info("찬송가 URL 수집 완료: %d장", len(hymn_urls))
    return hymn_urls


# ── 개별 장 페이지에서 NWC 다운로드 URL 추출 ─────────────────────────────

def fetch_nwc_links(page_url: str) -> list[tuple[str, str]]:
    """
    페이지 URL → [(파일명, 다운로드URL), ...] 반환.
    blog.kakaocdn.net/dna/ 경로의 .nwc 링크를 수집.
    """
    resp = requests.get(page_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "kakaocdn.net" in href and ".nwc" in href.lower() and href not in seen:
            seen.add(href)
            # URL에서 파일명 추출 (인코딩된 경로의 마지막 세그먼트)
            path_part = href.split("?")[0].split("/")[-1]
            filename = unquote(path_part)
            if not filename.lower().endswith(".nwc"):
                filename += ".nwc"
            results.append((filename, href))

    return results


# ── 파일 다운로드 ─────────────────────────────────────────────────────────

def download_file(url: str, dest: Path) -> bool:
    """URL → dest 파일로 저장. 성공 시 True."""
    if dest.exists():
        log.info("  이미 존재, 건너뜀: %s", dest.name)
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        log.info("  ✓ %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
        return True
    except Exception as e:
        log.warning("  ✗ 다운로드 실패 %s: %s", dest.name, e)
        return False


# ── 메인 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="risen.runean.com NWC 자동 다운로드")
    parser.add_argument("--out", default="data/nwc", help="저장 디렉터리")
    parser.add_argument("--start", type=int, default=1, help="시작 장 번호")
    parser.add_argument("--end", type=int, default=645, help="끝 장 번호")
    parser.add_argument("--hymns", help="특정 장만 (쉼표 구분, 예: 1,101,200)")
    parser.add_argument("--dry-run", action="store_true", help="URL만 출력, 다운로드 안 함")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 목록에서 URL 수집
    hymn_urls = fetch_hymn_urls()

    # 2. 대상 장 번호 필터링
    if args.hymns:
        targets = sorted(int(x) for x in args.hymns.split(","))
    else:
        targets = sorted(n for n in hymn_urls if args.start <= n <= args.end)

    log.info("처리 대상: %d장", len(targets))

    ok, fail, skip = 0, 0, 0

    for num in targets:
        if num not in hymn_urls:
            log.warning("목록에 없음: %d장", num)
            fail += 1
            continue

        page_url = hymn_urls[num]
        log.info("[%d장] %s", num, page_url)

        try:
            links = fetch_nwc_links(page_url)
        except Exception as e:
            log.warning("  페이지 로딩 실패: %s", e)
            fail += 1
            time.sleep(DELAY_MIN)
            continue

        if not links:
            log.warning("  NWC 링크 없음")
            fail += 1
        else:
            for orig_name, dl_url in links:
                # 파일명에 장번호 접두사 보장: 새찬송가_NNN_...
                stem = orig_name.replace(".nwc", "").replace(".NWC", "")
                # 이미 번호 있으면 그대로, 없으면 추가
                if not re.match(r"새?찬송가[_ ]\d+", stem):
                    stem = f"새찬송가_{num:03d}_{stem}"
                dest = out_dir / f"{stem}.nwc"

                if args.dry_run:
                    print(f"  [DRY] {dest.name}")
                    print(f"        {dl_url[:80]}...")
                    skip += 1
                else:
                    if download_file(dl_url, dest):
                        ok += 1
                    else:
                        fail += 1

        # 요청 간격
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(delay)

    log.info("완료 — 성공:%d  실패:%d  건너뜀:%d", ok, fail, skip)


if __name__ == "__main__":
    main()
