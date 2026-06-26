function print_case39_ehnw_data(doSolve)
%PRINT_CASE39_EHNW_DATA  打印修改版 IEEE39 完整算例数据与求解基准状态
%
%   用法:
%     >> print_case39_ehnw_data()        % 先打印算例数据，再尝试求解并打印基准状态
%     >> print_case39_ehnw_data(false)    % 仅打印算例数据 + 参考基准状态（无需 Gurobi）
%
%   输出章节:
%     【1】–【8】 算例原始数据（节点/支路/机组/场景参数）
%     【9】–【13】极热场景 DC-OPF 求解后系统运行基准状态

if nargin < 1, doSolve = true; end

mpc = case39_ehnw();
sc  = weather_scenario();

sep = repmat('=', 1, 78);
fprintf('%s\n', '修改版 IEEE 39 节点完整算例数据 (case39_ehnw)');
fprintf('%s\n', sep);

%% 1. 系统概况
fprintf('\n【1】系统概况\n');
fprintf('  基准容量 baseMVA = %.0f\n', mpc.baseMVA);
fprintf('  节点数 nBus      = %d\n', mpc.nBus);
fprintf('  支路数 nBranch   = %d\n', size(mpc.branch,1));
fprintf('  机组数 nGen      = %d\n', size(mpc.gen,1));
fprintf('  负荷节点数       = %d\n', size(mpc.busPd0,1));
fprintf('  平衡节点         = bus %d\n', mpc.slackBus);
fprintf('  基准负荷合计     = %.2f MW\n', sum(mpc.busPd0(:,2)));

%% 2. 节点表（39 节点）
% type: 1=PQ负荷, 2=PV发电, 3=平衡
busType = ones(39,1);
busType([30:39]) = 2;
busType(31) = 3;
Pd0 = zeros(39,1);
for k = 1:size(mpc.busPd0,1)
    Pd0(mpc.busPd0(k,1)) = mpc.busPd0(k,2);
end

fprintf('\n【2】节点数据（39 节点）\n');
fprintf('%-5s%-6s%-12s%-12s%s\n','bus','type','Pd0(MW)','角色','备注');
typeName = {'PQ负荷','PV发电','平衡'};
for b = 1:39
    role = typeName{busType(b)};
    note = '';
    if busType(b)==2
        gidx = find(mpc.gen(:,1)==b, 1);
        if ~isempty(gidx)
            tc = mpc.gen(gidx,2);
            names = {'火电','水电','风电','光伏'};
            note = sprintf('G%d %s', gidx, names{tc});
        end
    elseif busType(b)==3
        note = 'G2 火电-燃煤(平衡机)';
    end
    fprintf('%-5d%-6d%-12.2f%-12s%s\n', b, busType(b), Pd0(b), role, note);
end

%% 3. 支路
fprintf('\n【3】支路数据（%d 条）\n', size(mpc.branch,1));
fprintf('%-5s%-5s%-10s%-10s%-8s\n','fbus','tbus','x(p.u.)','rateA(MW)','tap');
for l = 1:size(mpc.branch,1)
    br = mpc.branch(l,:);
    fprintf('%-5d%-5d%-10.4f%-10.0f%-8.3f\n', br(1), br(2), br(3), br(4), br(5));
end

%% 4. 发电机
fprintf('\n【4】发电机数据（10 台）\n');
fprintf('%-4s%-5s%-10s%-6s%-10s%-8s%-8s%-8s\n', ...
    'G','bus','类型','燃料','Prated','Pmin%','c2','c1');
fuelName = {'—','燃煤','燃气'};
typeNameG = {'火电','水电','风电','光伏'};
for g = 1:size(mpc.gen,1)
    gi = mpc.gen(g,:);
  fprintf('G%-3d%-5d%-10s%-6s%-10.0f%-8.2f%-8.4f%-8.1f\n', ...
        g, gi(1), typeNameG{gi(2)}, fuelName{gi(3)+1}, ...
        gi(4), gi(5), gi(6), gi(7));
end
fprintf('  铭牌总容量 = %.0f MW\n', sum(mpc.gen(:,4)));

%% 5. 机组运行参数
fprintf('\n【5】机组运行参数 genOps\n');
fprintf('%-4s%-10s%-10s%-10s%-10s\n','G','Pg0(MW)','ramp_up','ramp_dn','e_avail');
for g = 1:size(mpc.genOps,1)
    op = mpc.genOps(g,:);
    fprintf('G%-3d%-10.2f%-10.2f%-10.2f%-10.2f\n', g, op(1), op(2), op(3), op(4));
end

%% 6. 气象与荷侧参数
fprintf('\n【6】极热无风气象场景 weather_scenario\n');
fprintf('  dt_h=%.1f h, T_amb=%.1f C, wind=%.1f m/s, G=%.0f W/m^2\n', ...
    sc.dt_h, sc.T_amb, sc.wind_speed, sc.irradiance);
fprintf('  火电: T_ref=%.0f C, alpha_coal=%.3f, alpha_gas=%.3f\n', ...
    sc.T_ref_thermal, sc.alpha_coal, sc.alpha_gas);
fprintf('  水电: k_hydro=%.2f\n', sc.k_hydro);
fprintf('  风电: v_ci=%.0f, v_r=%.0f, v_co=%.0f m/s\n', ...
    sc.v_cut_in, sc.v_rated, sc.v_cut_out);
fprintf('  光伏: G_stc=%.0f, T_stc=%.0f, NOCT=%.0f, gamma=%.3f\n', ...
    sc.G_stc, sc.T_stc, sc.NOCT, sc.gamma_pv);
fprintf('  负荷: T_L0=%.0f C, beta=%.3f, rho_cool=%.2f\n', ...
    sc.T_L0, sc.beta_load, sc.rho_cool);
fprintf('  VOLL = [%.0f, %.0f, %.0f] $/MWh\n', sc.voll(1), sc.voll(2), sc.voll(3));

%% 7. 极热场景下源侧降容与荷侧修正
[Pmax, Pmin, typeName] = derate_sources(mpc, sc);
[lbPg, ubPg] = source_dispatch_bounds(mpc, sc, Pmax, Pmin);
[loadBus, Dtotal, Dlevel] = load_temperature(mpc, sc);

fprintf('\n【7】极热场景(T=%.0fC) 源侧降容与调度区间\n', sc.T_amb);
fprintf('%-4s%-10s%-8s%-8s%-8s%-8s%-8s\n','G','类型','Pmax','Pmin','lb','ub','备注');
for g = 1:size(mpc.gen,1)
    fprintf('G%-3d%-10s%-8.1f%-8.1f%-8.1f%-8.1f\n', ...
        g, typeName{g}, Pmax(g), Pmin(g), lbPg(g), ubPg(g));
end

fprintf('\n【8】极热场景 荷侧温度修正需求 (MW)\n');
fprintf('%-5s%-10s%-10s%-10s%-10s%-10s\n','bus','Pd0','D(T)','一级','二级','三级');
for k = 1:numel(loadBus)
    b = loadBus(k);
    pd0 = mpc.busPd0(mpc.busPd0(:,1)==b, 2);
    fprintf('%-5d%-10.2f%-10.2f%-10.2f%-10.2f%-10.2f\n', ...
        b, pd0, Dtotal(k), Dlevel(k,1), Dlevel(k,2), Dlevel(k,3));
end
fprintf('  合计: Pd0=%.2f, D(T)=%.2f MW\n', sum(mpc.busPd0(:,2)), sum(Dtotal));

%% 9–13 求解后系统运行基准状态
if doSolve
    try
        fprintf('\n>> 正在调用 Gurobi 求解 DC-OPF ...\n');
        res = run_extreme_heat_opf('verbose', false);
        fprintf('>> 求解成功，以下为实时最优解。\n');
    catch ME
        fprintf('\n>> Gurobi 求解不可用 (%s)，使用 baseline_state_ref 参考数据。\n', ME.message);
        ref = baseline_state_ref();
        res = ref_to_res(ref, mpc, sc);
    end
else
    ref = baseline_state_ref();
    res = ref_to_res(ref, mpc, sc);
    fprintf('\n>> 使用 baseline_state_ref 参考基准状态（与 Gurobi/Python 一致）。\n');
end
print_baseline_state(res, mpc, sc);

fprintf('\n%s\n', sep);
fprintf('数据文件: matlab/case39_ehnw.m, matlab/weather_scenario.m\n');
fprintf('运行优化: res = run_extreme_heat_opf();\n');
fprintf('完整表格: docs/03_IEEE39修改版完整算例数据.md 第 11 节\n');
fprintf('%s\n', sep);

end
