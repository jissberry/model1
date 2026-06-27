# 极热无风气象条件下源-荷供需失衡建模与最优调度

本项目针对**极热无风（Extreme-Heat / No-Wind）复合极端气象事件**，建立电力系统"源-荷"
供需失衡模型，并基于**修改版 IEEE 39 节点算例**构建以"最小化切负荷惩罚 + 发电成本"为目标的
**直流最优潮流（DC-OPF）优化调度模型**，用 **MATLAB + Gurobi** 求解极热场景下系统运行的基准状态。

## 内容结构

```
docs/                       数学模型文档（中文）
  01_源荷失衡模型.md          第一步：源侧四类机组降容公式 + 荷侧负荷分类与温度响应
  02_最优潮流调度模型.md       第二步：DC-OPF 优化调度模型（目标/约束/Gurobi 标准型/结果）
  03_IEEE39修改版完整算例数据.md  修改版 IEEE39 完整节点/支路/机组/负荷数据 + MATLAB 用法
  04_极热条件元件故障概率模型.md  第四步：变压器/电源/线路故障概率模型 + 文献 + 算例概率
  word/                     Word 格式导出（01/02/03 三份文档）

matlab/                     MATLAB + Gurobi 主实现
  case39_ehnw.m             修改版 IEEE39 算例数据（四类机组 + 各类负荷）
  weather_scenario.m        极热无风气象场景参数
  print_case39_ehnw_data.m  打印完整算例数据（对照 docs/03）
  derate_sources.m          第一步-A：四类机组最大出力(降容)与出力区间
  load_temperature.m        第一步-B：荷侧温度响应需求与一/二/三级拆分
  build_and_solve_dcopf.m   第二步：构建并用 Gurobi 求解 DC-OPF
  run_extreme_heat_opf.m    主程序入口（含结果报告）
  fault_probability.m       第四步：节点变压器/电源/线路故障概率（主程序）
  node_xf_power.m           非电源节点变压器通过功率 P_served
  conductor_temperature.m   IEEE Std 738 稳态热平衡求解导线温度
  fault_params.m            故障概率模型参数
  print_fault_probabilities.m  打印三类元件故障概率报告

verify/                     开源求解器验证（无需 MATLAB/Gurobi）
  case_data.py              与 MATLAB 完全一致的算例数据
  models.py                 源侧降容 / 荷侧温度模型
  verify_dcopf.py           cvxpy 复现 DC-OPF（参考实现）
  verify_matrix_form.py     逐元素复现 Gurobi 标准型矩阵装配并对比
  fault_probability.py      第四步故障概率模型（Python 验证，与 MATLAB 一致）
```

## 运行

### MATLAB + Gurobi（主实现）

需安装 [Gurobi](https://www.gurobi.com/) 及其 MATLAB 接口（`gurobi.m` 在搜索路径中）。

```matlab
cd matlab
res = run_extreme_heat_opf();
```

将打印源侧出力、荷侧切负荷、功率平衡与线路负载率报告。

### Python 开源验证（无 MATLAB/Gurobi 时）

```bash
pip install numpy scipy cvxpy
cd verify
python3 verify_dcopf.py          # 复现 DC-OPF 并输出结果报告
python3 verify_matrix_form.py    # 校验 MATLAB Gurobi 矩阵装配正确性
```

## 核心结果（$T=40℃$，$v=2\,\text{m/s}$，$G=900\,\text{W/m}^2$）

| 指标 | 数值 |
|---|---|
| 目标函数最优值 | 1 011 492.5 $/h |
| 发电成本 | 248 686.6 $/h |
| 切负荷惩罚成本 | 762 805.9 $/h |
| 极热修正后总需求 | 6 754.6 MW |
| 可用发电上限 | 6 008.4 MW |
| 总切负荷 | 762.8 MW（11.29%，全部为三级可中断负荷）|

极热无风下：风电几乎全失、光伏降容至约 75%、水电枯水至 85%、火电高温降容 2.5%~4.5%，
叠加空调负荷激增，系统出现约 763 MW 硬缺口；最优调度在保障一/二级关键负荷的前提下，
仅切除惩罚最低的三级可中断负荷，实现经济-安全最优。

详见 `docs/` 下的两份模型文档。
