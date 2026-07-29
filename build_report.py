"""把 REPORT.md/.en.md 与图合并成中英双语可切换的图文报告。
Merge REPORT.md/.en.md with figures into one bilingual (中/EN) illustrated report.

产物 / outputs (self-contained, no external deps):
  report_full.html  — 双语可切换，中文用 figures/、英文用 figures_en/，图 base64 内嵌
  report_full.pdf   — 由 Chromium 打印（中文视图）

用法 / usage:
  python build_report.py            # html + pdf
  python build_report.py --html     # html only
"""

import base64
import json
import os
import sys

import markdown as md

HERE = os.path.dirname(os.path.abspath(__file__))

CAPTIONS = {
    "fig1_device_scaling.png":
        "图 1 · 器件层：几何缩放的 τ 收益逐代衰减，互连占级延迟比例 22%→72%",
    "fig2_fold_criterion.png":
        "图 2 · 电路层：折叠判据 τ_Benefit 与 τ_Penalty 随混合键合 pitch 的交叉",
    "fig3_fold_gains.png":
        "图 3 · 电路层：LogicFolding 收益，模型（独立文献参数） vs Kirin 2026 实测",
    "fig4_fanout_dilemma.png":
        "图 4 · 封装层：N²-vs-N 扇出困境——可达算力斜率发散与 2.5D 的 ridge 上移",
    "fig5_cluster_scaling.png":
        "图 5 · 系统层：集群扩展效率（大消息）与 MoE 小消息时延，空心方块为 SimPy 离散事件验证点",
    "fig6_amdahl_saturation.png":
        "图 6 · 级联实验 A：单层优化的 Amdahl 饱和，虚线为各层占比决定的加速上限",
    "fig7_decade_trajectories.png":
        "图 7 · 级联实验 B：十年演进，单点优化饱和 vs 全栈 τ-first 维持年化 α",
    "fig8_bottleneck_migration.png":
        "图 8 · 级联实验 C：瓶颈迁移——每步优化使主导 τ 层转移",
    "fig9_thermal_constraint.png":
        "图 9 · 热约束：多层折叠的可持续频率与温升构成（对应论文开放问题 §6）",
    "fig10_alpha_decomposition.png":
        "图 10 · 级联实验 D：论文 AI 侧 α≈10/年 的口径分解",
}
CAPTIONS_EN = {
    "fig1_device_scaling.png":
        "Fig 1 · Device layer: τ gain from geometric scaling decays; interconnect share of stage delay 22%→72%",
    "fig2_fold_criterion.png":
        "Fig 2 · Circuit layer: folding criterion — τ_Benefit vs τ_Penalty crossing over hybrid-bond pitch",
    "fig3_fold_gains.png":
        "Fig 3 · Circuit layer: LogicFolding gains, model (independent literature) vs Kirin 2026 measured",
    "fig4_fanout_dilemma.png":
        "Fig 4 · Package layer: N²-vs-N fan-out dilemma — achievable-compute divergence and 2.5D ridge rise",
    "fig5_cluster_scaling.png":
        "Fig 5 · System layer: cluster scaling efficiency (large msg) and MoE small-msg latency; hollow squares are SimPy discrete-event validation points",
    "fig6_amdahl_saturation.png":
        "Fig 6 · Cascade A: Amdahl saturation of single-layer optimization; dashed = per-layer speedup ceiling",
    "fig7_decade_trajectories.png":
        "Fig 7 · Cascade B: ten-year evolution — single-point saturates vs full-stack τ-first sustains annual α",
    "fig8_bottleneck_migration.png":
        "Fig 8 · Cascade C: bottleneck migration — each step shifts the dominant τ layer",
    "fig9_thermal_constraint.png":
        "Fig 9 · Thermal constraint: sustainable frequency and ΔT composition of multi-tier folding (paper open problem §6)",
    "fig10_alpha_decomposition.png":
        "Fig 10 · Cascade D: accounting decomposition of the paper's AI-side α≈10/yr",
}


def data_uri(fname: str, figdir: str) -> str:
    with open(os.path.join(HERE, figdir, fname), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def inject_figures(md_text: str, figdir: str = "figures",
                   captions: dict = CAPTIONS) -> str:
    """在每张图被引用的那一行之后，插入内嵌的 <figure> 块（图取自 figdir）。"""
    out = []
    for line in md_text.splitlines():
        out.append(line)
        for fname, cap in captions.items():
            if fname in line:
                out.append("")
                out.append(
                    f'<figure>\n<img src="{data_uri(fname, figdir)}" alt="{cap}">\n'
                    f'<figcaption>{cap}</figcaption>\n</figure>')
                out.append("")
    return "\n".join(out)


def render_body(md_path: str, figdir: str, captions: dict) -> str:
    with open(os.path.join(HERE, md_path), encoding="utf-8") as f:
        src = f.read()
    src = inject_figures(src, figdir, captions)
    body = md.markdown(src, extensions=[
        "tables", "fenced_code", "sane_lists", "toc", "attr_list"])
    body = body.replace("<table>", '<div class="table-wrap"><table>')
    body = body.replace("</table>", "</table></div>")
    return body


CSS = """
:root{--ink:#14181c;--ink2:#3f464e;--muted:#6b7178;--line:#dfe3e8;
  --accent:#2a5fa0;--accent-soft:#eef3fa;--warn:#8a5a00;--warn-soft:#fbf3e2;
  --code-bg:#f4f6f8;--surface:#fff;}
*{box-sizing:border-box;}
body{margin:0;background:#eceef1;color:var(--ink);
  font-family:-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",
  "Noto Sans CJK SC","Segoe UI",sans-serif;line-height:1.75;font-size:14.5px;}
.page{max-width:860px;margin:24px auto;background:var(--surface);
  padding:56px 64px 72px;box-shadow:0 1px 6px rgba(0,0,0,.08);}
h1{font-size:26px;line-height:1.4;margin:0 0 6px;font-weight:750;text-wrap:balance;}
h2{font-size:20px;margin:34px 0 10px;padding-top:14px;border-top:2px solid var(--ink);
  font-weight:700;text-wrap:balance;break-after:avoid;}
h3{font-size:16.5px;margin:24px 0 6px;font-weight:650;break-after:avoid;}
h4{font-size:14.5px;margin:16px 0 4px;color:var(--ink2);break-after:avoid;}
p{margin:9px 0;}
blockquote{margin:14px 0;padding:8px 18px;border-left:3px solid var(--accent);
  background:var(--accent-soft);border-radius:0 5px 5px 0;color:var(--ink2);}
blockquote p{margin:4px 0;}
ul,ol{margin:9px 0;padding-left:1.5em;}
li{margin:3px 0;}li::marker{color:var(--accent);}
code{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:.9em;
  background:var(--code-bg);border:1px solid var(--line);border-radius:4px;padding:.5px 5px;}
pre{background:var(--code-bg);border:1px solid var(--line);border-radius:6px;
  padding:12px 16px;overflow-x:auto;line-height:1.6;break-inside:avoid;}
pre code{background:none;border:none;padding:0;}
a{color:var(--accent);text-underline-offset:2px;}
strong{font-weight:650;}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:12.8px;
  break-inside:avoid;}
th,td{border:1px solid var(--line);padding:6px 11px;text-align:left;vertical-align:top;}
th{background:var(--code-bg);font-weight:650;color:var(--ink2);}
.table-wrap{overflow-x:auto;}
figure{margin:20px 0;padding:14px;background:#fcfcfb;border:1px solid var(--line);
  border-radius:7px;break-inside:avoid;text-align:center;}
figure img{max-width:100%;height:auto;border-radius:3px;}
figcaption{margin-top:9px;font-size:12px;color:var(--muted);
  font-family:ui-monospace,Menlo,Consolas,monospace;line-height:1.55;text-align:center;}
hr{border:none;border-top:1px solid var(--line);margin:26px 0;}
.doc-meta{color:var(--muted);font-size:12.5px;margin:2px 0 0;}
.lang-block{display:none;}
:root[data-lang="zh"] .lang-zh{display:block;}
:root[data-lang="en"] .lang-en{display:block;}
.langtoggle{position:fixed;top:14px;right:16px;z-index:100;display:flex;
  border:1px solid var(--line);border-radius:7px;overflow:hidden;background:#fff;
  box-shadow:0 1px 5px rgba(0,0,0,.12);font-size:13px;}
.langtoggle button{border:none;background:#fff;padding:6px 14px;cursor:pointer;
  color:var(--ink2);font:inherit;}
.langtoggle button.active{background:var(--accent);color:#fff;}
@media print{
  body{background:#fff;font-size:11.5px;}
  .page{box-shadow:none;margin:0;max-width:none;padding:0 6mm;}
  .langtoggle{display:none;}
  figure,table,pre,blockquote{break-inside:avoid;}
  h1,h2,h3,h4{break-after:avoid;}
  a{color:var(--ink);text-decoration:none;}
}
"""

_PAGE = """<!doctype html><html lang="zh-CN" data-lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_zh}</title><style>{css}</style></head>
<body>
<div class="langtoggle" role="group" aria-label="language">
  <button data-l="zh" class="active">中文</button><button data-l="en">EN</button>
</div>
<div class="page">
  <div class="lang-block lang-zh">{body_zh}</div>
  <div class="lang-block lang-en">{body_en}</div>
</div>
<script>
(function(){{
  var TITLE={{zh:{title_zh_j},en:{title_en_j}}},root=document.documentElement;
  function set(l){{root.setAttribute('data-lang',l);root.setAttribute('lang',l==='zh'?'zh-CN':'en');
    document.title=TITLE[l];
    document.querySelectorAll('.langtoggle button').forEach(function(b){{
      b.classList.toggle('active',b.dataset.l===l);}});}}
  document.querySelectorAll('.langtoggle button').forEach(function(b){{
    b.addEventListener('click',function(){{set(b.dataset.l);}});}});
  set('zh');
}})();
</script>
</body></html>"""


def build_bilingual(zh_md, en_md, title_zh, title_en, out_name):
    body_zh = render_body(zh_md, "figures", CAPTIONS)
    body_en = render_body(en_md, "figures_en", CAPTIONS_EN)
    html = _PAGE.format(css=CSS, body_zh=body_zh, body_en=body_en,
                        title_zh=title_zh, title_en=title_en,
                        title_zh_j=json.dumps(title_zh, ensure_ascii=False),
                        title_en_j=json.dumps(title_en, ensure_ascii=False))
    out = os.path.join(HERE, out_name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


def build_pdf(html_path: str, out_name="report_full.pdf") -> None:
    import glob
    from playwright.sync_api import sync_playwright
    exe = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    pdf = os.path.join(HERE, out_name)
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe[0] if exe else None)
        pg = b.new_page()
        pg.goto("file://" + html_path, wait_until="networkidle")
        pg.pdf(path=pdf, format="A4", print_background=True,
               margin={"top": "14mm", "bottom": "14mm",
                       "left": "12mm", "right": "12mm"})
        b.close()
    print(f"written {pdf} ({os.path.getsize(pdf)/1e6:.1f} MB)")


if __name__ == "__main__":
    html_path = build_bilingual(
        "REPORT.md", "REPORT.en.md",
        "τ Scaling 全栈级联仿真验证报告",
        "τ Scaling — Full-Stack Cascade Simulation Report",
        "report_full.html")
    if "--html" not in sys.argv:
        build_pdf(html_path)
