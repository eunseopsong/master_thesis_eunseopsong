# 잔여 경고

- `Package microtype Warning: Command \pickup@font is not defined as expected.`
- `pdfTeX warning (ext4): destination with the same identifier (name{page.1}) has been already used, duplicate ignored`

기존 KoTeX/microtype font patch와 표지/본문 page.1 PDF destination 경고다. 수정 전 ZIP의 빌드 로그에도 같은 경고가 있으며, 후속 수정에서 새 경고를 추가하지 않았다. page.1은 PDF 내부 페이지 anchor 경고이며 figure/table 번호나 LaTeX label 중복이 아니다. 컴파일 오류, 미정의 인용/참조, 중복 label, overfull box, 누락 glyph는 없다.
