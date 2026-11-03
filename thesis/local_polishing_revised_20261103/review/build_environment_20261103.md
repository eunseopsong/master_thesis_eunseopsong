# 로컬 빌드 환경

이PC에는pdfLaTeX/KoTeX가설치되어있지않았다. Ubuntu jammy저장소에서TeX Live 2021/2022(dev)패키지를다운로드하고`dpkg-deb -x`로`/tmp/thesis-revision-20261103/texroot`에만풀었다. 시스템설치·전역환경·로봇환경은변경하지않았다.

필요패키지: texlive-binaries,texlive-base,texlive-latex-base,texlive-latex-recommended,texlive-latex-extra,texlive-pictures,texlive-fonts-recommended,texlive-lang-korean,texlive-lang-cjk,texlive-plain-generic,texlive-science,cm-super-minimal,cm-super,pfb2t1c2pfb. 기존시스템libkpathsea와Poppler를사용한다.

Debian의생성형fmtutil/updmap설정을패키지의`var/lib/tex-common`조각에서`/tmp/.../tex-config/web2c`로합쳤다. local `mktexlsr`, `fmtutil-sys --byfmt pdflatex`, `updmap-sys`로형식·fontmap을생성했다. cm-super의 압축 글꼴은 같은 /tmp 경로에서 t1c2pfb로 풀었다. 이파일/폰트는논문ZIP에포함하지않는다.

```bash
source /tmp/thesis-revision-20261103/tex-env.bash
export PERL5LIB="$THESIS_TEXROOT/usr/share/texlive/tlpkg:$TEXMFDIST/scripts/texlive"
cd /home/eunseop1/master_thesis_eunseopsong/thesis/local_polishing_revised_20261103
bash build.sh
```

정상Ubuntu TeX환경의동등명령은해당프로젝트에서`bash build.sh`다. 학교style/class/bst,제목/표지정보와상하25mm여백을유지한다. 실제최종실행결과는review의build로그와validation파일에기록한다.
