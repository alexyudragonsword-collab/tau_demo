"""Layer 4 — 系统层：集群通信 τ (验证论文命题 P4).

通信代价模型（α-β 扩展, [Thakur 2005]）：
  每消息代价 = o (软件/协议发起开销) + α (网络传输延迟) + 字节/B
三档 fabric（见 params.FABRICS）：
  tcp  — 传统协议栈：内核栈+DMA 拷贝+协议转换，每消息均需握手
  rdma — RDMA/IB：绕过内核，仍有 PCIe→NIC 转换与 WQE/门铃开销
  ub   — 内存语义统一总线：免转换、硬件一致性、亚 μs 远程访问

集合通信：
  分层 AllReduce（训练梯度，大消息）:
    节点内 reduce-scatter + 节点间 ring allreduce + 节点内 all-gather
  All-to-All（MoE 路由，小消息）:
    每卡向其余 n-1 卡各发一条消息；tcp 类逐消息串行握手，
    rdma/ub 类可流水（发起开销仍逐消息累积）

同时提供 SimPy 离散事件仿真（含链路争用与随机抖动），
在中小规模上验证解析模型，大规模扫描用解析式。
"""

from dataclasses import dataclass

import numpy as np
import simpy

from . import params as P


# ---------------------------------------------------------------------
# 解析代价模型
# ---------------------------------------------------------------------

def ring_allreduce_t(n: int, vol_bytes: float, o: float, alpha: float,
                     bw: float, per_msg_handshake: bool) -> float:
    """Ring AllReduce: 2(n-1) 步，每步一条消息."""
    if n <= 1:
        return 0.0
    steps = 2 * (n - 1)
    per_step_lat = o + alpha if per_msg_handshake else max(o, alpha)
    return steps * per_step_lat + 2.0 * vol_bytes * (n - 1) / (n * bw)


def hierarchical_allreduce_t(n_gpus: int, vol_bytes: float, fabric: dict,
                             gpus_per_node: int = None) -> float:
    """节点内 RS/AG + 节点间 ring AllReduce."""
    g = gpus_per_node or P.GPUS_PER_NODE
    n_nodes = max(1, n_gpus // g)
    t = 0.0
    if g > 1:
        # 节点内 reduce-scatter + all-gather ≈ 一次 ring allreduce 的代价
        t += ring_allreduce_t(g, vol_bytes, fabric["o"],
                              fabric["alpha_intra"], fabric["bw_intra"],
                              fabric["per_msg_handshake"])
    if n_nodes > 1:
        t += ring_allreduce_t(n_nodes, vol_bytes / g, fabric["o"],
                              fabric["alpha_inter"], fabric["bw_inter"],
                              fabric["per_msg_handshake"])
    return t


def alltoall_t(n: int, msg_bytes: float, fabric: dict) -> float:
    """All-to-All（跨节点为主，取 inter 参数）."""
    if n <= 1:
        return 0.0
    o, a, bw = fabric["o"], fabric["alpha_inter"], fabric["bw_inter"]
    wire = (n - 1) * msg_bytes / bw
    if fabric["per_msg_handshake"]:
        return (n - 1) * (o + a + msg_bytes / bw)     # 逐消息串行
    return (n - 1) * o + a + wire                     # 发起开销累积，线上流水


# ---------------------------------------------------------------------
# 负载：训练迭代 / MoE 推理步
# ---------------------------------------------------------------------

@dataclass
class IterResult:
    n_gpus: int
    fabric: str
    t_compute: float
    t_comm: float
    t_iter: float
    scaling_eff: float   # 相对理想线性扩展


def train_iteration(n_gpus: int, fabric_name: str) -> IterResult:
    """数据并行训练一个迭代：计算 + 梯度分层 AllReduce."""
    fab = P.FABRICS[fabric_name]
    total_flops = P.FLOPS_PER_TOKEN * P.GLOBAL_BATCH_TOKENS
    t_comp = total_flops / (n_gpus * P.PER_GPU_TFLOPS_EFF * 1e12)
    vol = P.MODEL_PARAMS * P.BYTES_PER_PARAM
    t_comm = hierarchical_allreduce_t(n_gpus, vol, fab)
    t_iter = t_comp + t_comm
    # 理想：t_comp 随卡数线性下降、无通信
    t_ideal = total_flops / (n_gpus * P.PER_GPU_TFLOPS_EFF * 1e12)
    return IterResult(n_gpus, fabric_name, t_comp, t_comm, t_iter,
                      t_ideal / t_iter)


def moe_decode_step(n_gpus: int, fabric_name: str,
                    experts_parallel: int = None) -> IterResult:
    """MoE 推理 decode 一步：每层 2 次 all-to-all（dispatch+combine）."""
    fab = P.FABRICS[fabric_name]
    ep = experts_parallel or min(n_gpus, 64)
    # 每对端消息：每卡 token 数 × hidden × bf16 / 目标卡数
    msg = P.MOE_TOKENS_PER_GPU_DECODE * P.MOE_HIDDEN * 2 / ep
    t_comm = P.MOE_LAYERS * 2 * alltoall_t(ep, msg, fab)
    # decode 计算（访存受限，粗略常数/卡）
    t_comp = P.MOE_LAYERS * 8e-6
    t_step = t_comp + t_comm
    return IterResult(n_gpus, fabric_name, t_comp, t_comm, t_step,
                      t_comp / t_step)


# ---------------------------------------------------------------------
# SimPy 离散事件仿真（验证解析模型：含链路争用 + 抖动）
# ---------------------------------------------------------------------

def simpy_ring_allreduce(n: int, vol_bytes: float, fabric: dict,
                         jitter: float = 0.05, seed: int = 7) -> float:
    """事件级 ring allreduce：n 个参与者、单向环、每步同步。

    每步每卡向右邻发送 chunk (vol/n)：发起开销 o → 占用本卡出链路
    (chunk/bw) → 传播 α。链路为 simpy.Resource 容量 1（争用显式化）。
    """
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    o, a, bw = fabric["o"], fabric["alpha_inter"], fabric["bw_inter"]
    chunk = vol_bytes / n
    links = [simpy.Resource(env, capacity=1) for _ in range(n)]
    step_barrier = [env.event() for _ in range(2 * (n - 1))]
    arrived = [0] * (2 * (n - 1))

    def worker(rank: int):
        """单卡进程：2(n−1) 步，每步向右邻发一个 chunk 后等全体到齐。"""
        for step in range(2 * (n - 1)):
            with links[rank].request() as req:
                yield req
                lat = (o + a) if fabric["per_msg_handshake"] else max(o, a)
                yield env.timeout(lat * rng.uniform(1, 1 + jitter)
                                  + chunk / bw)
            arrived[step] += 1
            if arrived[step] == n:
                step_barrier[step].succeed()
            yield step_barrier[step]

    for r in range(n):
        env.process(worker(r))
    env.run()
    return float(env.now)


def simpy_alltoall(n: int, msg_bytes: float, fabric: dict,
                   jitter: float = 0.05, seed: int = 7) -> float:
    """事件级 all-to-all：每卡出链路容量 1，n-1 条消息排队发送."""
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    o, a, bw = fabric["o"], fabric["alpha_inter"], fabric["bw_inter"]
    links = [simpy.Resource(env, capacity=1) for _ in range(n)]
    done = env.event()
    remaining = [n * (n - 1)]

    def sender(rank: int):
        """单卡进程：向其余 n−1 张卡各发一条消息，共享本卡出链路。"""
        for dst in range(n):
            if dst == rank:
                continue
            with links[rank].request() as req:
                yield req
                occupy = msg_bytes / bw + o
                if fabric["per_msg_handshake"]:
                    occupy += a          # 串行等待对端确认
                yield env.timeout(occupy * rng.uniform(1, 1 + jitter))
            if not fabric["per_msg_handshake"]:
                yield env.timeout(a)     # 传播延迟不占链路
            remaining[0] -= 1
            if remaining[0] == 0:
                done.succeed()

    for r in range(n):
        env.process(sender(r))
    env.run(until=done)
    return float(env.now)
