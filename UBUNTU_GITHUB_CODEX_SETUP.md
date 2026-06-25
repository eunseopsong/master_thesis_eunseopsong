# Ubuntu, GitHub, and Codex Setup

## 1. Install LaTeX and Git
```bash
sudo apt update
sudo apt install -y git latexmk texlive-latex-extra texlive-fonts-recommended texlive-lang-korean texlive-bibtex-extra
```

## 2. Build the thesis
```bash
chmod +x build.sh
./build.sh
```

## 3. Create a private GitHub repository
From this project directory:
```bash
git init
git branch -M main
git add .
git commit -m "Initial thesis LaTeX project"
git remote add origin https://github.com/<USER>/<REPOSITORY>.git
git push -u origin main
```

## 4. Use Codex locally
Open the full project directory in VS Code or run Codex from the repository root. The project-level instructions are in `AGENTS.md`.
