function fp = fault_params()
%FAULT_PARAMS  极热条件元件故障概率模型参数
%   （在文献给出的合理范围内取值，构造极热典型场景；可据实际系统替换）
%   与 verify/fault_probability.py 中 FP 字典完全一致。

% ---- 评估窗口：一次持续高温事件(持续高温日) ----
fp.t_expose_h = 24.0;

% ---- A. 变压器 (IEEE C57.91-2011 + Arrhenius-Weibull) ----
fp.xf_lambda0_yr = 0.020;   % 正常条件基准年故障率 (/yr)
fp.xf_dTO_rated  = 55.0;    % 额定负载顶层油温升 ΔθTO,R (°C)
fp.xf_dH_rated   = 25.0;    % 额定负载热点-顶油温差 ΔθH,R (°C)
fp.xf_R          = 8.0;     % 负载损耗/空载损耗之比 R
fp.xf_n          = 0.9;     % 顶油温升指数 n
fp.xf_m          = 0.8;     % 绕组温升指数 m
fp.xf_theta_ref  = 110.0;   % 参考热点温度 (°C, 65°C-rise 绝缘正常寿命点)
fp.xf_B_arr      = 15000.0; % Arrhenius 老化常数 B (IEEE C57.91-2011)
fp.xf_S_rated    = 500.0;   % 统一节点变压器额定容量 S_T^rated (MVA/MW)

% ---- B. 电源 (比例风险/Logistic 应力模型) ----
%   λ0 基准年强迫停运频次 (/yr)、aT 温度应力系数 (1/°C)、aL 出力应力系数
fp.gen_lambda0_yr = struct('coal',4.0,'gas',5.0,'hydro',2.0,'wind',6.0,'solar',5.0);
fp.gen_aT = struct('coal',0.020,'gas',0.030,'hydro',0.008,'wind',0.015,'solar',0.012);
fp.gen_aL = struct('coal',0.60,'gas',0.70,'hydro',0.30,'wind',0.40,'solar',0.50);
fp.gen_T0 = 25.0;           % 参考温度 (°C)

% ---- C. 线路 (IEEE Std 738 导线温度 + 指数应力) ----
fp.ln_lambda0_yr = 0.80;    % 正常条件基准年故障率 (/回·yr)
fp.ln_bT = 0.030;           % 导线温度应力系数 (1/°C)
fp.ln_bS = 1.50;            % 过载应力系数
fp.ln_Tc_ref = 75.0;        % 导线连续运行参考温度 (°C)
% 代表性导线 (Drake 795 kcmil 26/7 ACSR)
fp.cond_D      = 0.02814;   % 外径 (m)
fp.cond_R25    = 7.283e-5;  % 电阻 @25°C (Ω/m)
fp.cond_R75    = 8.688e-5;  % 电阻 @75°C (Ω/m)
fp.cond_emiss  = 0.5;       % 发射率 ε
fp.cond_absorp = 0.5;       % 太阳吸收率 α
fp.V_base_kV   = 345.0;     % 线电压 (kV)
% 额定电流定义天气 (基准天气下 β=1 时导线达连续运行温度 75°C)
fp.rate_Ta = 25.0; fp.rate_v = 2.0; fp.rate_G = 0.0; fp.rate_Tc = 75.0;

end
