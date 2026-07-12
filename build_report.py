"""把 REPORT.md 与 figures/ 的 10 张图合并成一个图文并茂的报告。

产物（均自包含、无外部依赖）：
  report_full.html  — 渲染后的完整报告，图以 base64 内嵌，浏览器直接打开
  report_full.pdf   — 由 Chromium 打印 report_full.html 得到（可选，需 Playwright）

用法:
  python build_report.py            # 生成 html + pdf
  python build_report.py --html     # 只生成 html
"""

import base64
import os
import sys

import markdown as md

HERE = os.path.dirname(os.path.abspath(__file__))

# 每张图的说明（按被引用小节顺序插入）
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


def data_uri(fname: str) -> str:
    with open(os.path.join(HERE, "figures", fname), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def inject_figures(md_text: str) -> str:
    """在每张图被引用的那一行之后，插入内嵌的 <figure> 块。"""
    out = []
    for line in md_text.splitlines():
        out.append(line)
        for fname, cap in CAPTIONS.items():           # 保持 fig1..fig10 顺序
            if fname in line:
                out.append("")
                out.append(
                    f'<figure>\n<img src="{data_uri(fname)}" alt="{cap}">\n'
                    f'<figcaption>{cap}</figcaption>\n</figure>')
                out.append("")
    return "\n".join(out)


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
@media print{
  body{background:#fff;font-size:11.5px;}
  .page{box-shadow:none;margin:0;max-width:none;padding:0 6mm;}
  h2{break-before:auto;}
  figure,table,pre,blockquote{break-inside:avoid;}
  h1,h2,h3,h4{break-after:avoid;}
  a{color:var(--ink);text-decoration:none;}
}
"""

TEMPLATE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{css}</style></head>
<body><div class="page">{body}</div></body></html>"""


def build_html() -> str:
    with open(os.path.join(HERE, "REPORT.md"), encoding="utf-8") as f:
        src = f.read()
    src = inject_figures(src)
    body = md.markdown(src, extensions=[
        "tables", "fenced_code", "sane_lists", "toc", "attr_list"])
    # 表格加横向滚动容器（长表在窄屏/打印时可读）
    body = body.replace("<table>", '<div class="table-wrap"><table>')
    body = body.replace("</table>", "</table></div>")
    html = TEMPLATE.format(title="τ Scaling 全栈级联仿真验证报告",
                           css=CSS, body=body)
    out = os.path.join(HERE, "report_full.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


def build_pdf(html_path: str) -> None:
    import glob
    from playwright.sync_api import sync_playwright
    exe = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    pdf = os.path.join(HERE, "report_full.pdf")
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
    html_path = build_html()
    if "--html" not in sys.argv:
        build_pdf(html_path)
