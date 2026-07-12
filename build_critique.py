"""把 CRITIQUE.md 与被引用的图渲染成自包含 critique.html（图 base64 内嵌）。

复用 build_report.py 的渲染管线（CSS/模板/图注入）。
用法: python build_critique.py
"""

import os

import markdown as md

import build_report as br

HERE = os.path.dirname(os.path.abspath(__file__))


def build() -> str:
    with open(os.path.join(HERE, "CRITIQUE.md"), encoding="utf-8") as f:
        src = f.read()
    src = br.inject_figures(src)              # 仅插入文中出现的图，按 fig1..10 顺序
    body = md.markdown(src, extensions=[
        "tables", "fenced_code", "sane_lists", "toc", "attr_list"])
    body = body.replace("<table>", '<div class="table-wrap"><table>')
    body = body.replace("</table>", "</table></div>")
    html = br.TEMPLATE.format(
        title="对抗性附录 · τ Scaling 论文质疑", css=br.CSS, body=body)
    out = os.path.join(HERE, "critique.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


if __name__ == "__main__":
    build()
