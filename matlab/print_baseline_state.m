function print_baseline_state(res, mpc, sc)
%PRINT_BASELINE_STATE  打印极热场景 DC-OPF 求解后完整系统运行基准状态
%
%   输出：汇总、发电机出力、39 节点状态、负荷/切负荷、46 条支路/变压器潮流。
%   res 来自 run_extreme_heat_opf 或 baseline_state_ref 转换结果。

if isfield(res, 'summary')
    sm = res.summary;
else
    sm.status = res.status;
    sm.obj_total = res.obj;
    sm.gen_cost = res.gen_cost;
    sm.shed_cost = res.shed_cost;
    sm.total_Pg_MW = sum(res.Pg);
    sm.total_D_MW = sum(res.Dtotal);
    sm.total_shed_MW = sum(res.shed(:));
    sm.total_served_MW = sm.total_D_MW - sm.total_shed_MW;
    if isfield(res, 'branch_loading')
        sm.max_branch_loading_pct = max(res.branch_loading);
        sm.n_overloaded = sum(res.branch_loading > 100 + 1e-6);
    else
        sm.max_branch_loading_pct = NaN;
        sm.n_overloaded = NaN;
    end
end

sep = repmat('=', 1, 78);
fprintf('\n%s\n', sep);
fprintf('【9】极热场景求解后系统运行基准状态 (DC-OPF 最优解)\n');
fprintf('%s\n', sep);
fprintf('  求解状态           : %s\n', sm.status);
fprintf('  目标函数最优值     : %.2f ($/h)\n', sm.obj_total);
fprintf('  发电成本           : %.2f ($/h)\n', sm.gen_cost);
fprintf('  切负荷惩罚成本     : %.2f ($/h)\n', sm.shed_cost);
fprintf('  总发电 sum(Pg)     : %.2f MW\n', sm.total_Pg_MW);
fprintf('  极热修正总需求     : %.2f MW\n', sm.total_D_MW);
fprintf('  总切负荷           : %.2f MW (%.2f%%)\n', sm.total_shed_MW, ...
    sm.total_shed_MW/sm.total_D_MW*100);
fprintf('  实际供电负荷       : %.2f MW\n', sm.total_served_MW);
fprintf('  线路最大负载率     : %.2f%%\n', sm.max_branch_loading_pct);
fprintf('  越限线路数         : %d\n', sm.n_overloaded);

%% 发电机
fprintf('\n【10】发电机出力 (MW)\n');
fprintf('%-4s%-5s%-12s%10s%10s%10s%8s\n','G','bus','类型','Pg','lb','ub','利用率');
ng = numel(res.Pg);
for g = 1:ng
    bus = mpc.gen(g,1);
    tc = mpc.gen(g,2);
    names = {'火电','水电','风电','光伏'};
    fuel = {'','-燃煤','-燃气',''};
    if tc == 1
        if mpc.gen(g,3)==2, fn = '-燃气'; else, fn = '-燃煤'; end
    else
        fn = '';
    end
    prated = mpc.gen(g,4);
    util = 0; if prated>0, util = res.Pg(g)/prated*100; end
    if isfield(res,'lbPg'), lb = res.lbPg(g); else, lb = res.Pmin(g); end
    if isfield(res,'ubPg'), ub = res.ubPg(g); else, ub = res.Pmax(g); end
    fprintf('G%-3d%-5d%-12s%10.2f%10.1f%10.1f%7.1f%%\n', ...
        g, bus, [names{tc} fn], res.Pg(g), lb, ub, util);
end

%% 节点状态
fprintf('\n【11】节点运行状态 (39 节点)\n');
fprintf('%-5s%10s%10s%10s%10s%10s%10s\n','bus','theta(deg)','Pg','D(T)','shed','served','P_inj');
if isfield(res.theta_deg')
    theta_deg = res.theta_deg(:);
else
    theta_deg = res.theta(:) * 180/pi;
end
loadBus = res.loadBus(:);
shed = res.shed;
if size(shed,1) ~= numel(loadBus)
    shed = shed';  % ensure nL x 3
end
lbMap = containers.Map(loadBus, 1:numel(loadBus));
Pd0v = zeros(39,1);
for k = 1:size(mpc.busPd0,1)
    Pd0v(mpc.busPd0(k,1)) = mpc.busPd0(k,2);
end
for b = 1:39
    pg = 0;
    gidx = find(mpc.gen(:,1)==b);
    if ~isempty(gidx), pg = sum(res.Pg(gidx)); end
    d = 0; sh = 0; served = 0;
    if isKey(lbMap, b)
        k = lbMap(b);
        d = res.Dtotal(k);
        sh = sum(shed(k,:));
        served = d - sh;
    end
    fprintf('%-5d%10.3f%10.2f%10.2f%10.2f%10.2f%10.2f\n', ...
        b, theta_deg(b), pg, d, sh, served, pg - served);
end

%% 负荷切负荷
fprintf('\n【12】负荷与切负荷明细 (21 节点)\n');
fprintf('%-5s%10s%10s%10s%10s%10s%10s%10s\n', ...
    'bus','Pd0','D(T)','shed_L1','shed_L2','shed_L3','shed','served');
for k = 1:numel(loadBus)
    b = loadBus(k);
    pd0 = Pd0v(b);
    d = res.Dtotal(k);
    s1 = shed(k,1); s2 = shed(k,2); s3 = shed(k,3);
    fprintf('%-5d%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f\n', ...
        b, pd0, d, s1, s2, s3, s1+s2+s3, d-(s1+s2+s3));
end

%% 支路/变压器潮流
fprintf('\n【13】支路/变压器潮流 (46 条)\n');
fprintf('%-4s%-5s%-5s%-6s%-6s%12s%10s%10s%s\n', ...
    'L','fbus','tbus','类型','tap','flow(MW)','rateA','load%%','方向');
nbr = size(mpc.branch,1);
for l = 1:nbr
    f = mpc.branch(l,1); t = mpc.branch(l,2);
    tap = mpc.branch(l,5);
    if tap == 0
        typ = '线路'; tapShow = 1.0;
    else
        typ = '变压器'; tapShow = tap;
    end
    flow = res.branch_flow(l);
    rateA = mpc.branch(l,4);
    pct = abs(flow)/rateA*100;
    if flow >= 0
        dir = sprintf('%d->%d', f, t);
    else
        dir = sprintf('%d->%d', t, f);
    end
    fprintf('L%-3d%-5d%-5d%-6s%-6.3f%12.2f%10.0f%9.2f%% %s\n', ...
        l, f, t, typ, tapShow, flow, rateA, pct, dir);
end

fprintf('\n%s\n', sep);

end
