"""把 CRITIQUE.md/.en.md 与被引用的图渲染成中英双语可切换的 critique.html。
Bilingual (中/EN) adversarial appendix. Reuses build_report's bilingual pipeline.

用法 / usage: python build_critique.py
"""

import build_report as br

if __name__ == "__main__":
    br.build_bilingual(
        "CRITIQUE.md", "CRITIQUE.en.md",
        "对抗性附录 · τ Scaling 论文质疑",
        "Adversarial Appendix · Challenging the τ Scaling Paper",
        "critique.html")
