"""生成自包含 tau_lab.html（注入模型 JS）。用法: python build_tau_lab.py"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "tau_lab_model.js"), encoding="utf-8") as f:
    model_js = f.read()
with open(os.path.join(HERE, "tau_lab_template.html"), encoding="utf-8") as f:
    html = f.read()

out = os.path.join(HERE, "tau_lab.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html.replace("{{MODEL_JS}}", model_js))
print(f"written {out} ({os.path.getsize(out)/1e3:.0f} KB)")
