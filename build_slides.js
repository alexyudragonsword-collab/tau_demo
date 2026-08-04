const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";           // 13.3 x 7.5
const W = 13.333, H = 7.5;

// ---- 调色板（科技蓝，与项目图表一致）----
const NAVY = "0F1B2D", NAVY2 = "18314F", INK = "14181C", INK2 = "51606E",
      MUTED = "8A97A3", LINE = "DDE3E9", WHITE = "FFFFFF", CARD = "F5F8FB",
      BLUE = "2A78D6", AQUA = "1BAF7A", AMBER = "D98A00", RED = "D64545",
      ICE = "CADCFC";
const HFONT = "Microsoft YaHei", BFONT = "Microsoft YaHei";
const FIGZH = "/home/user/tau_demo/figures/";

function bg(s, c){ s.background = { color: c }; }
function shadow(){ return { type:"outer", color:"9AA7B4", opacity:0.35, blur:8, offset:2, angle:90 }; }

// τ watermark on dark slides
function tau(s, x, y, sz, col, tr){
  s.addText("τ", { x, y, w:sz, h:sz, fontFace:"Cambria", fontSize:sz*46,
    color:col, align:"center", valign:"middle", bold:true, transparency:tr, margin:0 });
}
function badge(s, x, y, d, fill, txt, tcol, fs){
  s.addShape(p.ShapeType.ellipse, { x, y, w:d, h:d, fill:{color:fill} });
  s.addText(txt, { x, y, w:d, h:d, align:"center", valign:"middle", bold:true,
    color:tcol||WHITE, fontFace:HFONT, fontSize:fs||14, margin:0 });
}

// ===================================================================
// Slide 1 — 封面
// ===================================================================
let s = p.addSlide(); bg(s, NAVY);
s.addShape(p.ShapeType.rect, { x:0, y:0, w:W, h:H, fill:{color:NAVY} });
tau(s, 9.2, 1.2, 5.2, "20406B", 0);   // 大 τ 水印
s.addText("SIMULATION-BASED PAPER REVIEW", { x:0.9, y:1.15, w:9, h:0.4,
  color:"7FA8DB", fontFace:HFONT, fontSize:13, charSpacing:3, bold:true });
s.addText("用全栈 τ 级联仿真\n验证华为「时间缩放理论」", { x:0.85, y:1.7, w:9.6, h:2.2,
  color:WHITE, fontFace:HFONT, fontSize:40, bold:true, lineSpacing:48 });
s.addText([
  { text:"A Time Scaling Theory for Multi-Layer Electronic Systems", options:{ italic:true, color:ICE, fontSize:15, breakLine:true } },
  { text:"何庭波 · Huawei · ChinaXiv:202605.00224", options:{ color:"9FB6D6", fontSize:13 } },
], { x:0.9, y:3.95, w:10.5, h:0.9, fontFace:HFONT, lineSpacing:22 });

const pills = ["论文分析","独立建模仿真","对抗性审阅","中英双语交互交付"];
let px = 0.9;
pills.forEach(t => {
  const w = 0.42 + t.length*0.24;
  s.addShape(p.ShapeType.roundRect, { x:px, y:5.35, w, h:0.5, rectRadius:0.25,
    fill:{color:NAVY2}, line:{color:"335A82", width:1} });
  s.addText(t, { x:px, y:5.35, w, h:0.5, align:"center", valign:"middle",
    color:ICE, fontFace:HFONT, fontSize:13, margin:0 });
  px += w + 0.25;
});
s.addText("面向管理层的项目汇报　·　2026", { x:0.9, y:6.5, w:8, h:0.4,
  color:MUTED, fontFace:HFONT, fontSize:12 });
s.addNotes("项目一句话定位：把华为 τ scaling 论文的核心主张，用独立文献校准的四层仿真模型逐条检验，并交付可交互、可复现、中英双语的完整成果。");

// ===================================================================
// Slide 2 — 背景与任务
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("背景与任务", { x:0.7, y:0.5, w:8, h:0.7, color:INK, fontFace:HFONT, fontSize:32, bold:true });
s.addText("华为提出以时间常数 τ 取代几何缩放作为半导体演进的新标尺。任务：读懂其核心思想，独立建模仿真加以检验。",
  { x:0.7, y:1.25, w:11.9, h:0.7, color:INK2, fontFace:HFONT, fontSize:15, lineSpacing:22 });

const steps = [
  ["1","分析核心思想","提炼论文 5 个可检验命题（器件→系统全栈）"],
  ["2","独立建模","四层级联仿真，参数全部取自公开文献"],
  ["3","仿真论证","复现论文数字，并做对抗性审阅与敏感性检验"],
  ["4","交付","报告 + 交互实验台 + 中英双语，全部可复现"],
];
let sx = 0.7, sw = 2.9, gap = 0.33;
steps.forEach((st, i) => {
  const x = sx + i*(sw+gap);
  s.addShape(p.ShapeType.roundRect, { x, y:2.3, w:sw, h:3.5, rectRadius:0.1,
    fill:{color:CARD}, line:{color:LINE, width:1}, shadow:shadow() });
  badge(s, x+0.35, y0=2.65, 0.7, BLUE, st[0], WHITE, 24);
  s.addText(st[1], { x:x+0.3, y:3.55, w:sw-0.6, h:0.5, color:INK, fontFace:HFONT, fontSize:18, bold:true });
  s.addText(st[2], { x:x+0.3, y:4.1, w:sw-0.55, h:1.5, color:INK2, fontFace:HFONT, fontSize:13.5, lineSpacing:20, valign:"top" });
  if(i<3) s.addText("→", { x:x+sw-0.02, y:3.7, w:gap+0.04, h:0.6, align:"center", valign:"middle", color:MUTED, fontSize:22, bold:true, margin:0 });
});
s.addText("成果已提交至内部仓库（分支 claude/paper-analysis-model-scenario）并作为 Artifact 发布。",
  { x:0.7, y:6.15, w:11.9, h:0.5, color:MUTED, fontFace:HFONT, fontSize:12.5, italic:true });
s.addNotes("这是一次把外部论文当作待检验假设、用可复现仿真独立评估的方法演练。");

// ===================================================================
// Slide 3 — 论文核心思想
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("论文核心思想：从几何缩放到时间缩放", { x:0.7, y:0.5, w:12, h:0.7, color:INK, fontFace:HFONT, fontSize:30, bold:true });
s.addText([
  { text:"摩尔定律的本质从来不是「更小」，而是「更快」。", options:{ bold:true, color:INK, breakLine:true, fontSize:16 } },
  { text:"7nm 以下几何缩放失效后，应直接以特征时间常数 τ 为全栈统一优化目标。", options:{ color:INK2, fontSize:14 } },
], { x:0.7, y:1.25, w:8.0, h:1.0, fontFace:HFONT, lineSpacing:22, valign:"top" });
// τ formula card
s.addShape(p.ShapeType.roundRect, { x:8.9, y:1.2, w:3.7, h:1.15, rectRadius:0.1, fill:{color:NAVY} });
s.addText("τ = f(τ_transistor, τ_circuit,\nτ_chip, τ_system)", { x:8.9, y:1.2, w:3.7, h:1.15,
  align:"center", valign:"middle", color:ICE, fontFace:"Cambria", fontSize:15, bold:true, margin:0, lineSpacing:22 });

const props = [
  ["P1","几何缩放趋平","速度饱和 + 互连寄生反超本征延迟", AQUA],
  ["P2","LogicFolding","垂直折叠：判据 τ收益 > τ代价", AQUA],
  ["P3","N²-vs-N 扇出困境","算力∝N² 而边缘带宽∝N 的拓扑赤字", AQUA],
  ["P4","UB 通信 τ 压缩","内存语义总线 ~100ns，≈500×", AMBER],
  ["P5","τ 全栈共享目标","主导 τ 层就是下一个投资方向", BLUE],
];
let cy = 2.7, cw = 5.75, ch = 1.28, cgap = 0.28;
props.forEach((pr, i) => {
  const col = i % 2, row = (i - col) / 2;
  const x = 0.7 + col*(cw+0.35), y = cy + row*(ch+cgap);
  s.addShape(p.ShapeType.roundRect, { x, y, w:cw, h:ch, rectRadius:0.09, fill:{color:CARD}, line:{color:LINE, width:1} });
  badge(s, x+0.28, y+0.3, 0.68, pr[3], pr[0], WHITE, 18);
  s.addText(pr[1], { x:x+1.15, y:y+0.2, w:cw-1.3, h:0.5, color:INK, fontFace:HFONT, fontSize:16.5, bold:true, valign:"middle", margin:0 });
  s.addText(pr[2], { x:x+1.15, y:y+0.68, w:cw-1.35, h:0.5, color:INK2, fontFace:HFONT, fontSize:12.5, valign:"top", margin:0 });
});
// 5th card spans note
s.addText("τ_{n+1} = τ_n / α　（α 因应用而异：移动 ~1.3，AI 号称至 10 /年）",
  { x:6.8, y:5.55, w:5.75, h:1.0, color:INK2, fontFace:HFONT, fontSize:13, valign:"middle", lineSpacing:20 });
s.addNotes("五个命题贯穿器件到系统。P4 标黄、P5 标蓝——后面会说明它们最值得推敲。");

// ===================================================================
// Slide 4 — 方法：四层级联仿真
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("方法：四层级联仿真模型", { x:0.7, y:0.5, w:9, h:0.7, color:INK, fontFace:HFONT, fontSize:30, bold:true });
s.addText("把 τ 分解到四层逐层建模，再级联成系统 τ。关键：参数全部取自独立公开文献，论文自身数据只作对照目标——避免循环论证。",
  { x:0.7, y:1.22, w:11.9, h:0.7, color:INK2, fontFace:HFONT, fontSize:14.5, lineSpacing:21 });

const layers = [
  ["器件层","α-power law + 铜互连尺寸效应","IRDS · Sakurai · Steinhögl"],
  ["电路层","Davis 线长分布 + LogicFolding 折叠","Davis · Rahman&Reif · imec"],
  ["封装层","N²-vs-N + Roofline","NVIDIA · Micron HBM"],
  ["系统层","α-β 集合通信 + SimPy 离散事件","Thakur · ZeRO · UB-Mesh"],
];
let ly = 2.25, lh = 0.82, lgap = 0.16;
layers.forEach((l, i) => {
  const y = ly + i*(lh+lgap);
  s.addShape(p.ShapeType.roundRect, { x:0.7, y, w:7.6, h:lh, rectRadius:0.08,
    fill:{color: i%2?CARD:"ECF2F8"}, line:{color:LINE, width:1} });
  s.addText(`Layer ${i+1}`, { x:0.85, y, w:1.1, h:lh, color:BLUE, fontFace:HFONT, fontSize:12, bold:true, valign:"middle", align:"center", margin:0 });
  s.addText(l[0], { x:1.95, y, w:1.5, h:lh, color:INK, fontFace:HFONT, fontSize:16, bold:true, valign:"middle", margin:0 });
  s.addText(l[1], { x:3.4, y, w:3.3, h:lh, color:INK2, fontFace:HFONT, fontSize:12.5, valign:"middle", margin:0 });
  s.addText(l[2], { x:6.7, y, w:1.5, h:lh, color:MUTED, fontFace:HFONT, fontSize:10, valign:"middle", align:"right", margin:0, italic:true });
});
s.addText("↓  级联  →  系统 τ", { x:0.7, y:5.95, w:7.6, h:0.4, align:"center", color:BLUE, fontFace:HFONT, fontSize:13, bold:true });

// right: calibration stats
const kpis = [["30+","校准参数（逐项注明文献出处）"],["10","仿真图表（中/英双套）"],["17","敏感性扰动 · 0 结论翻转"]];
let ky = 2.25;
kpis.forEach(k => {
  s.addShape(p.ShapeType.roundRect, { x:8.6, y:ky, w:4.0, h:1.12, rectRadius:0.1, fill:{color:NAVY} });
  s.addText(k[0], { x:8.75, y:ky+0.06, w:1.5, h:1.0, color:AQUA, fontFace:HFONT, fontSize:38, bold:true, valign:"middle", align:"center", margin:0 });
  s.addText(k[1], { x:10.2, y:ky, w:2.3, h:1.12, color:ICE, fontFace:HFONT, fontSize:12.5, valign:"middle", lineSpacing:17, margin:0 });
  ky += 1.28;
});
s.addNotes("四层模型 + 级联；30+ 参数全部独立文献校准；这是让仿真结果具备论证力的关键设计。");

// ===================================================================
// Slide 5 — 关键结果
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("关键结果：仿真独立复现论文数字", { x:0.7, y:0.5, w:11, h:0.7, color:INK, fontFace:HFONT, fontSize:30, bold:true });

const stats = [
  ["−24.9%","折叠线长降幅","论文 −30%", AQUA],
  ["+12.3%","关键路径频率增益","论文 +13%", AQUA],
  ["9–159×","MoE 小消息 UB 加速","vs RDMA / TCP", BLUE],
  ["1.22","协同年化 α","vs 单点 1.02–1.08", BLUE],
];
let stx = 0.7, stw = 2.9, stg = 0.33;
stats.forEach((st, i) => {
  const x = stx + i*(stw+stg);
  s.addShape(p.ShapeType.roundRect, { x, y:1.5, w:stw, h:1.75, rectRadius:0.1, fill:{color:CARD}, line:{color:LINE, width:1}, shadow:shadow() });
  s.addText(st[0], { x:x+0.15, y:1.62, w:stw-0.3, h:0.85, color:st[3], fontFace:HFONT, fontSize:34, bold:true, align:"center", valign:"middle", margin:0 });
  s.addText(st[1], { x:x+0.15, y:2.45, w:stw-0.3, h:0.4, color:INK, fontFace:HFONT, fontSize:13.5, bold:true, align:"center", margin:0 });
  s.addText(st[2], { x:x+0.15, y:2.82, w:stw-0.3, h:0.35, color:MUTED, fontFace:HFONT, fontSize:11, align:"center", margin:0 });
});
// embed fig3
s.addImage({ path: FIGZH+"fig3_fold_gains.png", x:0.7, y:3.55, w:5.3, h:3.11 });
s.addText("LogicFolding 收益：模型（独立文献参数） vs Kirin 实测", { x:0.7, y:6.62, w:5.3, h:0.35, color:MUTED, fontFace:HFONT, fontSize:10.5, align:"center", italic:true });

// right findings
const finds = [
  ["N²-vs-N 是纯几何事实","2.5D 利用率随规模坍塌，3D 恢复 N² 对齐；无需任何校准。"],
  ["瓶颈按层迁移","优化通信→计算→再回通信，「主导 τ 层就是下一个投资方向」自然涌现。"],
  ["结论稳健","17 项参数 ±50% 扰动，结论方向 0 次翻转。"],
];
let fy = 3.7;
finds.forEach(f => {
  badge(s, 6.5, fy, 0.34, AQUA, "✓", WHITE, 14);
  s.addText(f[0], { x:6.98, y:fy-0.05, w:5.6, h:0.4, color:INK, fontFace:HFONT, fontSize:15, bold:true, margin:0 });
  s.addText(f[1], { x:6.98, y:fy+0.36, w:5.6, h:0.7, color:INK2, fontFace:HFONT, fontSize:12.5, lineSpacing:18, margin:0, valign:"top" });
  fy += 1.05;
});
s.addNotes("模型用独立参数就复现了论文的折叠数字；N²-vs-N、瓶颈迁移、稳健性是最扎实的结果。");

// ===================================================================
// Slide 6 — 对抗性审阅
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("深度发现：对抗性审阅", { x:0.7, y:0.5, w:9, h:0.7, color:INK, fontFace:HFONT, fontSize:30, bold:true });
s.addText("方向判断无懈可击；但几个最醒目的量化头条依赖最有利的基线与未公开的内部数据。",
  { x:0.7, y:1.22, w:11.9, h:0.5, color:INK2, fontFace:HFONT, fontSize:14.5 });

// left: challenges
s.addText("最易质疑", { x:0.7, y:1.95, w:5.6, h:0.45, color:RED, fontFace:HFONT, fontSize:17, bold:true });
const chal = [
  ["α ≈ 10/年","硬件三因子仅 ≈2.0/年（含精度 ≈2.6），10× 需算法/软件因子"],
  ["UB「500×」","对最差 TCP 基线；对 RDMA 仅 ~10–30×，且只在小消息兑现"],
  ["能量账被回避","论文自认「τ 非焦耳律」；CloudMatrix 约 4× 功耗换 ~2× 算力"],
];
let chy = 2.5;
chal.forEach(c => {
  s.addShape(p.ShapeType.roundRect, { x:0.7, y:chy, w:5.65, h:1.15, rectRadius:0.08, fill:{color:"FBF0F0"}, line:{color:"F0D2D2", width:1} });
  s.addText(c[0], { x:0.95, y:chy+0.12, w:5.2, h:0.42, color:"B03030", fontFace:HFONT, fontSize:15, bold:true, margin:0 });
  s.addText(c[1], { x:0.95, y:chy+0.55, w:5.25, h:0.55, color:INK2, fontFace:HFONT, fontSize:12, lineSpacing:16, margin:0, valign:"top" });
  chy += 1.28;
});

// right: solid + fig10
s.addText("最经得起推敲", { x:6.65, y:1.95, w:6, h:0.45, color:AQUA, fontFace:HFONT, fontSize:17, bold:true });
const solid = ["N²-vs-N 拓扑赤字（纯几何、与工艺无关）","互连占级延迟 22%→72%（独立文献一致）",">80% 能耗在数据搬运（Horowitz/Boroumand）"];
let soy = 2.5;
solid.forEach(t => {
  badge(s, 6.65, soy, 0.3, AQUA, "✓", WHITE, 12);
  s.addText(t, { x:7.08, y:soy-0.05, w:5.5, h:0.5, color:INK, fontFace:HFONT, fontSize:12.8, valign:"middle", margin:0, lineSpacing:16 });
  soy += 0.62;
});
s.addImage({ path: FIGZH+"fig10_alpha_decomposition.png", x:6.65, y:4.5, w:5.95, h:2.11 });
s.addText("实验 D：α≈10/年 的口径分解——硬件仅解释到 ~2×/年", { x:6.65, y:6.6, w:5.95, h:0.35, color:MUTED, fontFace:HFONT, fontSize:10.5, align:"center", italic:true });
s.addNotes("一句话审稿意见：卓越的工程报告与正确的范式呼吁，但把工程增益包装成了缩放定律。");

// ===================================================================
// Slide 7 — 交付物
// ===================================================================
s = p.addSlide(); bg(s, WHITE);
s.addText("交付物：可复现 · 可交互 · 中英双语", { x:0.7, y:0.5, w:12, h:0.7, color:INK, fontFace:HFONT, fontSize:30, bold:true });

const del = [
  ["仿真代码包","tau_sim 四层模型 + 热约束 + 级联；run_all 一键出图；敏感性脚本", BLUE],
  ["分析报告","REPORT（正面论证）+ CRITIQUE（对抗性附录），图文并茂 PDF/HTML", BLUE],
  ["交互实验台","τ Lab（6 面板拖参实时重算）+ Streamlit 版（含 SimPy 验证）", AQUA],
  ["中英双语","4 个页面右上角 中/EN 切换；中/英两套标签图；JS 与 Python 逐位对拍", AMBER],
];
let dx = 0.7, dw = 5.85, dh = 1.6, dgx = 0.35, dgy = 0.32;
del.forEach((d, i) => {
  const col = i%2, row=(i-col)/2;
  const x = dx + col*(dw+dgx), y = 1.6 + row*(dh+dgy);
  s.addShape(p.ShapeType.roundRect, { x, y, w:dw, h:dh, rectRadius:0.1, fill:{color:CARD}, line:{color:LINE, width:1}, shadow:shadow() });
  badge(s, x+0.3, y+0.35, 0.5, d[2], "●", WHITE, 12);
  s.addText(d[0], { x:x+1.0, y:y+0.28, w:dw-1.2, h:0.5, color:INK, fontFace:HFONT, fontSize:17, bold:true, margin:0, valign:"middle" });
  s.addText(d[1], { x:x+1.0, y:y+0.78, w:dw-1.25, h:0.7, color:INK2, fontFace:HFONT, fontSize:12.8, lineSpacing:18, margin:0, valign:"top" });
});
// bottom stat strip
s.addShape(p.ShapeType.roundRect, { x:0.7, y:5.5, w:11.95, h:1.15, rectRadius:0.1, fill:{color:NAVY} });
const bs = [["8","次提交，全部推送"],["4","双语页面"],["2","交互工具（Artifact）"],["100%","可复现"]];
bs.forEach((b, i) => {
  const x = 0.9 + i*2.98;
  s.addText(b[0], { x, y:5.62, w:1.3, h:0.9, color:AQUA, fontFace:HFONT, fontSize:34, bold:true, valign:"middle", align:"center", margin:0 });
  s.addText(b[1], { x:x+1.25, y:5.5, w:1.65, h:1.15, color:ICE, fontFace:HFONT, fontSize:12, valign:"middle", lineSpacing:16, margin:0 });
});
s.addNotes("成果不是一份静态报告，而是一套可复现、可交互、双语的评估资产。");

// ===================================================================
// Slide 8 — 结论与建议
// ===================================================================
s = p.addSlide(); bg(s, NAVY);
tau(s, 9.6, 3.4, 4.2, "1B3352", 0);
s.addText("结论与建议", { x:0.9, y:0.7, w:9, h:0.7, color:WHITE, fontFace:HFONT, fontSize:32, bold:true });
s.addShape(p.ShapeType.roundRect, { x:0.9, y:1.65, w:11.5, h:1.25, rectRadius:0.1, fill:{color:NAVY2} });
s.addText([
  { text:"一句话结论：", options:{ bold:true, color:AQUA, fontSize:16 } },
  { text:"方向判断（几何缩放已死、时间是真货币、拓扑赤字、数据搬运主导）几乎无懈可击；真正经不起细究的是三个头条数字（α=10、500×、+55%）与被回避的能量账。", options:{ color:WHITE, fontSize:15 } },
], { x:1.2, y:1.8, w:10.9, h:0.95, fontFace:HFONT, lineSpacing:23, valign:"middle" });

s.addText("给论文的三条建设性追问", { x:0.9, y:3.15, w:10, h:0.45, color:ICE, fontFace:HFONT, fontSize:16, bold:true });
const rec = [
  "给出 α 的可测量定义与分层分解——把「10×/年」拆成硬件/算法/精度各占多少",
  "为 τ 配强制的能量协同指标，使 τ-first 不能 license 撞电网的设计",
  "公开一组 τ-profile 基准与受控反事实，让「τ 优于纯几何缩放」可被第三方复现",
];
let ry = 3.75;
rec.forEach((t, i) => {
  badge(s, 0.95, ry, 0.42, BLUE, String(i+1), WHITE, 16);
  s.addText(t, { x:1.55, y:ry-0.05, w:10.8, h:0.55, color:WHITE, fontFace:HFONT, fontSize:14, valign:"middle", margin:0, lineSpacing:18 });
  ry += 0.72;
});
s.addShape(p.ShapeType.roundRect, { x:0.9, y:6.15, w:11.5, h:0.8, rectRadius:0.1, fill:{color:"142943"}, line:{color:"2A4A6E", width:1} });
s.addText([
  { text:"内部价值：", options:{ bold:true, color:AQUA, fontSize:13 } },
  { text:"一套「把外部技术主张当假设、用可复现仿真独立评估」的方法与工具，可复用于后续技术尽调。", options:{ color:ICE, fontSize:13 } },
], { x:1.2, y:6.15, w:11, h:0.8, fontFace:HFONT, valign:"middle", lineSpacing:18 });
s.addNotes("结论平衡：肯定方向、指出量化主张的脆弱处；三条追问建设性；强调方法论的内部可复用价值。");

p.writeFile({ fileName: "/home/user/tau_demo/slides_tau_scaling.pptx" })
 .then(f => console.log("written", f));
