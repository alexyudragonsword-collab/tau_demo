"""全部仿真参数，逐项注明出处。

校准原则：论文自身数据（Kirin 实测、UB 500×）只作为“待复现目标”，
不作为模型输入；模型输入取自独立公开文献，使仿真结果与论文数字的
吻合具有论证力而非循环论证。

出处缩写（详见 REPORT.md 参数表）：
  [IRDS]      International Roadmap for Devices and Systems
  [Sakurai]   Sakurai & Newton, IEEE JSSC 25(2), 1990 (alpha-power law)
  [Harris]    Harris, FO4 delay metric; HMC E158 讲义 (线电容 0.2fF/μm)
  [Stillmaker] Stillmaker & Baas, Integration VLSI J. 2017 (节点缩放方程)
  [Steinhogl] Steinhögl et al., PRB 2002 (铜线宽-电阻率)
  [Davis]     Davis, De, Meindl, IEEE TED 45(3), 1998 (先验线长分布)
  [Rahman]    Rahman & Reif, IEEE TVLSI 8(6), 2000 (3D 线长模型)
  [Bakoglu]   Bakoglu 1990 (Rent 指数)
  [imec]      imec ECTC/IEDM 2023-2025 (混合键合 pitch/电阻)
  [SoIC]      Chen et al., ECTC 2019 + TSMC SoIC 路线图报道
  [Thakur]    Thakur, Rabenseifner, Gropp, IJHPCA 2005 (集合通信代价)
  [ZeRO]      Rajbhandari et al., SC 2020 (DP 梯度通信量 2Ψ)
  [NV]        NVIDIA H100/NVLink/Quantum-2 公开规格
  [CM384]     Huawei CloudMatrix384, arXiv:2506.12708 (UB 392GB/s, <1μs)
  [UBMesh]    UB-Mesh, arXiv:2503.20377 (每跳 ~150ns)
  [Llama3]    Llama 3 405B 报告 (16K H100, MFU 38-43%)
  [Paper]     何庭波, ChinaXiv:202605.00224 (被验证论文, 仅作对照目标)
"""

# =====================================================================
# Layer 1 — 晶体管/器件层
# =====================================================================

# FO4 为公开锚点插值 [Stillmaker/Harris]（foundry 精确值保密, ±30%）;
# Vdd 为公开típ值 [TSMC 公开页/报道]; Lg 为物理栅长(节点名已与尺寸脱钩);
# mx_pitch/w: 最细局部互连金属间距/线宽 (nm) [imec 逻辑路线图]
NODES = {
    "28nm": dict(lg=30.0, vdd=0.95, vth=0.35, fo4=15.0, mx_pitch=90, w=45),
    "16nm": dict(lg=26.0, vdd=0.80, vth=0.33, fo4=11.0, mx_pitch=64, w=32),
    "7nm":  dict(lg=20.0, vdd=0.75, vth=0.30, fo4=8.0,  mx_pitch=40, w=20),
    "5nm":  dict(lg=17.0, vdd=0.72, vth=0.28, fo4=7.0,  mx_pitch=30, w=15),
    "3nm":  dict(lg=15.0, vdd=0.70, vth=0.26, fo4=6.0,  mx_pitch=24, w=12),
}
NODE_ORDER = ["28nm", "16nm", "7nm", "5nm", "3nm"]

ALPHA_POWER = 1.25         # 速度饱和指数 [Sakurai]; 现代短沟道 1.1-1.3
MU_LONG_CHANNEL = 2.0      # 长沟道平方律对照 (α=2 即 Shockley)

# 铜互连: ρ_eff(w) ≈ ρ0·(1 + λ/w), λ≈40nm 平均自由程
# 单参数拟合 [Steinhogl] 实测点 (40nm→~3, 20nm→3-5, 18nm→~9 μΩ·cm 含阻挡层)
RHO_CU_BULK = 1.68e-8      # Ω·m
CU_MFP_NM = 40.0
WIRE_AR = 2.0              # 互连纵横比
WIRE_CAP_PER_M = 0.20e-9   # F/m = 0.2 fF/μm，跨节点近似常数 [Harris]


def rho_cu(width_nm: float) -> float:
    """铜电阻率的线宽尺寸效应（工程单参数拟合）."""
    return RHO_CU_BULK * (1.0 + CU_MFP_NM / width_nm)


# =====================================================================
# Layer 2 — 电路层 / LogicFolding
# =====================================================================

RENT_P = 0.62              # Rent 指数, 高速逻辑 0.6-0.75, 取偏保守 [Bakoglu]
N_GATES = 1.0e7            # 折叠域门数（一个处理核量级）
LOGIC_DEPTH = 16           # 关键路径逻辑深度（FO4 级数），高频核典型 14-18
FOLD_EFFICIENCY = 0.85     # 实际布局达到 1/√k 理论线长收缩的效率
                           # (实测 2 层 16-25% vs 理论 29% → 0.6-0.85) [Rahman]

# 混合键合 (F2F)。pitch: 量产 6μm(2026)→R&D 2μm(imec D2W)→0.4μm(W2W);
# 论文 Kirin 2026 用 1.5μm。电性: R≈0.1-0.5Ω, C 亚 fF、随焊盘面积缩放 [imec/SoIC]
HB_CAP_PER_PAD_2UM = 0.2e-15   # F @ 2μm pitch
HB_RES_PER_PAD = 0.3           # Ω（键合点+两侧过孔栈）
TOP_METAL_PITCH_NM = 720       # 顶层金属间距 [Paper 对照, 与公开工艺一致]

# TSV（F2B/供电用; F2F 信号不经 TSV）
TSV_CAP = 30e-15           # F, 5μm 级 TSV [文献 10-200fF 区间中值]

# 折叠密度开销: TSV KOZ + 供电网络 + 键合冗余（2 层折叠单层开销）
FOLD_AREA_OVERHEAD_2T = 0.23
AREA_UTILIZATION = 0.68    # 版图利用率 [Paper: Kirin 68%; 业界 60-75%]

# 论文对照目标（不进入模型，仅画在图上做对照）
PAPER_TARGETS = dict(
    wire_len_reduction=0.30,     # 代表性核线长 -30%
    freq_gain=0.13,              # P核频率 +13%
    density_before=155.0,        # MTr/mm²
    density_after=238.0,         # (+54%)
    clock_skew_reduction=0.25,
)

# =====================================================================
# Layer 3 — 芯片/封装层 (N² vs N)
# =====================================================================

# 以 H100 类 GPU 校准: 814mm², ~990 TFLOPS BF16 dense, HBM3 3.35TB/s [NV]
COMPUTE_DENSITY_TFLOPS_MM2 = 1.2
HBM_STACK_BW_TBS = 1.2                # HBM3E 每栈 >1.2TB/s [Micron/NV]
HBM_STACK_EDGE_MM = 11.0              # 每栈占 die 边缘长度
EDGE_SIDES_FOR_HBM = 2                # 2.5D 通常两侧放 HBM
# 3D folding: 表面供内存带宽密度。2μm pitch 混合键合 25 万点/mm²,
# 信号占比~25%、每信号 ~4Gb/s → ~0.03 TB/s/mm² (保守)
SURFACE_BW_TBS_MM2 = 0.03
GEMM_INTENSITY = 300.0                # FLOP/Byte, 训练 GEMM [NV roofline]
DECODE_INTENSITY = 2.0                # FLOP/Byte, 推理 decode/KV-cache

# =====================================================================
# Layer 4 — 系统层 (集群通信)
# =====================================================================

# α-β 代价模型 [Thakur]: 每消息 = o(协议/软件发起) + α(传输) + 字节/B
# o、α 校准:
#   TCP/IP 内核栈端到端数十μs; RDMA/IB 端到端 2-3μs (NIC~0.7μs+交换~0.3μs);
#   UB: 每跳~150ns [UBMesh], 超节点跨机 <1μs [CM384]
# 带宽: 400G IB = 50GB/s 单向 [NV]; NVLink4 = 450GB/s 单向 [NV];
#   UB (CloudMatrix) = 392GB/s 单向每 NPU [CM384]
FABRICS = {
    # 传统以太/TCP 类: 内核栈+多次拷贝+协议转换, 逐消息握手
    "legacy_tcp":  dict(o=25e-6, alpha_intra=0.7e-6, alpha_inter=1.0e-6,
                        bw_intra=450e9, bw_inter=12.5e9,
                        per_msg_handshake=True),
    # RDMA/IB 类: 绕过内核, 仍有 PCIe→NIC 协议转换与 WQE/门铃
    "legacy_rdma": dict(o=1.5e-6, alpha_intra=0.7e-6, alpha_inter=1.0e-6,
                        bw_intra=450e9, bw_inter=50e9,
                        per_msg_handshake=False),
    # UB 协议 (受控对比: 与 IB 同为 400G 物理线, 只换协议栈)
    "ub_protocol": dict(o=0.05e-6, alpha_intra=0.10e-6, alpha_inter=0.30e-6,
                        bw_intra=450e9, bw_inter=50e9,
                        per_msg_handshake=False),
    # UB + Hi-ONE 光互连: 协议 + 带宽扁平化 (超节点内均匀 392GB/s)
    "ub_hione":    dict(o=0.05e-6, alpha_intra=0.10e-6, alpha_inter=0.30e-6,
                        bw_intra=392e9, bw_inter=392e9,
                        per_msg_handshake=False),
}
GPUS_PER_NODE = 8

# LLM 负载（100B 级稠密模型训练 [ZeRO/Llama3]; MoE 推理 decode）
MODEL_PARAMS = 100e9
BYTES_PER_PARAM = 2                   # bf16
GLOBAL_BATCH_TOKENS = 4e6
FLOPS_PER_TOKEN = 6 * MODEL_PARAMS    # ≈6·P FLOP/token (训练)
PER_GPU_TFLOPS_EFF = 400.0            # 有效算力 (990 BF16 峰值×~40% MFU [Llama3])
MOE_LAYERS = 60
MOE_HIDDEN = 8192
MOE_TOKENS_PER_GPU_DECODE = 32        # decode 每卡在飞 token
