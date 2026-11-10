# 석사학위논문 최종 제출본

**Human-Guided Local Robotic Polishing via Joint Motion–Force Representation and Force-Conditioned Imitation Learning**
송은섭 (Eunseop Song) · 성균관대학교 대학원 지능형로봇학과

## 제출 파일

| 파일 | 용도 |
|---|---|
| `ThesisMain.pdf` | 학위논문 본문 (표지 · 속표지 · 제출서 · 인준서 · 목차 · 초록 · 본문 · 참고문헌 · 부록 · 논문요약) |
| `ThesisCover.pdf` | 제본용 표지와 책등(Side of Cover). 책등은 표지에만 인쇄하고 본문에는 넣지 않는다. |

## 양식

대학원 공식 영문 석사학위논문 양식(2026-10-16판)을 따른다.

- A4, 위·아래 여백 38 mm, 좌·우 30 mm, 쪽번호 위치 15 mm
- 본문 11 pt, 줄간격 200 %, 장 제목 16 pt, 절 제목 14 pt (Times 계열 / 명조 계열)
- 표지: Master's Thesis 14 pt, 제목 22 pt, 성명·학교 16 pt
- 제출서 `October 2026`, 인준서 `December 2026`, 책등 연도 `2027` — 양식에서 고정한 값으로 `thesis_metadata.tex`에 있다.
- 인준서의 심사위원 성명은 기본적으로 비워 둔다. 서명본(1부)에 성명을 인쇄하려면 `thesis_metadata.tex`의 `\approvalnamesfalse`를 `\approvalnamestrue`로 바꾼다.

## 빌드

```bash
./build.sh                        # ThesisMain.pdf, ThesisCover.pdf
python3 scripts/make_figures.py   # data/ 로부터 figures/*.pdf 재생성 (numpy, matplotlib, pillow)
```

pdfLaTeX, BibTeX, KoTeX가 필요하다. `~/texlive`에 사용자 설치본이 있으면 `build.sh`가 자동으로 사용한다.

## 구성

- `ThesisMain.tex` 본문 진입점, `ThesisCover.tex` 표지 진입점
- `thesis_metadata.tex` 제목·성명·심사위원·날짜, `frontmatter.tex` 표지·제출서·인준서·책등
- `abstract_eng.tex`, `abstract_kr.tex`, `chapters/`, `tables/`, `figures/`, `Bibliography/ThesisRef.bib`
- `data/` 그림과 표의 수치 원본, `scripts/make_figures.py` 그림 생성 스크립트

이전 원고, 검수 기록, 과거 제출 묶음은 Git 태그 `archive-pre-cleanup-20261110`(커밋 `c7b37f3`)에 그대로 남아 있다.
