"""生成中英双语可切换的自包含 dashboard.html（图 base64 内嵌）。
Bilingual (中/EN) self-contained dashboard: zh body uses figures/, en body figures_en/.

用法 / usage: python build_dashboard.py
"""

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = [f"fig{i}_" for i in range(1, 11)]  # 仅用于计数说明


def b64(figdir: str, idx: int) -> str:
    import glob
    m = glob.glob(os.path.join(HERE, figdir, f"fig{idx}_*.png"))
    with open(m[0], "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def fill(body: str, figdir: str) -> str:
    for i in range(1, 11):
        body = body.replace("{{FIG%d}}" % i, b64(figdir, i))
    return body


def split_head_body(path: str):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    i = html.index("</style>") + len("</style>")
    return html[:i], html[i:]


LANG_CSS = """
<style>
  .langtoggle { position:fixed; top:14px; right:16px; z-index:100; display:flex;
    border:1px solid var(--line); border-radius:7px; overflow:hidden;
    background:var(--surface); box-shadow:0 1px 6px rgba(0,0,0,.18); font-size:13px; }
  .langtoggle button { border:none; background:var(--surface); padding:6px 13px;
    cursor:pointer; color:var(--ink2); font:inherit; }
  .langtoggle button.active { background:var(--accent); color:#fff; }
  .lang-en { display:none; }
  :root[data-lang="en"] .lang-zh { display:none; }
  :root[data-lang="en"] .lang-en { display:block; }
</style>"""

TOGGLE = """
<div class="langtoggle" role="group" aria-label="language">
  <button data-l="zh" class="active">中文</button><button data-l="en">EN</button>
</div>"""

TOGGLE_JS = """
<script>
(function(){
  var root=document.documentElement;
  function set(l){root.setAttribute('data-lang',l);
    root.setAttribute('lang',l==='zh'?'zh-CN':'en');
    document.querySelectorAll('.langtoggle button').forEach(function(b){
      b.classList.toggle('active',b.dataset.l===l);});}
  document.querySelectorAll('.langtoggle button').forEach(function(b){
    b.addEventListener('click',function(){set(b.dataset.l);});});
  set('zh');
})();
</script>"""


def build() -> str:
    head, body_zh = split_head_body(os.path.join(HERE, "dashboard_template.html"))
    _, body_en = split_head_body(os.path.join(HERE, "dashboard_template.en.html"))
    body_zh = fill(body_zh, "figures")
    body_en = fill(body_en, "figures_en")
    html = (head + LANG_CSS + TOGGLE
            + '<div class="lang-zh">' + body_zh + '</div>'
            + '<div class="lang-en">' + body_en + '</div>'
            + TOGGLE_JS)
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written {out} ({os.path.getsize(out)/1e6:.1f} MB)")
    return out


if __name__ == "__main__":
    build()
