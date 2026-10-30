# 문헌 확인 기록

확인일: 2026-10-15. 기존 `Bibliography/ThesisRef.bib`를 출발점으로 원문/저자 공개 원문/공식 proceedings와 대조했다. 외부 그림은 사용하지 않았다. 아래 링크는 원문 확인과 BibTeX 항목의 근거이며 논문에서는 동일 citation key로 인용한다.

| Citation key | 확인한 1차 출처 | 사용 범위 |
|---|---|---|
| schneyer2023segmentation | [DLR 기록과 accepted manuscript](https://elib.dlr.de/196051/) | 자유곡면 segmentation, tool/workpiece geometry, contact area/spacing. 원본 bib의 Simon/Alexander를 실제 Stefan Schneyer/Arne Sachtler로 수정했다. 권호·쪽은 DLR 공식 기록을 따른다. |
| mohsin2019path | [출판사 원문](https://www.mdpi.com/2076-3417/9/24/5489), [저자기관 서지](https://research.cuhk.edu.hk/en/publications/path-planning-under-force-control-in-robotic-polishing-of-the-com-2/) | 경로·힘제어·공정 조건 결합, eyeglass frame과 품질 측정의 존재. 타 논문 수치를 본 실험 성과로 사용하지 않는다. |
| alt2024robogrind | [저자 원문 PDF](https://benjaminalt.github.io/assets/pdf/robogrind_ICRA24.pdf), [원문 HTML](https://arxiv.org/html/2402.16542v2) | III–VI의 인지·interactive wizard·경로·hybrid force-position control, VII–VIII의 blade refurbishment 범위. 권호·쪽은 별도로 확정하지 않아 생략했으며 본문의 내용 주장은 원문을 따른다. |
| chen2025dexforce | [DexForce v2 원문](https://arxiv.org/html/2501.10356v2) | III의 force-informed position targets, impedance replay, RGB+forces/moments observation; IV의 observation ablation. 별도 desired-force vector 출력으로 잘못 분류하지 않는다. 검증되지 않은 저널 정보는 넣지 않았다. |
| liu2025forcemimic | [ForceMimic v3 원문](https://arxiv.org/html/2410.07554v3), [저자 공식 코드 설명](https://github.com/ForceMimic/forcecapture) | III-A–C: handheld sensing, PC+TCP condition, wrench/pose output, orthogonal hybrid primitive. ICRA 2025 acceptance는 공식 코드에서 확인했다. 측정 force history가 관측에 있다고 가정하지 않는다. |
| he2025foar | [FoAR v2 원문](https://arxiv.org/html/2411.15753v2) | III와 appendix의 force/torque input, contact predictor, position reactive control; wiping/peeling/chopping. 원문 버전을 인용하며 journal DOI의 접근 실패를 확인된 내용과 분리한다. |
| zhou2024admitdiff | [저자 프로젝트](https://ryanjiao.github.io/AdmitDiffPolicy/), [원문 초록](https://arxiv.org/abs/2409.14440) | multimodal observation, action+desired force, admittance execution에 한정. 세부 차원·정량 우위를 표에 임의 추가하지 않는다. |
| zhao2023act | [RSS 공식 proceedings](https://roboticsproceedings.org/rss19/p016.html), [공식 PDF](https://www.roboticsproceedings.org/rss19/p016.pdf) | action chunks와 demonstration learning 배경. DOI와 저자·연도 확인. |
| chi2023diffusionpolicy | [저자 프로젝트와 BibTeX](https://diffusion-policy.cs.columbia.edu/), [저자 공개 원문](https://diffusion-policy.cs.columbia.edu/diffusion_policy_2023.pdf) | conditional action generation과 receding horizon. 방법 원 출처 RSS 2023을 인용한다. 기존 IJRR key는 보존 원본에 남는다. |
| lipman2023flow | [저자 arXiv 원문 기록](https://arxiv.org/abs/2210.02747) | Flow Matching 원리와 ICLR 2023 원 출처. 본 프로젝트의 선형 경로/손실/적분 세부는 직접 읽은 snapshot 코드에 근거한다. |
| simeoni2025dinov3 | [DINOv3 저자 원문](https://arxiv.org/abs/2508.10104) | visual backbone의 원 출처. 본 모델의 frozen 설정/ROI/fusion 차원은 로컬 config 및 소스에 근거한다. |
| hogan1985impedance | [저자 연구실 원문 PDF](https://newmanlab.mit.edu/wp-content/uploads/2017/09/1985-impedance-control-an-approach-to-manipulation-part-I-theory.pdf) | interaction dynamics/impedance 배경. Part I의 1–7쪽을 인용하며 원본의 Part I–III를 한 편처럼 쓰던 표기를 정리했다. |
| keemink2018admittance | [저자기관 원문](https://ris.utwente.nl/ws/files/29087621/admittance.pdf), [공식 서지](https://research.utwente.nl/en/publications/admittance-control-for-physical-human-robot-interaction/) | admittance의 force-to-motion 역할. 저자·권호·쪽·DOI 확인. |

예전 bib의 나머지 항목은 `provenance/original_latex/Bibliography/ThesisRef.bib`에 보존한다. 원문 확인 없이 그 기능·성과를 본문으로 옮기지 않는다. 각 연구의 실제 사용 인터페이스만 비교하고 서로 다른 연구의 성공률을 순위화하지 않는다.
