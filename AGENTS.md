# Thesis Project Instructions

## Main entry points
- `ThesisMain.tex`: main thesis document.
- `ThesisCover.tex`: separate cover document.
- Chapter source files are stored in numbered chapter directories.
- References are managed in `Bibliography/ThesisRef.bib`.

## Build on Ubuntu
Run:
```bash
chmod +x build.sh
./build.sh
```
The main outputs are `ThesisMain.pdf` and `ThesisCover.pdf`.

## Editing rules
- Do not modify `XThesis_skku_eng.sty`, `IEEEtran.cls`, or bibliography style files unless explicitly requested.
- Do not invent references, numerical results, experiments, or claims.
- Mark unfinished work as `planned`, `preliminary`, or `TBD`.
- Preserve labels, citation keys, and cross-references.
- Use formal academic English.
- Escape LaTeX special characters such as `%`, `_`, `&`, and `#`.
- Keep the page layout in `ThesisMain.tex` with equal top and bottom margins unless explicitly requested otherwise.

## Validation
- Compile the full thesis after editing.
- Fix compilation errors and broken references.
- Review the generated PDF for missing figures, clipping, and layout problems.
- Report unresolved warnings separately.
