# Build Notes

## Ubuntu dependencies
```bash
sudo apt update
sudo apt install -y git latexmk texlive-latex-extra texlive-fonts-recommended texlive-lang-korean texlive-bibtex-extra
```

## Build
```bash
chmod +x build.sh
./build.sh
```

The script runs:
1. `pdflatex ThesisMain.tex`
2. `bibtex ThesisMain`
3. `pdflatex ThesisMain.tex`
4. `pdflatex ThesisMain.tex`
5. `pdflatex ThesisCover.tex`

## Layout change in this version
- Top margin: 25 mm
- Bottom margin: 25 mm
- Left margin: 36 mm
- Right margin: 36 mm
- Default 50 pt blank space above chapter headings removed

The layout is defined in `ThesisMain.tex`. Do not modify the school style file only to change page margins.

## Known non-fatal warnings
- A `microtype` compatibility warning may appear with the legacy thesis template.
- A small overfull box may appear in a long title or table. Check the generated PDF after major edits.
