/* τ Lab — tau_sim 核心模型的 JS 移植（与 tau_sim/*.py 保持一致）
 * 纯函数、无依赖；浏览器与 Node（对拍测试）均可运行。 */

const M = {};

/* ---------------- 参数（对应 tau_sim/params.py） ---------------- */
M.NODE = { lg: 20.0, vdd: 0.75, vth: 0.30, fo4: 8.0, w: 20 };   // 7nm
M.ALPHA_POWER = 1.25;
M.RHO_CU_BULK = 1.68e-8;
M.CU_MFP_NM = 40.0;
M.WIRE_AR = 2.0;
M.WIRE_CAP_PER_M = 0.20e-9;
M.N_GATES = 1e7;
M.LOGIC_DEPTH = 16;
M.TOP_METAL_PITCH_NM = 720;
M.HB_CAP_PER_PAD_2UM = 0.2e-15;
M.HB_RES_PER_PAD = 0.3;
M.FOLD_AREA_OVERHEAD_2T = 0.23;
M.AREA_UTILIZATION = 0.68;
M.DENSITY_2D = 155.0;
M.SKEW_FRACTION = 0.10;
M.DRIVER_UPSIZE = 8.0;
M.CROSS_DETOUR_COEF = 2.0;

M.COMPUTE_DENSITY = 1.2;        // TFLOPS/mm²
M.HBM_STACK_BW = 1.2;           // TB/s
M.HBM_STACK_EDGE = 11.0;        // mm
M.EDGE_SIDES = 2;
M.SURFACE_BW_DENSITY = 0.03;    // TB/s/mm²

M.FABRICS = {
  legacy_tcp:  { o: 25e-6, ai: 0.7e-6, ae: 1.0e-6, bi: 450e9, be: 12.5e9, hs: true },
  legacy_rdma: { o: 1.5e-6, ai: 0.7e-6, ae: 1.0e-6, bi: 450e9, be: 50e9,  hs: false },
  ub_protocol: { o: 0.05e-6, ai: 0.10e-6, ae: 0.30e-6, bi: 450e9, be: 50e9, hs: false },
  ub_hione:    { o: 0.05e-6, ai: 0.10e-6, ae: 0.30e-6, bi: 392e9, be: 392e9, hs: false },
};
M.GPUS_PER_NODE = 8;
M.MODEL_PARAMS = 100e9;
M.GLOBAL_BATCH_TOKENS = 4e6;
M.PER_GPU_FLOPS = 400e12;
M.MOE_LAYERS = 60;
M.MOE_HIDDEN = 8192;
M.MOE_TOKENS = 32;

/* 热参数（tau_sim/thermal.py） */
M.R_TIER = 0.34 + 1.2 + 2.0;
M.DT_BUDGET = 60.0;
M.Q0 = { mobile: 0.25, ai: 0.86 };
M.WIRE_POWER_FRACTION = 0.45;
M.MEM_TIER_Q_RATIO = 0.2;

/* ---------------- Layer 2: 线长与折叠 ---------------- */

M.rhoCu = (wNm) => M.RHO_CU_BULK * (1 + M.CU_MFP_NM / wNm);

M.wireRC = function () {
  const w = M.NODE.w * 1e-9, h = w * M.WIRE_AR;
  return { r: M.rhoCu(M.NODE.w) / (w * h), c: M.WIRE_CAP_PER_M };
};

/* Davis 分布 cdf（随 Rent p 变化，缓存） */
M._davisCache = {};
M.davisCdf = function (p) {
  const key = p.toFixed(3);
  if (M._davisCache[key]) return M._davisCache[key];
  const nSide = Math.sqrt(M.N_GATES);
  const lMax = Math.floor(2 * nSide) - 1;
  const cdf = new Float64Array(lMax);
  let sum = 0;
  for (let i = 0; i < lMax; i++) {
    const l = i + 1;
    let m = l <= nSide
      ? l * l * l / 3 - 2 * nSide * l * l + 2 * M.N_GATES * l
      : Math.pow(2 * nSide - l, 3) / 6;
    m = Math.max(m, 0) * Math.pow(l, 2 * p - 4);
    sum += m;
    cdf[i] = sum;
  }
  for (let i = 0; i < lMax; i++) cdf[i] /= sum;
  M._davisCache[key] = cdf;
  return cdf;
};

M.percentileWl = function (p, q) {
  const cdf = M.davisCdf(p);
  let lo = 0, hi = cdf.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (cdf[mid] < q) lo = mid + 1; else hi = mid; }
  return lo + 1;
};

M.gatePitchUm = function () {
  const gpm = M.DENSITY_2D * 1e6 / 4 * M.AREA_UTILIZATION;
  return 1e3 / Math.sqrt(gpm);
};

M.critWiresUm = function (rentP) {
  const gp = M.gatePitchUm();
  const out = [];
  for (let i = 0; i < M.LOGIC_DEPTH; i++) {
    const q = 0.95 + (0.9995 - 0.95) * i / (M.LOGIC_DEPTH - 1);
    out.push(M.percentileWl(rentP, q) * gp);
  }
  return out;
};

M.wireDelayPerUm = function () {  // ps/μm
  const { r, c } = M.wireRC();
  const cg = 0.5e-15, rg = M.NODE.fo4 * 1e-12 / (5 * cg);
  return 2 * Math.sqrt(0.38 * r * c * rg * cg) * 1e-6 * 1e12;
};

M.critPathTau = function (wiresUm, nCross, pitchUm, skewScale) {
  const cg = 0.5e-15, rg = M.NODE.fo4 * 1e-12 / (5 * cg);
  const tauGates = M.LOGIC_DEPTH * M.NODE.fo4;
  const tauWires = M.wireDelayPerUm() * wiresUm.reduce((a, b) => a + b, 0);
  const cHb = M.HB_CAP_PER_PAD_2UM * Math.pow(pitchUm / 2, 2);
  const tauCross = nCross * (M.HB_RES_PER_PAD + rg / M.DRIVER_UPSIZE) * cHb * 1e12;
  return (tauGates + tauWires + tauCross) * (1 + M.SKEW_FRACTION * skewScale);
};

M.fold = function (tiers, pitchUm, rentP, eff) {
  const wl2d = M.critWiresUm(rentP);
  const tau2d = M.critPathTau(wl2d, 0, 2.0, 1.0);
  const shrink = 1 - eff * (1 - 1 / Math.sqrt(tiers));
  const wl3d = wl2d.map(w => w * shrink);
  const nCross = Math.ceil(M.LOGIC_DEPTH / 2);
  const gear = pitchUm * 1e3 / M.TOP_METAL_PITCH_NM;
  const detour = M.CROSS_DETOUR_COEF * Math.max(gear - 1, 0) * pitchUm;
  const wl3dEff = wl3d.map((w, i) => i < nCross ? w + detour : w);
  const tau3d = M.critPathTau(wl3dEff, nCross, pitchUm, shrink);
  const tauIdeal = M.critPathTau(wl3d, 0, pitchUm, shrink);
  const overhead = M.FOLD_AREA_OVERHEAD_2T * (1 + 0.35 * (tiers - 2));
  return {
    tiers, pitchUm, gear,
    wlReduction: 1 - shrink,
    skewReduction: 1 - shrink,
    tau2d, tau3d,
    freqGain: tau2d / tau3d - 1,
    benefit: tau2d - tauIdeal,
    penalty: tau3d - tauIdeal,
    density: M.DENSITY_2D * tiers * (1 - overhead),
  };
};

/* ---------------- 热约束（tau_sim/thermal.py） ---------------- */

M.freqOfV = function (v) {
  const { vdd, vth } = M.NODE, a = M.ALPHA_POWER;
  return (Math.pow(v - vth, a) / v) / (Math.pow(vdd - vth, a) / vdd);
};

M.vOfFreq = function (x) {
  let lo = M.NODE.vth + 1e-3, hi = M.NODE.vdd * 1.3;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (M.freqOfV(mid) < x) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
};

M.sustained = function (tiers, style, cooling, foldRes) {
  const q0 = M.Q0[cooling];
  const rHs = M.DT_BUDGET / q0;
  const fBurst = tiers > 1 ? 1 + foldRes.freqGain : 1.0;
  const cDyn = 1 - M.WIRE_POWER_FRACTION * (tiers > 1 ? foldRes.wlReduction : 0);
  const weights = [];
  for (let i = 0; i < tiers; i++)
    weights.push(style === 'logic-on-memory' && i > 0 ? M.MEM_TIER_Q_RATIO : 1.0);

  const dtAt = (x) => {
    const v = M.vOfFreq(x);
    const pf = cDyn * Math.pow(v / M.NODE.vdd, 2) * x;
    const q = weights.map(w => q0 * w * pf);
    const total = q.reduce((a, b) => a + b, 0);
    let grad = 0;
    for (let i = 0; i < tiers - 1; i++)
      grad += M.R_TIER * q.slice(i + 1).reduce((a, b) => a + b, 0);
    return { dt: rHs * total + grad, grad };
  };

  if (tiers === 1) return { fSustained: 1.0, fBurst: 1.0, grad: 0 };
  if (dtAt(fBurst).dt <= M.DT_BUDGET)
    return { fSustained: fBurst, fBurst, grad: dtAt(fBurst).grad };
  let lo = 0.05, hi = fBurst;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (dtAt(mid).dt > M.DT_BUDGET) hi = mid; else lo = mid;
  }
  const x = (lo + hi) / 2;
  return { fSustained: x, fBurst, grad: dtAt(x).grad };
};

/* ---------------- Layer 3: N²-vs-N ---------------- */

M.pkg = function (sideMm, surfDensity, hbmBw) {
  const peak = M.COMPUTE_DENSITY * sideMm * sideMm;
  const bwEdge = (M.EDGE_SIDES * sideMm / M.HBM_STACK_EDGE) * hbmBw;
  const bwSurf = surfDensity * sideMm * sideMm;
  return { peak, bwEdge, bwSurf };
};

/* ---------------- Layer 4: 集合通信 ---------------- */

M.ringAllreduceT = function (n, vol, f) {
  if (n <= 1) return 0;
  const perStep = f.hs ? f.o + f.a : Math.max(f.o, f.a);
  return 2 * (n - 1) * perStep + 2 * vol * (n - 1) / (n * f.b);
};

M.hierAllreduceT = function (nGpus, vol, fab) {
  const g = M.GPUS_PER_NODE;
  const nNodes = Math.max(1, Math.floor(nGpus / g));
  let t = 0;
  if (g > 1)
    t += M.ringAllreduceT(g, vol, { o: fab.o, a: fab.ai, b: fab.bi, hs: fab.hs });
  if (nNodes > 1)
    t += M.ringAllreduceT(nNodes, vol / g, { o: fab.o, a: fab.ae, b: fab.be, hs: fab.hs });
  return t;
};

M.alltoallT = function (n, msg, fab) {
  if (n <= 1) return 0;
  const wire = (n - 1) * msg / fab.be;
  if (fab.hs) return (n - 1) * (fab.o + fab.ae + msg / fab.be);
  return (n - 1) * fab.o + fab.ae + wire;
};

M.trainEff = function (nGpus, fab) {
  const totalFlops = 6 * M.MODEL_PARAMS * M.GLOBAL_BATCH_TOKENS;
  const tComp = totalFlops / (nGpus * M.PER_GPU_FLOPS);
  const vol = M.MODEL_PARAMS * 2;
  const tComm = M.hierAllreduceT(nGpus, vol, fab);
  return tComp / (tComp + tComm);
};

M.moeStep = function (ep, fab) {
  const msg = M.MOE_TOKENS * M.MOE_HIDDEN * 2 / ep;
  const tComm = M.MOE_LAYERS * 2 * M.alltoallT(ep, msg, fab);
  return tComm + M.MOE_LAYERS * 8e-6;
};

/* ---------------- 级联（tau_sim/cascade.py） ---------------- */

M.SMALL_MSGS = 5000;

M.iterationTau = function (nGpus, fabName, kComp, kMem, kOther) {
  const fab = M.FABRICS[fabName];
  const totalFlops = 6 * M.MODEL_PARAMS * M.GLOBAL_BATCH_TOKENS;
  const tCompute = totalFlops / (nGpus * M.PER_GPU_FLOPS);
  const tMemory = tCompute * 0.25 / 0.45;
  const tOther = tCompute * 0.05 / 0.45;
  const vol = M.MODEL_PARAMS * 2;
  const tComm = M.hierAllreduceT(nGpus, vol, fab)
    + M.SMALL_MSGS * (fab.o + fab.ae);
  return {
    compute: tCompute / kComp,
    memory: tMemory / kMem,
    comm: tComm,
    other: tOther / (kOther || 1),
  };
};

if (typeof module !== 'undefined') module.exports = M;
if (typeof window !== 'undefined') window.TauModel = M;
