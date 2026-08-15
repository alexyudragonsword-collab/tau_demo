# tau_demo — Validating the τ Scaling Theory with a Full-Stack Cascade Simulation

English ｜ [中文](README.md)

An independent, simulation-based examination of the core ideas in Tingbo He's
(Huawei) *"A Time Scaling Theory for Multi-Layer Electronic Systems"*
(ChinaXiv:202605.00224).

A four-layer cascade model — transistor → circuit → chip/package → system —
with three embedded sub-models (LogicFolding, the N²-vs-N fan-out dilemma, and
UB cluster communication) tests the paper's five core propositions: P1 geometric
scaling flattens, P2 the folding criterion, P3 the topological deficit, P4
communication-τ compression, and P5 τ as a shared full-stack optimization target
with bottleneck migration.

**Findings: [REPORT.en.md](REPORT.en.md) · Adversarial review:
[CRITIQUE.en.md](CRITIQUE.en.md) · Development: [ARCHITECTURE.md](ARCHITECTURE.md)
(Chinese).**

> **Every model input comes from independent public literature** (each cited in
> `tau_sim/params.py`). The paper's own numbers are treated as *targets to
> reproduce*, never as model inputs — that is what makes agreement evidence
> rather than circularity.

## Quick start

```bash
pip install -r requirements.txt
python run_all.py           # figures/fig1-fig10 (Chinese labels) + console comparison
python run_all.py --lang en # figures_en/ (English labels)
python sensitivity.py       # robustness check: 17 parameters perturbed ±50%
```

## Tests

```bash
python tests/test_regression.py   # 14 golden-value groups — the guardrail for every number in the report
python tests/test_crosscheck.py   # JS port vs Python baseline, 22 metrics (needs node)
```

Both run standalone and under pytest. CI (`.github/workflows/ci.yml`) runs the
tests, generates both figure sets, checks sensitivity, and builds every page.

**If you change a model formula, run both tests** — `tau_lab_model.js` is a
hand-written port and does not follow the Python side automatically.

## Interactive GUIs (two versions)

```bash
streamlit run app.py    # full local version: 7 tabs, reuses all of tau_sim (incl. SimPy DES)
python build_tau_lab.py # builds tau_lab.html: zero-dependency single file, just double-click
```

Together they cover every simulation in the report (browser version: 6 panels;
Streamlit: 7 tabs) — device-layer scaling (P1), the folding workbench (criterion
crossing + thermal constraint), package N²-vs-N, cluster communication (large/small
message regimes, with UB parameters open to stress-testing), cascade experiments
A/B/C/D (bottleneck migration / Amdahl / decade trajectory / α decomposition), and
a **sensitivity scan** (interactive tornado diagram over 12 parameters × 5 metrics,
plus a 1D sweep that shades the conclusion-flip region). The only thing missing
from the browser build is the SimPy discrete-event validation (simpy cannot run
in JS); it lives in the Streamlit app.

## Reports and presentation material

```bash
python build_report.py        # report_full.html + report_full.pdf (PDF needs playwright)
python build_report.py --html # HTML only
python build_critique.py      # critique.html (adversarial appendix)
python build_dashboard.py     # dashboard.html (visual report page)
node build_slides.js          # slides_tau_scaling.pptx (8-slide deck; needs npm i pptxgenjs)
```

> **Bilingual**: all four HTML pages (`dashboard.html`, `tau_lab.html`,
> `report_full.html`, `critique.html`) carry a 中/EN toggle in the top-right
> corner; both prose and figures switch with the language (English uses
> `figures_en/`).

## Results at a glance

| Proposition | Simulation result | Paper's claim |
|---|---|---|
| P1 interconnect takes the delay budget | share 22%→72%; stage delay rises again beyond 5 nm | "local interconnect parasitic R, C overtake intrinsic delay" |
| P2 folding wirelength / skew / frequency | −24.9% / −24.9% / +12.3% | −30% / −25% / +13% (Kirin 2026) |
| P2 criterion flip point | gear ratio ≈ 4.3 (sensitivity band 3.3–6.2) | engineering rule < 3 (conservative side) |
| P3 2.5D ridge rises | beyond N ≈ 55 mm even GEMM is memory-bound | "no transistor-level gain closes a topological deficit" |
| P4 small-message all-to-all | same physical link, swapped stack: 9.8× (RDMA) / 159× (TCP) | UB ≈ 500× τ compression |
| P5 decade annualized α | coordinated 1.22 vs single-point 1.02–1.08 | τ_{n+1}=τ_n/α needs cross-layer synergy |
| Thermal constraint | heterogeneous fold sustains f ≈ 0.98; homogeneous 0.80 | paper's open problem §6; AMD X3D corroborates |
| α ≈ 10/yr accounting | hardware three factors ≈ 2.0/yr; only 1.67 when efficiency collapses | τ compression's job is holding α_eff ≈ 1 |

## Repository layout

```
tau_sim/                  # simulation model (four layers + thermal + cascade)
├── params.py             # all calibrated parameters, each with its literature source
├── layer1_device.py      # device: FO4 + Cu interconnect size effect
├── layer2_circuit.py     # circuit: Davis wirelength distribution + LogicFolding
├── layer3_chip.py        # package: N²-vs-N + roofline
├── layer4_system.py      # system: α-β collectives + SimPy discrete-event simulation
├── thermal.py            # thermal: sustainable frequency of multi-tier folding
└── cascade.py            # cascade: Amdahl / decade / bottleneck migration / α decomposition
tests/                    # regression tests + JS↔Python cross-check
run_all.py                # runs every experiment (--lang en for English figures)
sensitivity.py            # sensitivity check (17 perturbations)
app.py                    # Streamlit GUI (7 tabs)
tau_lab_model.js          # hand-written JS port of the model (kept honest by the cross-check test)
tau_lab_template.html     # browser τ Lab template (with i18n)
build_*.py / build_slides.js   # build pipelines for pages, reports and slides
figures/  figures_en/     # generated figures (Chinese / English label sets)
REPORT.md   REPORT.en.md  # full analysis report (reading of the paper + results + limits)
CRITIQUE.md CRITIQUE.en.md# adversarial appendix (assumptions most open to challenge)
ARCHITECTURE.md           # architecture and development guide
CHANGELOG.md              # release history (each entry flags whether conclusions changed)
ROADMAP.md                # open work (separates this simulation's debts from the paper's open questions)
```
