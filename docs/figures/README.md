# 论文插图说明

全部插图由 `scripts/make_paper_figures.py` 基于 `verify/` 下的实际计算结果生成，
分辨率 300 dpi，可直接用于论文排版。

重新生成：

```bash
cd /workspace
python3 scripts/make_paper_figures.py
```

## 数据来源

| 图 | 数据文件 |
|---|---|
| 图 1 | 无（框架示意） |
| 图 2 | `verify/models.py`、`verify/case_data.py` 实时计算 |
| 图 3、图 4 | `verify/baseline_state.json` |
| 图 5 | `verify/fault_probability.json` |
| 图 6 | `verify/fault_scenarios_2000.csv`、`fault_scenarios_2000_meta.json` |
| 图 7、图 8 | `verify/fault_scenario_opf_stats.json`、`fault_scenario_opf_summary.csv` |

## 图目录

| 文件 | 图题 | 内容 |
|---|---|---|
| `fig1_framework.png` | 极热无风源荷失衡与热故障耦合风险评估框架 | 七个步骤的方法流程 |
| `fig2_source_load_imbalance.png` | 极热无风条件下的源侧降容与荷侧需求增长 | (a) 四类机组降容特性；(b) 风速-功率曲线；(c) 荷侧温敏增长与源荷缺口 |
| `fig3_baseline_dispatch.png` | 极热无风基准 OPF 调度结果 | (a) 机组出力与调度区间；(b) 分类型容量-出力对比 |
| `fig4_load_shedding.png` | 基准 OPF 的分级切负荷结果 | (a) 各负荷节点需求与切负荷构成；(b) 分级需求与切负荷 |
| `fig5_fault_probability.png` | 极热条件下三类元件的热故障概率 | (a) 发电机；(b) 线路负载率-导线温度-故障概率；(c) 三类元件对比 |
| `fig6_monte_carlo.png` | 蒙特卡洛故障场景抽样结果 | (a) 故障元件数分布；(b) 各类元件故障事件数；(c) 抽样一致性校验 |
| `fig7_shedding_distribution.png` | 2000 个热故障场景的切负荷分布 | (a) 频数分布；(b) 经验累积分布；(c) 分位数切负荷构成 |
| `fig8_risk_drivers.png` | 切负荷风险的主导因素分析 | (a) 发电机故障数影响；(b) 网络故障与火电停机耦合；(c) 不同故障组合对比 |

## 建议插入位置

| 章节 | 图 |
|---|---|
| I. 引言 / II. 建模 开头 | 图 1 |
| II. 极热无风条件下的源荷失衡建模 | 图 2 |
| VI-B 基准 OPF 结果 | 图 3、图 4 |
| VI-C 故障概率与蒙特卡洛场景 | 图 5、图 6 |
| VI-D 故障后 OPF 遍历结果 | 图 7、图 8 |

## 优化版预览（尚未替换正式图）

预览图位于 `docs/figures/preview/`，仅供审阅，**不会自动覆盖**上级目录中的 `fig1`–`fig8`。

**先看总览：**

| 文件 | 说明 |
|---|---|
| `preview/contact_optimized.png` | 图 1–8 优化版拼图 |
| `preview/contact_new_candidates.png` | 3 张新增候选图拼图 |

**单张预览：**

| 文件 | 对应 |
|---|---|
| `preview_01_framework_v2.png` … `preview_08_risk_drivers_v2.png` | 现有图 1–8 优化版 |
| `preview_09_new_risk_consequence.png` | 新增候选 A：元件概率—后果风险矩阵 |
| `preview_10_new_bus_exposure.png` | 新增候选 B：负荷节点失电暴露度 |
| `preview_11_new_exceedance.png` | 新增候选 C：新增切负荷超越概率曲线 |
