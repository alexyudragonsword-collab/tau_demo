"""从 figures/ 与报告内容生成自包含 dashboard.html（图表 base64 内嵌）。

用法: python build_dashboard.py
"""

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def b64(name: str) -> str:
    with open(os.path.join(HERE, "figures", name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


FIGS = {f"FIG{i}": b64(n) for i, n in enumerate([
    "fig1_device_scaling.png", "fig2_fold_criterion.png",
    "fig3_fold_gains.png", "fig4_fanout_dilemma.png",
    "fig5_cluster_scaling.png", "fig6_amdahl_saturation.png",
    "fig7_decade_trajectories.png", "fig8_bottleneck_migration.png",
    "fig9_thermal_constraint.png", "fig10_alpha_decomposition.png"], 1)}

with open(os.path.join(HERE, "dashboard_template.html"), encoding="utf-8") as f:
    html = f.read()

for key, uri in FIGS.items():
    html = html.replace("{{" + key + "}}", uri)

out = os.path.join(HERE, "dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"written {out} ({os.path.getsize(out)/1e6:.1f} MB)")
