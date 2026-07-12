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
  if (Object.keys(M._davisCache).length > 120) M._davisCache = {};
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

M.iterationTau = function (nGpus, fabName, kComp, kMem, kOther, kComm) {
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
    comm: tComm / (kComm || 1),
    other: tOther / (kOther || 1),
  };
};
M.totalTau = (nGpus, fab, kC, kM, kO, kCm) =>
  Object.values(M.iterationTau(nGpus, fab, kC, kM, kO, kCm)).reduce((a, b) => a + b, 0);

/* ---------------- Layer 1: 器件层节点扫描（对齐 layer1_device.py） ---------------- */

M.NODES = {
  '28nm': { lg: 30.0, vdd: 0.95, vth: 0.35, fo4: 15.0, w: 45 },
  '16nm': { lg: 26.0, vdd: 0.80, vth: 0.33, fo4: 11.0, w: 32 },
  '7nm':  { lg: 20.0, vdd: 0.75, vth: 0.30, fo4: 8.0,  w: 20 },
  '5nm':  { lg: 17.0, vdd: 0.72, vth: 0.28, fo4: 7.0,  w: 15 },
  '3nm':  { lg: 15.0, vdd: 0.70, vth: 0.26, fo4: 6.0,  w: 12 },
};
M.NODE_ORDER = ['28nm', '16nm', '7nm', '5nm', '3nm'];
M.MU_LONG_CHANNEL = 2.0;
M.WIRE_SPAN_UM = 50.0;

M.bufferedWireNode = function (node) {   // ps/μm，含铜尺寸效应
  const nd = M.NODES[node];
  const w = nd.w * 1e-9, h = w * M.WIRE_AR;
  const r = M.rhoCu(nd.w) / (w * h), c = M.WIRE_CAP_PER_M;
  const cg = 0.5e-15, rg = nd.fo4 * 1e-12 / (5 * cg);
  return 2 * Math.sqrt(0.38 * r * c * rg * cg) * 1e-6 * 1e12;
};

M.deviceScan = function () {
  const ref = M.NODES['28nm'];
  const sq = n => n.lg * n.lg * n.vdd / Math.pow(n.vdd - n.vth, M.MU_LONG_CHANNEL);
  return M.NODE_ORDER.map(name => {
    const nd = M.NODES[name];
    const tauInt = nd.fo4;
    const tauSq = ref.fo4 * sq(nd) / sq(ref);
    const tauWire = M.bufferedWireNode(name) * M.WIRE_SPAN_UM;
    const tauStage = tauInt + tauWire;
    return { node: name, tauInt, tauSq, tauWire, tauStage,
             wireFrac: tauWire / tauStage, wirePsPerMm: M.bufferedWireNode(name) * 1e3 };
  });
};

/* ---------------- 级联实验 B/D（对齐 cascade.py） ---------------- */

M.decadeTrajectories = function (nGpus, years) {
  nGpus = nGpus || 4096; years = years || 10;
  const t0 = M.totalTau(nGpus, 'legacy_tcp', 1, 1, 1, 1);
  const deviceOnly = [], fabricOnly = [], tauFirst = [];
  for (let y = 0; y <= years; y++) {
    deviceOnly.push(M.totalTau(nGpus, 'legacy_tcp', Math.pow(1.15, y), 1, 1, 1) / t0);
    const fab = y < 2 ? 'legacy_tcp' : (y < 4 ? 'legacy_rdma' : 'ub_hione');
    fabricOnly.push(M.totalTau(nGpus, fab, 1, 1, 1, 1) / t0);
  }
  // τ-first：逐年演进 + 投给主导层
  let kC = 1, kM = 1, kO = 1, kCm = 1, fab = 'legacy_tcp';
  tauFirst.push(1);
  for (let y = 1; y <= years; y++) {
    kC *= 1.15;
    if (y === 2) kC *= 1.25;
    if (y === 3) fab = 'ub_protocol';
    if (y === 4) fab = 'ub_hione';
    if (y === 5) kM *= 1.6;
    const parts = M.iterationTau(nGpus, fab, kC, kM, kO, kCm);
    const dom = Object.keys(parts).reduce((a, b) => parts[a] > parts[b] ? a : b);
    if (dom === 'compute') kC *= 1.2;
    else if (dom === 'memory') kM *= 1.2;
    else if (dom === 'comm') kCm *= 1.2;
    else kO *= 1.2;
    tauFirst.push(M.totalTau(nGpus, fab, kC, kM, kO, kCm) / t0);
  }
  const alpha = a => Math.pow(1 / a[a.length - 1], 1 / years);
  return {
    series: [
      { name: '只推器件节点', pts: deviceOnly, alpha: alpha(deviceOnly) },
      { name: '只换网络 fabric', pts: fabricOnly, alpha: alpha(fabricOnly) },
      { name: '全栈 τ-first 协同', pts: tauFirst, alpha: alpha(tauFirst) },
    ],
  };
};

M.ALPHA_SCALE = 1.58; M.ALPHA_CHIP = 1.25; M.ALPHA_PRECISION = 1.30;
M.N0_CHIPS = 512; M.TOKENS_PER_GPU = 1024;
M.MODEL_GROWTH = Math.sqrt(M.ALPHA_SCALE * M.ALPHA_CHIP);

M.weakScalingEff = function (nGpus, modelP, fab, kComm, perChip) {
  const tComp = 6 * modelP * M.TOKENS_PER_GPU / (perChip * M.PER_GPU_FLOPS);
  const vol = modelP * 2;
  const tComm = M.hierAllreduceT(Math.round(nGpus), vol, fab) / (kComm || 1);
  return tComp / (tComp + tComm);
};

M.alphaDecomp = function (years) {
  years = years || 10;
  const out = { years: [], legacy: null, tau_first: null };
  for (let y = 0; y <= years; y++) out.years.push(y);
  for (const strat of ['legacy', 'tau_first']) {
    const caps = [], effs = [];
    for (let y = 0; y <= years; y++) {
      const n = M.N0_CHIPS * Math.pow(M.ALPHA_SCALE, y);
      const perChip = Math.pow(M.ALPHA_CHIP, y);
      const modelP = M.MODEL_PARAMS * Math.pow(M.MODEL_GROWTH, y);
      let fab, kComm;
      if (strat === 'legacy') { fab = M.FABRICS.legacy_rdma; kComm = 1; }
      else if (y < 3) { fab = M.FABRICS.legacy_rdma; kComm = 1; }
      else if (y < 4) { fab = M.FABRICS.ub_protocol; kComm = 1; }
      else { fab = M.FABRICS.ub_hione; kComm = Math.pow(1.4, y - 4); }
      const eff = M.weakScalingEff(n, modelP, fab, kComm, perChip);
      effs.push(eff); caps.push(n * perChip * eff);
    }
    const cap0 = caps[0], eff0 = effs[0];
    out[strat] = {
      capability: caps.map(c => c / cap0),
      eff: effs,
      alphaTotal: Math.pow(caps[years] / cap0, 1 / years),
      alphaEff: Math.pow(effs[years] / eff0, 1 / years),
    };
  }
  return out;
};

/* ---------------- 敏感性扫描：参数注册表 + 指标 ---------------- */

M.RENT_P = 0.62;
M.FOLD_EFF = 0.85;

M.PARAMS = [
  { id: 'rent', label: 'Rent 指数 p', get: () => M.RENT_P, set: v => M.RENT_P = v },
  { id: 'eff', label: '折叠布局效率', get: () => M.FOLD_EFF, set: v => M.FOLD_EFF = v },
  { id: 'skew', label: '时钟裕量占比', get: () => M.SKEW_FRACTION, set: v => M.SKEW_FRACTION = v },
  { id: 'detour', label: '绕线系数', get: () => M.CROSS_DETOUR_COEF, set: v => M.CROSS_DETOUR_COEF = v },
  { id: 'hbcap', label: '键合电容/焊盘', get: () => M.HB_CAP_PER_PAD_2UM, set: v => M.HB_CAP_PER_PAD_2UM = v },
  { id: 'rtier', label: '层间热阻', get: () => M.R_TIER, set: v => M.R_TIER = v },
  { id: 'wpf', label: '互连功耗占比', get: () => M.WIRE_POWER_FRACTION, set: v => M.WIRE_POWER_FRACTION = v },
  { id: 'memq', label: '存储层功率比', get: () => M.MEM_TIER_Q_RATIO, set: v => M.MEM_TIER_Q_RATIO = v },
  { id: 'dtb', label: '温升预算', get: () => M.DT_BUDGET, set: v => M.DT_BUDGET = v },
  { id: 'ubo', label: 'UB 每消息开销', get: () => M.FABRICS.ub_protocol.o,
    set: v => { M.FABRICS.ub_protocol.o = v; M.FABRICS.ub_hione.o = v; } },
  { id: 'uba', label: 'UB 跨机延迟 α', get: () => M.FABRICS.ub_protocol.ae,
    set: v => { M.FABRICS.ub_protocol.ae = v; M.FABRICS.ub_hione.ae = v; } },
  { id: 'tcpo', label: 'TCP 栈开销', get: () => M.FABRICS.legacy_tcp.o,
    set: v => M.FABRICS.legacy_tcp.o = v },
];

M.crossoverPitch = function () {
  for (let p = 0.5; p <= 12.001; p += 0.1) {
    const r = M.fold(2, p, M.RENT_P, M.FOLD_EFF);
    if (r.penalty > r.benefit) return p;
  }
  return 12;
};

/* 指标: {label, unit, fn, flip(v)→bool 结论翻转, flipDesc} */
M.METRICS = {
  m1: { label: '2层折叠频率增益 @1.5μm', unit: '%',
        fn: () => M.fold(2, 1.5, M.RENT_P, M.FOLD_EFF).freqGain * 100,
        flip: v => v < 0, flipDesc: '增益转负 → 折叠不再划算' },
  m2: { label: '判据反转点 pitch', unit: 'μm',
        fn: () => M.crossoverPitch(),
        flip: v => v < 1.5, flipDesc: '反转点低于 Kirin 的 1.5μm 工作点' },
  m3: { label: '2层异构折叠可持续频率（移动）', unit: '×',
        fn: () => M.sustained(2, 'logic-on-memory', 'mobile',
                              M.fold(2, 1.5, M.RENT_P, M.FOLD_EFF)).fSustained,
        flip: v => v < 0.9, flipDesc: '低于 0.9 → 不再"近乎无损"' },
  m4: { label: 'MoE @128卡 UB 相对 RDMA 加速', unit: '×',
        fn: () => M.moeStep(128, M.FABRICS.legacy_rdma) /
                  M.moeStep(128, M.FABRICS.ub_protocol),
        flip: v => v < 1, flipDesc: 'UB 不再占优' },
  m5: { label: '级联全开相对基线加速 @4096卡', unit: '×',
        fn: () => {
          const s = o => Object.values(o).reduce((a, b) => a + b, 0);
          return s(M.iterationTau(4096, 'legacy_tcp', 1, 1, 1)) /
                 s(M.iterationTau(4096, 'ub_hione', 1.6, 2.5, 1));
        },
        flip: v => v < 1, flipDesc: '级联优化无净收益' },
};

/* 龙卷风数据: 每参数 ±s 扰动后的指标值（按摆幅降序） */
M.tornado = function (metricId, s) {
  const met = M.METRICS[metricId];
  const base = met.fn();
  const rows = M.PARAMS.map(p => {
    const b = p.get();
    p.set(b * (1 - s)); const lo = met.fn();
    p.set(b * (1 + s)); const hi = met.fn();
    p.set(b);
    return { label: p.label, lo, hi, span: Math.abs(hi - lo) };
  });
  rows.sort((a, b) => b.span - a.span);
  return { base, rows };
};

/* 1D 扫描: 参数在 0.5×~1.5× base 上扫 n 点 */
M.sweep1d = function (metricId, paramId, n) {
  const met = M.METRICS[metricId];
  const p = M.PARAMS.find(x => x.id === paramId);
  const b = p.get();
  const pts = [];
  for (let i = 0; i < (n || 31); i++) {
    const f = 0.5 + i / ((n || 31) - 1);
    p.set(b * f);
    const v = met.fn();
    pts.push([f, v, met.flip(v)]);
  }
  p.set(b);
  return { base: met.fn(), pts };
};

if (typeof module !== 'undefined') module.exports = M;
if (typeof window !== 'undefined') window.TauModel = M;
