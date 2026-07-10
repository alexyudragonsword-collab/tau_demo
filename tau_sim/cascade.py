"""级联组合 — τ_system = g(各层 τ)，验证论文总命题 P5.

系统场景：AI 训练迭代（论文 α≈10/年 的负载端）。
把系统 τ 分解为可独立优化的分量：

  τ_iter = t_compute (算力·频率 ← 电路层 ← 器件层)
         + t_memory  (访存暴露时间 ← 封装层带宽)
         + t_comm    (梯度同步 + 小消息同步 ← 系统层 fabric)
         + t_other   (软件调度/优化器等)

实验 A（Amdahl 饱和）：单层加速 k∈[1,100]，系统加速饱和于该层占比倒数。
实验 B（协同 vs 单点）：10 年演进轨迹，只优化单层 vs 全栈 τ-first。
实验 C（瓶颈迁移）：按论文叙事依次引入 UB 协议 → Hi-ONE 光带宽 →
    3D Folding 内存 → LogicFolding 算力，展示主导 τ 层迁移
    ——“主导 τ 层就是下一个投资方向”。
"""

from dataclasses import dataclass, replace

import numpy as np

from . import params as P
from .layer4_system import hierarchical_allreduce_t


@dataclass
class SystemConfig:
    """系统 τ 的杠杆（k_* 为相对基线的加速倍数，>1 更快）。"""
    n_gpus: int = 4096
    k_compute: float = 1.0    # 器件+电路层 (节点演进, LogicFolding)
    k_memory: float = 1.0     # 封装层 (3D Folding / HBM 混合键合)
    fabric: str = "legacy_tcp"
    k_comm: float = 1.0       # 系统层 fabric 代际内的持续改进 (带宽/延迟)
    k_other: float = 1.0      # 软件栈


# 基线分量标定：计算/访存/其他的占比取大规模训练实测
# (Llama3 405B MFU≈40%; MegaScale/PaLM: 访存暴露+重计算 ~25-30%)
BASE_COMPUTE_FRAC = 0.45
BASE_MEMORY_FRAC = 0.25
BASE_OTHER_FRAC = 0.05
# 通信分量不设固定占比，由 Layer4 模型按 fabric/规模计算

# 每迭代小消息集合操作数（TP/PP 同步、调度、参数服务器心跳等,
# 逐消息付出 o+α; MegaScale/Domino: 小消息延迟是暴露通信的主要来源之一）
SMALL_MSGS_PER_ITER = 5000


def iteration_tau(cfg: SystemConfig) -> dict:
    """迭代 τ 的分量分解 (秒)。"""
    total_flops = P.FLOPS_PER_TOKEN * P.GLOBAL_BATCH_TOKENS
    t_compute = total_flops / (cfg.n_gpus * P.PER_GPU_TFLOPS_EFF * 1e12)
    t_memory = t_compute * BASE_MEMORY_FRAC / BASE_COMPUTE_FRAC
    t_other = t_compute * BASE_OTHER_FRAC / BASE_COMPUTE_FRAC

    fab = P.FABRICS[cfg.fabric]
    vol = P.MODEL_PARAMS * P.BYTES_PER_PARAM
    t_large = hierarchical_allreduce_t(cfg.n_gpus, vol, fab)
    per_msg = fab["o"] + fab["alpha_inter"]
    t_small = SMALL_MSGS_PER_ITER * per_msg

    return {
        "compute": t_compute / cfg.k_compute,
        "memory": t_memory / cfg.k_memory,
        "comm": (t_large + t_small) / cfg.k_comm,
        "other": t_other / cfg.k_other,
    }


def total_tau(cfg: SystemConfig) -> float:
    return float(sum(iteration_tau(cfg).values()))


# ---------------------------------------------------------------------
# 实验 A — Amdahl 饱和
# ---------------------------------------------------------------------

def amdahl_scan(base: SystemConfig | None = None,
                ks: np.ndarray | None = None) -> dict:
    """单独把某一分量加速 k 倍，观察系统加速的饱和。"""
    base = base or SystemConfig()
    ks = ks if ks is not None else np.logspace(0, 2, 60)
    parts0 = iteration_tau(base)
    t0 = sum(parts0.values())
    out = {"k": ks, "fractions": {m: v / t0 for m, v in parts0.items()}}
    for layer in ["compute", "memory", "comm", "other"]:
        speedups = []
        for k in ks:
            parts = dict(parts0)
            parts[layer] = parts0[layer] / k
            speedups.append(t0 / sum(parts.values()))
        out[layer] = np.array(speedups)
    return out


# ---------------------------------------------------------------------
# 实验 B — 十年轨迹：单点优化 vs 全栈 τ-first
# ---------------------------------------------------------------------

def decade_trajectories(years: int = 10, n_gpus: int = 4096) -> dict:
    """三种投资策略下的系统 τ 轨迹（归一化到第 0 年）。

    只推器件节点   : 每年算力 +15%（后摩尔时代先进节点的年化收益）
    只换网络fabric : 第2年 RDMA、第4年 UB+Hi-ONE，其余层不动
    全栈 τ-first  : 器件 +15%/年 为底座，且每年把一次“定向改进”
                    (+20%) 投给当年主导 τ 层；里程碑与论文路线图对应：
                    第2年 LogicFolding(+25% 算力)、第3年 UB 协议、
                    第4年 Hi-ONE 光带宽、第5年 3D Folding(+60% 内存)
    """
    base = SystemConfig(n_gpus=n_gpus)
    t0 = total_tau(base)

    def run_device_only():
        return np.array([total_tau(replace(base, k_compute=1.15 ** y))
                         for y in range(years + 1)])

    def run_fabric_only():
        taus = []
        for y in range(years + 1):
            fab = ("legacy_tcp" if y < 2 else
                   "legacy_rdma" if y < 4 else "ub_hione")
            taus.append(total_tau(replace(base, fabric=fab)))
        return np.array(taus)

    def run_tau_first():
        taus = [t0]
        cfg = replace(base)
        for y in range(1, years + 1):
            cfg = replace(cfg, k_compute=cfg.k_compute * 1.15)
            if y == 2:
                cfg = replace(cfg, k_compute=cfg.k_compute * 1.25)  # 折叠
            if y == 3:
                cfg = replace(cfg, fabric="ub_protocol")
            if y == 4:
                cfg = replace(cfg, fabric="ub_hione")
            if y == 5:
                cfg = replace(cfg, k_memory=cfg.k_memory * 1.6)     # 3D 折叠
            parts = iteration_tau(cfg)
            dom = max(parts, key=parts.get)
            if dom == "compute":
                cfg = replace(cfg, k_compute=cfg.k_compute * 1.2)
            elif dom == "memory":
                cfg = replace(cfg, k_memory=cfg.k_memory * 1.2)
            elif dom == "comm":
                # fabric 代际内持续演进 (UB2.0、Hi-ONE 带宽翻代等)
                cfg = replace(cfg, k_comm=cfg.k_comm * 1.2)
            else:
                cfg = replace(cfg, k_other=cfg.k_other * 1.2)
            taus.append(total_tau(cfg))
        return np.array(taus)

    return {
        "只推器件节点": run_device_only() / t0,
        "只换网络 fabric": run_fabric_only() / t0,
        "全栈 τ-first 协同": run_tau_first() / t0,
    }


# ---------------------------------------------------------------------
# 实验 C — 瓶颈迁移
# ---------------------------------------------------------------------

def bottleneck_migration(n_gpus: int = 4096) -> list[tuple[str, dict]]:
    """论文叙事顺序的五个阶段，返回各阶段 τ 分量。"""
    stages = [
        ("阶段0\n传统协议栈",
         SystemConfig(n_gpus=n_gpus, fabric="legacy_tcp")),
        ("阶段1\n+UB 内存语义\n(免协议转换)",
         SystemConfig(n_gpus=n_gpus, fabric="ub_protocol")),
        ("阶段2\n+Hi-ONE 光互连\n(带宽扁平化)",
         SystemConfig(n_gpus=n_gpus, fabric="ub_hione")),
        ("阶段3\n+3D Folding\n(表面供内存)",
         SystemConfig(n_gpus=n_gpus, fabric="ub_hione", k_memory=2.5)),
        ("阶段4\n+LogicFolding\n(算力提频)",
         SystemConfig(n_gpus=n_gpus, fabric="ub_hione", k_memory=2.5,
                      k_compute=1.6)),
    ]
    return [(name, iteration_tau(cfg)) for name, cfg in stages]
