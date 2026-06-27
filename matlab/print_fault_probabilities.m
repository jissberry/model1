function fp_res = print_fault_probabilities(fp_res)
%PRINT_FAULT_PROBABILITIES  打印极热条件三类元件故障概率报告
%
%   用法:
%     >> print_fault_probabilities()           % 自动计算并打印
%     >> print_fault_probabilities(fp_res)     % 打印指定结果结构体
%
%   fp_res 由 fault_probability() 返回。

if nargin == 0
    mpc = case39_ehnw();
    sc  = weather_scenario();
    try
        fprintf('>> 正在调用 Gurobi 求解 DC-OPF 获取基准状态 ...\n');
        res = run_extreme_heat_opf('verbose', false);
        fprintf('>> 求解成功，正在计算故障概率 ...\n');
    catch ME
        fprintf('>> Gurobi 不可用 (%s)，使用 baseline_state_ref。\n', ME.message);
        ref = baseline_state_ref();
        res = ref_to_res(ref, mpc, sc);
    end
    fp_res = fault_probability(res, mpc, sc, false);
elseif nargin < 1
    error('print_fault_probabilities:InvalidInput', ...
        '用法: print_fault_probabilities() 或 print_fault_probabilities(fp_res)');
end

sc = fp_res.scenario;
sep = repmat('=', 1, 90);
fprintf('\n%s\n', sep);
fprintf('极热条件元件故障概率 (T=%.0f°C, v=%.0f m/s, G=%.0f W/m², 评估窗口=%.0f h)\n', ...
    sc.T_amb, sc.wind, sc.irradiance, sc.t_expose_h);
fprintf('统一节点变压器额定容量 S_T^{rated} = %.0f MW（共 %d 台，非电源节点各一台）\n', ...
    sc.xf_S_rated, sc.n_transformers);
fprintf('代表性导线额定电流 I_R = %.1f A\n', sc.I_rated_A);

%% A. 变压器
fprintf('%s\n', sep);
fprintf('【A】节点变压器故障概率 (IEEE C57.91 热点 + Arrhenius-Weibull)\n');
fprintf('%-4s%-5s%10s%8s%10s%10s%12s%12s\n', ...
    'Tx','bus','P(MW)','K','thetaH','FAA','lambda/yr','Pf');
xf = fp_res.transformers;
for i = 1:numel(xf)
    d = xf(i);
    fprintf('T%-3d%-5d%10.2f%8.3f%10.1f%10.3f%12.4f%12.3e\n', ...
        d.Tx, d.bus, d.P_MW, d.K, d.thetaH, d.FAA, d.lambda_yr, d.Pf);
end

%% B. 电源
fprintf('%s\n', sep);
fprintf('【B】电源故障概率 (比例风险应力模型)\n');
fprintf('%-4s%-5s%-12s%10s%8s%8s%12s%12s\n', ...
    'G','bus','类型','Pg','ell','Teff','lambda/yr','Pf');
gen = fp_res.generators;
for i = 1:numel(gen)
    d = gen(i);
    fprintf('G%-3d%-5d%-12s%10.2f%8.3f%8.1f%12.4f%12.3e\n', ...
        d.G, d.bus, d.type, d.Pg, d.ell, d.Teff, d.lambda_yr, d.Pf);
end

%% C. 线路
fprintf('%s\n', sep);
fprintf('【C】线路故障概率 (IEEE 738 导线温度 + 指数应力)\n');
fprintf('%-4s%-5s%-5s%10s%8s%10s%8s%12s%12s\n', ...
    'L','fb','tb','flow','beta','I(A)','Tc','lambda/yr','Pf');
ln = fp_res.lines;
for i = 1:numel(ln)
    d = ln(i);
    fprintf('L%-3d%-5d%-5d%10.2f%8.3f%10.1f%8.1f%12.4f%12.3e\n', ...
        d.L, d.fbus, d.tbus, d.flow, d.beta, d.I, d.Tc, d.lambda_yr, d.Pf);
end
fprintf('%s\n', sep);

end
