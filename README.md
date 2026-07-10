# tau_demo — τ Scaling 理论的全栈级联仿真验证

对何庭波（Huawei）《A Time Scaling Theory for Multi-Layer Electronic Systems》
（ChinaXiv:202605.00224）核心思想的独立仿真论证。

用晶体管 → 电路 → 芯片/封装 → 系统四层级联模型，内嵌 LogicFolding、
N²-vs-N 扇出困境、UB 集群通信三个子模型，检验论文的五个核心命题
（P1 几何缩放趋平、P2 折叠判据、P3 拓扑赤字、P4 通信 τ 压缩、
P5 全栈共享优化目标与瓶颈迁移）。

**分析结论见 [REPORT.md](REPORT.md)。**

## 快速开始

```bash
pip install -r requirements.txt
python run_all.py       # 生成 figures/fig1-fig8 + 控制台对照表
python sensitivity.py   # 关键参数 ±50% 扰动的稳健性检查
```

## 结果速览（模型输入全部来自独立公开文献）

| 命题 | 模型结果 | 论文对照 |
|------|---------|---------|
| P2 折叠线长/偏斜/频率 | −24.9% / −24.9% / +12.3% | −30% / −25% / +13% (Kirin 2026) |
| P2 折叠判据反转点 | gear ratio ≈ 4.3（敏感区 3.3–6.2） | 工程结论 <3（安全侧） |
| P3 2.5D ridge 上移 | N≈55mm 后 GEMM 也访存受限 | "拓扑赤字无法靠晶体管弥补" |
| P4 小消息 all-to-all | 同物理线换协议栈 9–150× | UB ≈500× τ 压缩 |
| P5 十年年化 α | 协同 1.22 vs 单点 1.02–1.08 | τ_{n+1}=τ_n/α 需跨层协同 |

## 目录结构

```
tau_sim/
├── params.py          # 全部校准参数（逐项注明文献出处）
├── layer1_device.py   # 器件层：FO4 + 铜互连尺寸效应
├── layer2_circuit.py  # 电路层：Davis 线长分布 + LogicFolding
├── layer3_chip.py     # 封装层：N²-vs-N + roofline
├── layer4_system.py   # 系统层：α-β 集合通信 + SimPy 离散事件仿真
└── cascade.py         # 级联：Amdahl 饱和 / 十年轨迹 / 瓶颈迁移
run_all.py             # 一键运行全部实验
sensitivity.py         # 敏感性检查
figures/               # 仿真输出图表
REPORT.md              # 完整分析报告（论文解读 + 结果 + 局限）
```
