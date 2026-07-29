# Using a Full-Stack τ Cascade Simulation to Argue the Core Ideas of "A Time Scaling Theory for Multi-Layer Electronic Systems"

> Paper under validation: He Tingbo (Huawei), *A Time Scaling Theory for Multi-Layer Electronic Systems*, ChinaXiv:202605.00224v1 (2026-05-25)
> This report: a four-layer cascade simulation model calibrated against independent public literature, reproducing and testing the paper's five core propositions.
> How to reproduce: `pip install -r requirements.txt && python run_all.py` (figures written to `figures/`), `python sensitivity.py` (sensitivity check).

---

## 1. Reading the Paper's Core Thesis

### 1.1 The through-line: from geometric scaling to time scaling

The paper's central thesis is: **the essence of Moore's Law was never "smaller" but "faster"**—transistor shrinking delivered value because switching got faster, signals traveled shorter distances, and fewer boundaries were crossed. Spatial scaling was only a *means* of compressing time. Once this means fails below 7nm (velocity saturation, interconnect parasitics dominating, cost inversion), the **characteristic time constant τ** should be taken directly as the first-order optimization target, defined and compressed at every layer of the stack:

```
τ = f(τ_transistor, τ_circuit, τ_chip, τ_system)      spanning ~12 orders of magnitude (ps → s)
τ_{n+1} = τ_n / α                                      α varies by application (mobile ~1.3/yr, AI up to 10/yr)
```

τ's unique value lies in **one shared dimension across the full stack**: process engineers, circuit designers, and system architects can, for the first time, discuss the same quantity in the same unit, making cross-layer co-optimization possible.

### 1.2 Five simulation-testable propositions

| # | Proposition | Paper basis | Correspondence in this simulation |
|---|------|---------|------------|
| P1 | Pure geometric scaling benefits flatten below 7nm: velocity saturation degrades intrinsic delay from ∝L² to ∝L; local interconnect parasitic RC overtakes the transistor's intrinsic delay | §1, §2 | Layer 1 device model |
| P2 | LogicFolding: at a fixed node, vertical folding shortens wire length↓, raises frequency↑, raises density↑, with criterion τ_Benefit > τ_Penalty; measured wire length −30%, frequency +13%, density 155→238 MTr/mm², skew −25%, gear ratio must be <3 | §3 | Layer 2 circuit model |
| P3 | N²-vs-N fan-out dilemma: 2.5D packaging compute ∝N² (area) while bandwidth/power ∝N (perimeter); the topological deficit cannot be closed by transistor improvements; 3D Folding moves edge resources to the surface to restore N² alignment | §4.3 | Layer 3 packaging model |
| P4 | The UB memory-semantic bus eliminates protocol conversion, cutting remote-access τ from tens of μs → ~100ns (≈500×), letting the cluster approach a "single-chip system" | §4.1-4.2 | Layer 4 cluster model |
| P5 | **Methodological meta-proposition**: τ is the first full-stack-shared optimization target since Dennard; a single-layer improvement only counts if it propagates to system τ; "the dominant τ layer is the next investment direction" | §2, §6, §7 | Cascade experiments A/B/C |

### 1.3 Calibration principle (avoiding circular reasoning)

The paper's own data (Kirin measurements, UB 500×) **serve only as target-to-reproduce counterpoints, not as model inputs**. All model inputs are taken from independent public literature (IRDS, IEEE papers, NVIDIA/imec/TSMC public data, MLSys/NSDI measurements); see the §3 parameter table. Only when the simulation results match the paper's numbers do they constitute independent corroboration of the paper.

---

## 2. Overall Model Architecture

```
Layer 1 device      FO4 gate delay (α-power law) + copper interconnect size effect
      ↓ provides gate delay, wire RC
Layer 2 circuit     Davis a-priori wire-length distribution + optimal-repeater delay + folding geometry (LogicFolding)
      ↓ provides frequency (→k_compute)
Layer 3 packaging   compute ∝N² vs edge bandwidth ∝N / surface bandwidth ∝N² + roofline
      ↓ provides memory supply (→k_memory)
Layer 4 system      α-β collective-communication cost model + SimPy discrete-event simulation (→t_comm)
      ↓
cascade  τ_iter = t_compute + t_memory + t_comm + t_other   (4096-GPU LLM training iteration)
```

Code structure: `tau_sim/layer1_device.py` → `layer2_circuit.py` → `layer3_chip.py` → `layer4_system.py` → `cascade.py`, with all parameters centralized in `tau_sim/params.py`.

---

## 3. Parameter Calibration Table (deep-research results, independent of the paper under validation)

| Parameter | Value | Source |
|------|------|------|
| FO4 gate delay 28/16/7/5/3nm | 15/11/8/7/6 ps (±30%) | Harris FO4 metric; Stillmaker & Baas, *Integration VLSI J.* 2017 (PTM HSPICE) |
| Velocity-saturation exponent α | 1.25 | Sakurai & Newton, *IEEE JSSC* 25(2), 1990; Rabaey textbook default 1.3 |
| Wire capacitance | 0.2 fF/μm (near-constant across nodes) | Harris HMC E158; UT-Austin VLSI lecture notes |
| Copper resistivity size effect | ρ(w) ≈ 1.68·(1+40nm/w) μΩ·cm | Steinhögl et al. measured fit (40nm→~3, 18nm→~9 μΩ·cm incl. barrier); imec BEOL |
| Rent exponent p | 0.62 (high-speed logic 0.6–0.75) | Bakoglu 1990; Landman & Russo 1971 |
| A-priori wire-length distribution | Davis closed-form structural factor | Davis, De, Meindl, *IEEE TED* 45(3), 1998 |
| 3D wire-length contraction | theoretical 1/√k × efficiency 0.85 (measured 2-layer 16–25%) | Rahman & Reif, *IEEE TVLSI* 2000; OpenSPARC T2 case |
| Hybrid bonding R / C | 0.3 Ω / 0.2 fF @2μm pitch (scales with pad area) | imec ECTC (measured 79.5 mΩ/point); TSMC SoIC ECTC 2019 |
| Hybrid bonding pitch, state of the art | mass production 6μm → R&D 2μm (D2W) / 0.4μm (W2W) | TSMC SoIC roadmap; imec 2024–2025 |
| Clock margin | 10% of path delay (skew budget 5–10%) | Harris, *Clock Skew Budgets*, 2002 |
| Compute/memory density anchors | 1.2 TFLOPS/mm² (BF16); HBM3E 1.2TB/s/stack, stack width ~11mm | NVIDIA H100 datasheet (814mm², 990 TFLOPS, 3.35TB/s); Micron HBM3E |
| Arithmetic intensity | GEMM ~300, decode ~2 FLOP/B (H100 ridge≈295) | NVIDIA Matrix-Multiplication Guide; Pope et al. 2022; Williams roofline |
| TCP/IP stack one-way latency | o≈25μs (of which ~18μs is the kernel stack) | Belay et al., IX, *OSDI* 2014; Guo et al., *SIGCOMM* 2016 |
| RDMA/IB latency | o≈1.5μs, end-to-end 2–3μs (NIC <0.6μs + switching ~0.1μs/hop) | ConnectX-6/7 datasheet; eRPC *NSDI* 2019; pcie-bench *SIGCOMM* 2018 |
| UB-class latency/bandwidth | ~150ns per hop; cross-machine <1μs; 392GB/s one-way/NPU | UB-Mesh arXiv:2503.20377; CloudMatrix384 arXiv:2506.12708 |
| AllReduce cost model | T = 2(n−1)(o+α) + 2V(n−1)/(nB) | Thakur et al., *IJHPCA* 2005; Patarasuk & Yuan 2009 |
| DP gradient traffic | ≈2×parameter bytes/iteration | ZeRO, *SC* 2020 |
| Large-scale training comm fraction | 20–55% (vs. this model's baseline 45–67%@TCP) | MegaScale *NSDI* 2024; Domino 2024; Llama3 405B (MFU 38–43%) |
| Data-movement energy corroboration | DRAM access ≈700× an FP32 add; 62.7% of system energy in data movement | Horowitz *ISSCC* 2014; Boroumand *ASPLOS* 2018 — supports the paper's "80% of energy in data movement" |
| Hybrid-bonding interface thermal resistance | 1.2 K·mm²/W (μbump is 4.2) | Oprins et al. (imec), *ASME JEP* 139(1), 2017 measured |
| BEOL metal-stack thermal resistance | 2.0 K·mm²/W (0.5–5.5 with via density) | Colgan et al. (IBM), *SEMI-THERM* 2013 measured |
| Thinned-silicon conduction | 50μm / 147 W·m⁻¹K⁻¹ ≈ 0.34 K·mm²/W | standard value; thin-film correction only needed <10μm (Stanford 2021) |
| 3D-stacking product-level thermal cost | AMD X3D: Tj,max −5°C, frequency −200~400MHz (−4~8%) | AMD product specs / TechInsights teardown — used for model cross-validation |

**The only parameter calibrated to the paper**: the 2-layer folding area overhead of 23% (matching density 155→238) and the layout utilization of 68% (stated explicitly in the paper). Therefore **density is a calibrated, not a predicted, item** and is flagged separately in the results tables.

---

## 4. Layer-by-Layer Simulation Results

### 4.1 Layer 1 — Geometric scaling benefits flatten (figure `fig1_device_scaling.png`) ✅ supports P1

- Intrinsic gate delay improves to 0.40× from 28nm→3nm, but far below the 0.34× implied by the long-channel square law—velocity saturation compresses the benefit from quadratic to linear;
- Adding a fixed-span (50μm) intermediate wire, **stage delay barely improves from 28nm→3nm (0.86→1.10, actually rising past 5nm)**: the copper size effect drives wire resistance from 7.8 kΩ/mm to 250 kΩ/mm, and optimal-repeater delay from 84 to 302 ps/mm;
- The interconnect share of stage delay goes 22% → 72%, consistent with the paper's statement that "local interconnect parasitic R and C overtake the intrinsic transit time several-fold."

**Conclusion**: the model independently reproduces the phenomenon that "transistors keep getting faster, but system τ stops getting faster"—which is precisely the motivation for τ scaling.

### 4.2 Layer 2 — LogicFolding (figures `fig2_fold_criterion.png`, `fig3_fold_gains.png`) ✅ supports P2

Fixed 7nm node, 10⁷-gate processing core, 1.5μm hybrid-bonding pitch:

| Metric | Model (2-layer fold) | Paper measurement (Kirin 2026) | Note |
|------|---------------|---------------------|------|
| Average wire-length reduction | **−24.9%** | −30% | theoretical ceiling 1−1/√2=29.3%, model takes layout efficiency 0.85 |
| Clock-skew reduction | **−24.9%** | −25% | model output (clock-tree wire length contracts proportionally), not an input |
| Critical-path frequency gain | **+12.3%** | +13% | 252ps → 225ps |
| Transistor density | 239 MTr/mm² | 238 | ⚠️ area overhead is calibrated, so this item is not an independent prediction |
| 4-layer fold (forward-looking) | wire length −42.5%, frequency +24.8%, density 378 | paper roadmap 400+ by 2031 | model supports roadmap attainability |

Folding-criterion sweep (fig 2): the crossover of τ_Benefit and τ_Penalty appears at **pitch ≈ 3.1μm (gear ratio ≈ 4.3)**, sensitivity range 2.4–4.4μm (gear 3.3–6.2). The paper's engineering conclusion "gear ratio should be below 3, the lower the better" falls on the safe side of this model—the model independently confirms that **the criterion exists, the direction agrees, and Kirin's 1.5μm choice has about a 2× margin**.

### 4.3 Layer 3 — N²-vs-N fan-out dilemma (figure `fig4_fanout_dilemma.png`) ✅ supports P3

Anchored to H100-class compute/bandwidth density:

- Achievable compute for a memory-bound workload (decode, ~2 FLOP/B): 2.5D grows along **slope 1**, 3D Folding along **slope 2**—the divergence of the two lines on the log-log plot is the topological deficit itself;
- Ridge arithmetic intensity (the FLOP/B needed to stay compute-bound): 2.5D rises linearly with edge length, and **past N≈55mm (roughly the equivalent edge length of 2 reticles) even GEMM (~300 FLOP/B) becomes memory-bound**; 3D Folding's ridge stays constant at ~40 FLOP/B, independent of scale;
- This explains the paper's judgment: "the stagnation of 2.5D scaling has nothing to do with how aggressive the underlying logic node is—no transistor-level improvement can close the topological deficit."

### 4.4 Layer 4 — Cluster communication τ (figure `fig5_cluster_scaling.png`) ✅ supports P4 (by regime)

The α-β collective-communication model + SimPy discrete-event simulation (with link contention and 5% jitter) cross-validate:

- **Large-message regime (training-gradient AllReduce, 200GB/iteration)**: scaling efficiency is set by bandwidth, not latency. At 16384 GPUs, TCP-class 7%, RDMA/IB 17%, UB+Hi-ONE (bandwidth flattened to 392GB/s) 26%. **The 500× α advantage is only partly cashed in here**—isolating UB's low latency alone (same 400G physical link, only swapping the protocol stack) barely changes training iteration time;
- **Small-message regime (MoE inference all-to-all, KB-scale messages)**: protocol-stack α fully dominates. On the same 400G physical link, per-step time for 128-GPU expert parallelism: TCP-class ~400ms, RDMA ~24ms, UB protocol ~2.6ms—**swapping the protocol stack brings a 9× (vs RDMA) to 150× (vs TCP) improvement**, and the SimPy event-level simulation validation points agree with the analytical model (at large scale, DES is slightly above the analytical value, due to link queueing—a real effect the analytical model ignores);
- The paper attributes 500× to a "tens of μs → 100ns" comparison whose baseline is a TCP/IP-class stack; this model confirms that order of magnitude (25μs/0.15μs ≈ 170×, reaching the 500× order once per-message handshaking is counted).

**Conclusion**: P4 holds but needs to be made precise—**the value of low α is concentrated in the small-message/fine-grained-access regime (MoE routing, remote KV-cache reads, memory pooling, synchronization primitives), while the benefit for large-message collectives comes mainly from the bandwidth flattening of UB+Hi-ONE**. This agrees with the paper's own narrative (UB solves the protocol τ, Hi-ONE solves the bandwidth wall, the two work together), and with reports of all-to-all latency sensitivity in public practice such as DeepSeek-V3.

---

## 5. Cascade Experiments: Arguing the Methodological Meta-Proposition P5

System scenario: a 4096-GPU, 100B-parameter LLM training iteration. Baseline (traditional TCP-class stack) τ decomposition: communication 67%, compute 20%, memory 11%, other 2%—the communication fraction sits at the upper end of the 20–55% range reported by MegaScale/Domino (a TCP-class baseline is inherently worse than an IB cluster).

### Experiment A — Amdahl saturation (figure `fig6_amdahl_saturation.png`)

Compress any single layer's τ by 100× alone, and system speedup saturates at the reciprocal of that layer's fraction: optimizing communication only → ceiling 3.0×; compute only → ceiling 1.25×; memory only → ceiling 1.13×. **No single layer can sustain "α× per year" on its own**—this is the quantitative form of "a single-layer improvement only counts if it propagates to system τ."

### Experiment B — Decade trajectory (figure `fig7_decade_trajectories.png`)

| Strategy | System τ after a decade | Annualized α |
|------|-------------|--------|
| Push the device node only (+15% compute/year) | 0.86× | 1.02 |
| Swap the network fabric only (RDMA→UB, then nothing left to do) | 0.47× (stalls from year 4) | 1.08 |
| **Full-stack τ-first co-design** (device+folding+UB+Hi-ONE+3D Folding+yearly investment into the dominant layer) | **0.14×** | **1.22** |

Single-point strategies all saturate within 2–4 years; only investing each year's improvement into **that year's dominant τ layer** keeps α going for a decade. Note: this experiment fixes cluster size; the paper's AI-side α≈10/year also includes growth of the hardware-integration scale itself (>100×/decade), and the two multiplied together give the paper's accounting.

### Experiment C — Bottleneck migration (figure `fig8_bottleneck_migration.png`)

Introducing each layer's optimization in turn along the paper's technology roadmap, the dominant τ layer migrates as follows:

```
Stage 0 traditional stack    τ=7.37s  dominant: communication (67%)
Stage 1 +UB memory-semantic  τ=4.22s  dominant: communication (42%)   ← protocol τ dropped but the bandwidth wall remains
Stage 2 +Hi-ONE optical link τ=3.46s  dominant: compute               ← communication steps down, bottleneck migrates
Stage 3 +3D Folding          τ=2.98s  dominant: compute
Stage 4 +LogicFolding        τ=2.43s  dominant: communication         ← bottleneck migrates back, pointing to the next round of UB/optical investment
```

None of the steps in the 3.0× end-to-end improvement acts in isolation; each optimization pushes dominance onto another layer—**"the dominant τ layer is the next investment direction" emerges naturally in the model**, even reproducing the cyclic return of the bottleneck (after stage 4 it is communication's turn again, corresponding to the paper's UB2.0 / higher-bandwidth optical-interconnect roadmap).

### Experiment D — Accounting decomposition of α≈10/year (figure `fig10_alpha_decomposition.png`)

Fixing 4096 GPUs, phase-one Experiment B can only yield α≈1.22/year; the paper's AI-side α≈10/year is a different accounting. Experiment D uses weak scaling (fixed per-chip batch, cluster growing 1.58×/year, i.e. the paper's ">100×/decade") + model size growing with total compute under the Chinchilla accounting (parameters ∝ √compute), decomposing system capability into three hardware factors:

```
capability = N_chips (α_scale=1.58) × per_chip (α_chip=1.25) × scaling efficiency (α_eff)
```

| Strategy | α_eff | α_total | Decade capability |
|------|-------|---------|---------|
| legacy fabric fixed (RDMA/IB unchanged) | 0.84 (efficiency 0.47→0.08 collapses) | 1.67/year | 165× |
| τ-first: fabric evolves in lockstep with compute | **1.02 (efficiency maintained 0.47→0.55)** | **2.01/year** | **1064×** |

**Findings**: (1) under τ-first, 1064× over a decade, compatible with the paper's "100×/decade integration" order-of-magnitude narrative (capability = integration × per-chip × efficiency); (2) **honest conclusion: the product of the three hardware factors ≈2.0/year, plus precision/number-format evolution (FP16→FP8→FP4, ~1.3/year, outside the model) ≈2.6/year—the paper's α≈10/year cannot be explained by hardware factors alone, it also requires algorithm/software factors, and its accounting deserves a more precise definition**; (3) the true role of τ compression under this accounting is not to contribute a multiplier directly, but to **hold α_eff≈1—keeping the gains of scale from being eaten by communication**. When the fabric stops evolving, α_eff=0.84 means losing 16% of the scale gain each year, a cumulative 6.4× loss over a decade.

## 5.5 Thermal Constraints: Sustainability of Multi-Layer Folding (figure `fig9_thermal_constraint.png`)

The phase-one folding model had no heat removal; this section adds it (corresponding to the paper's open problem §6 "thermal budget"). A one-dimensional thermal-resistance network: thinned silicon 0.34 + hybrid-bonding interface 1.2 (imec measured) + BEOL 2.0 (IBM measured) K·mm²/W; a temperature-rise budget of 60K, with the 2D baseline calibrating the cooling solution to fully use the budget; power-frequency-voltage coupled via the α-power law, and folding's reduced wire capacitance (Layer 2 wire-length reduction × 45% interconnect power share) counted as an efficiency gain.

| Fold configuration × cooling | 2-layer sustainable frequency | 4-layer sustainable frequency |
|----------------|--------------|--------------|
| Logic+memory (Kirin form) · mobile passive | **0.98 (near-lossless)** | 0.91 |
| Logic+logic (full power) · mobile passive | 0.80 | 0.61 |
| Logic+logic · AI liquid cooling | 0.80 | 0.60 |
| Circuit limit (no thermal constraint, reference) | 1.12 | 1.25 |

**Findings**: (1) **the bulk of the thermal constraint is TDP (folding doubles per-area power density); the inter-layer thermal-resistance gradient is a secondary term**—only 7% of the budget in the baseline, and only 18% even with a pessimistic 10 K·mm²/W bonding thermal resistance; (2) the sustainable frequency of homogeneous "logic+logic" full-power folding is significantly reduced and must be paired with backside power delivery, low-temperature bonding, and cooling innovation—the phase-one 4-layer +24.8% projection should be revised to **burst/conditionally attainable**; (3) **heterogeneous "logic+memory" folding is nearly thermally lossless (0.98)** while retaining +12% burst frequency and efficiency gains—this explains why the paper's deployment paths (Kirin folding SRAM, 3D Folding folding memory/power/IO) are all heterogeneous folds. Product-level cross-validation: AMD 3D V-Cache (also a memory-logic stack) measured a 4-8% frequency drop and a 5°C Tj,max drop, of the same order as this model's heterogeneous fold at −2.3%.

---

## 6. Sensitivity Check (`python sensitivity.py`)

Applying ±50%-order perturbations to 17 sets of key parameters (Rent exponent, clock margin, routing coefficient, folding efficiency, bonding capacitance, logic depth, fabric parameters in the direction unfavorable to UB, bonding thermal resistance 1–10 K·mm²/W, interconnect power share, memory-layer power ratio, temperature-rise budget, etc.):

- The folding frequency gain stays positive: **+7.7% ~ +19.4%**;
- The criterion-reversal point always exists and is above Kirin's 1.5μm: **2.4 ~ 4.4μm**;
- The co-design strategy's annualized α is always higher than the best single-point strategy: **1.22 vs 1.08**;
- Heterogeneous-fold sustainable frequency stays ≥0.92 and is always better than homogeneous full-power folding; the inter-layer gradient is always a secondary term in the temperature-rise budget (≤18%);
- **Number of conclusion-direction reversals: 0/17**.

## 7. Conclusions

**Where the simulation supports the paper's core ideas**:

1. P1 holds: with independent-literature parameters one can reproduce "geometric scaling flattens, interconnect takes over the delay budget" (interconnect share 22%→72%);
2. P2 holds: the folding criterion τ_Benefit>τ_Penalty genuinely exists, the model independently computes wire length −25%, skew −25%, frequency +12.3%, matching Kirin measurements (−30%/−25%/+13%), and is robust to parameter perturbation; the gear-ratio constraint agrees in direction;
3. P3 holds and is a pure geometric fact: the N²/N divergence does not depend on any process assumption, and the upward shift of the 2.5D ridge means "stacking compute without stacking surface bandwidth" must hit a wall;
4. P4 holds but by regime: the system value of the 500× τ compression is concentrated in small-message/fine-grained access; large-message training relies more on bandwidth flattening (UB and Hi-ONE are both indispensable—which is itself an example of cross-layer co-design);
5. P5 (the methodological claim) emerges in all three cascade experiments: single-layer optimization saturates, co-design sustains α, and dominant-layer migration points the way. **The operational value of τ as a full-stack-shared metric is demonstrable in the model, not just rhetoric.**

**Limitations and caveats**:

- The density 155→238 item is calibrated via area overhead and is a consistency check, not an independent prediction;
- The thermal model is a one-dimensional thermal-resistance network without lateral heat spreading or hotspot superposition (imec simulations show the worst homogeneous partition can reach +44% temperature rise); the sustainable frequency of the homogeneous 4-layer case should be treated as a conservative lower bound and the circuit limit as an upper bound, with the real landing point depending on progress in backside power delivery and low-temperature bonding—but the "heterogeneous folding is nearly lossless" conclusion has AMD X3D product data as cross-corroboration;
- The cluster model ignores compute-communication overlap; modern frameworks can hide 30–60% of communication time, which would proportionally compress the absolute share of the communication component in Experiment C but would not change the migration order;
- The paper's α≈10/year (AI) cannot be explained by hardware factors alone (Experiment D: three hardware factors ≈2.0/year, plus precision evolution ≈2.6/year); it needs algorithm/software factors to make up the rest, and the paper's definition and accounting of α deserve a more precise delineation;
- The model's fabric parameters are taken from the UB-Mesh/CloudMatrix papers (Huawei self-reported data with no independent benchmark corroboration); if the actual UB latency is higher than claimed, the gap in fig 5(b) narrows proportionally, but the regime structure is unchanged.

**Overall assessment**: under independent parameter calibration, all five of the paper's core propositions are supported by the simulation; in particular the methodological proposition P5—that τ is a full-stack-shared optimization target and that bottleneck migration determines the investment direction—is not "assumed into" the model but emerges naturally from the cascade of the four physical/queueing layers, which is the strongest corroboration of τ scaling as an *operational methodology* (rather than a slogan).

---

## Appendix: File Manifest

| File | Content |
|------|------|
| `tau_sim/params.py` | All calibrated parameters and their sources |
| `tau_sim/layer1_device.py` | P1: α-power law + copper size effect |
| `tau_sim/layer2_circuit.py` | P2: Davis wire-length distribution + folding geometry + criterion |
| `tau_sim/layer3_chip.py` | P3: N²/N + roofline |
| `tau_sim/layer4_system.py` | P4: α-β collective communication + SimPy DES |
| `tau_sim/cascade.py` | P5: cascade experiments A/B/C/D |
| `tau_sim/thermal.py` | Thermal constraint: sustainable frequency of multi-layer folding |
| `run_all.py` | One-click generation of figures/fig1–fig10 |
| `sensitivity.py` | Sensitivity check (17 items, script-style) |
| `build_dashboard.py` + `dashboard_template.html` | Generates the self-contained static report page dashboard.html |
| `app.py` | Streamlit interactive GUI (6 tabs, reusing all models + SimPy DES + sensitivity tornado) |
| `tau_lab_model.js` + `tau_lab_template.html` + `build_tau_lab.py` | Generates the browser version `tau_lab.html` (zero-dependency single file: four-model interaction + sensitivity sweep, JS bit-for-bit matched against Python) |

> Note: the interactive GUIs (`tau_lab.html`, `app.py`) and the static report page only change the form of presentation;
> the models, parameters, and conclusions used are identical to this report and introduce no new scientific claims.
