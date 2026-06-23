# NWC 악보 파일 출처

## 새찬송가 분리악보 (4부악보) · 합부악보

### 주요 출처: 라이즌 찬양 (risen.runean.com)

- **사이트**: https://risen.runean.com
- **형식**: Tistory 블로그, 찬송가별 개별 포스트
- **URL 패턴**: `https://risen.runean.com/entry/새찬송가-{N}장-{제목}-가사악보NWC`
- **파일**: 각 포스트에 분리악보(4부) + 합부악보 NWC 2개 제공
- **CDN**: blog.kakaocdn.net (signed URL, `expires` 파라미터 포함 — 장기 유효)
- **다운로드 방법**: 페이지 HTML에서 `blog.kakaocdn.net/*.nwc?credential=...` URL 추출 후 curl

#### 취득 현황 (2026-06-23)
| 구분 | 파일 수 | 비고 |
|------|--------|------|
| 분리악보 (`nwc/분리/`) | 645개 | 003~009 · 490 이 사이트에서 보완 |
| 합부악보 (`nwc/합부/`) | 553개 | 003~009 이 사이트에서 보완, 490 합부악보 CDN 404 |

---

### 보조 출처: Daum 카페 — 어린이책작가 윤영선 작업실

- **사이트**: https://m.cafe.daum.net/iiworld/SGU7/8
- **형식**: 개별 `.NWC` 파일 직접 링크 (`cfile*.uf.daum.net/attach/...`)
- **내용**: 새찬송가 전곡 4부 파트별 NWC (분리악보)
- **사용**: `490 주여 지난 밤 내꿈에.NWC` — risen.runean.com CDN 404로 여기서 대체 취득

---

### 참고: 전곡 압축 파일

| 링크 | 내용 |
|------|------|
| `http://cfile240.uf.daum.net/attach/260E4E3B54C2554726D11F` | 찬송가전곡nwc(4부파트별).zip |
| `http://cfile208.uf.daum.net/attach/227E6A3B54C2554832C3AF` | 찬송가전곡nwc(합보).zip |
| `http://bcch.kr/bbs/board.php?bo_table=tb06_0104&wr_id=227` | 새찬송가 NWC악보 (1장~645장) 압축파일 (포인트 필요) |
