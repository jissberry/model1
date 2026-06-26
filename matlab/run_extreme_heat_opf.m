function res = run_extreme_heat_opf()
%RUN_EXTREME_HEAT_OPF  极热无风场景源-荷失衡最优调度 主程序（MATLAB + Gurobi）
%
%   流程:
%     第一步-A  derate_sources    : 四类机组高温降容最大出力与出力区间
%     第一步-B  load_temperature  : 荷侧温度响应需求与一/二/三级拆分
%     第二步    build_and_solve_dcopf : 构建 DC-OPF 并调用 Gurobi 求解
%
%   运行前请确保 Gurobi 的 MATLAB 接口已安装（matlab/gurobi 在搜索路径中）。
%   用法:  >> res = run_extreme_heat_opf();

mpc = case39_ehnw();
sc  = weather_scenario();

% 第一步：源/荷失衡模型
[Pmax, Pmin, typeName]      = derate_sources(mpc, sc);
[lbPg, ubPg]                = source_dispatch_bounds(mpc, sc, Pmax, Pmin);
[loadBus, Dtotal, Dlevel]   = load_temperature(mpc, sc);

% 第二步：构建并求解最优潮流调度
res = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbPg, ubPg, loadBus, Dtotal, Dlevel);
res.typeName = typeName;

% 打印报告
print_report(mpc, sc, res);

end


function print_report(mpc, sc, res)
sep = repmat('=', 1, 74);
fprintf('%s\n', sep);
fprintf('极热无风场景 直流最优潮流（DC-OPF）求解结果  [MATLAB + Gurobi]\n');
fprintf('%s\n', sep);
fprintf('求解状态        : %s\n', res.status);
fprintf('目标函数最优值  : %.2f  ($/h)\n', res.obj);
fprintf('  发电成本      : %.2f  ($/h)\n', res.gen_cost);
fprintf('  切负荷惩罚成本: %.2f  ($/h)\n', res.shed_cost);
fprintf('%s\n', repmat('-',1,74));

ng = size(mpc.gen,1);
fprintf('源侧机组出力 (MW):\n');
fprintf('%-6s%-5s%-10s%9s%10s%10s%10s%10s%8s\n', ...
    '机组','母线','类型','额定','Pmin','调度下界','调度上界','出力Pg','利用率');
totPg = 0;
for g = 1:ng
    prated = mpc.gen(g,4);
    util = 0; if prated>0, util = res.Pg(g)/prated*100; end
    fprintf('G%-5d%-5d%-10s%9.0f%10.1f%10.1f%10.1f%10.1f%7.1f%%\n', ...
        g, mpc.gen(g,1), res.typeName{g}, prated, res.Pmin(g), ...
        res.lbPg(g), res.ubPg(g), res.Pg(g), util);
    totPg = totPg + res.Pg(g);
end
fprintf('合计  可用上限=%.1f  总发电=%.1f MW\n', sum(res.Pmax), totPg);
fprintf('%s\n', repmat('-',1,74));

totD   = sum(res.Dtotal);
totSh  = sum(res.shed(:));
fprintf('荷侧切负荷 (MW):\n');
fprintf('  极热修正后总需求 : %.1f\n', totD);
fprintf('  总切负荷         : %.1f  (%.2f%%)\n', totSh, totSh/totD*100);
for k = 1:numel(sc.level_frac)
    fprintf('    %-12s VOLL=%7.0f  切除=%8.1f MW\n', ...
        sc.level_name{k}, sc.voll(k), sum(res.shed(:,k)));
end
fprintf('%s\n', repmat('-',1,74));

fprintf('系统功率平衡校验 (MW):\n');
fprintf('  总发电 %.1f =?= 净需求 %.1f  (残差 %+.3f)\n', ...
    totPg, totD-totSh, totPg-(totD-totSh));

% 线路负载率
nbr = numel(res.bser);
maxpct = 0; nover = 0;
for l = 1:nbr
    f = mpc.baseMVA*res.bser(l)*(res.theta(res.fb(l))-res.theta(res.tb(l)));
    pct = abs(f)/res.rateA(l)*100;
    if pct>maxpct, maxpct=pct; end
    if pct>100+1e-6, nover=nover+1; end
end
fprintf('  线路最大负载率 %.1f%%，越限线路数 %d\n', maxpct, nover);
fprintf('%s\n', sep);
end
