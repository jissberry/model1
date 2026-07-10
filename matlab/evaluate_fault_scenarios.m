function stats = evaluate_fault_scenarios(scenarioCsv, outSummaryCsv, outBusShedCsv)
%EVALUATE_FAULT_SCENARIOS  遍历蒙特卡洛故障场景并求解故障后 DC-OPF
%
%   用法:
%     >> stats = evaluate_fault_scenarios()
%     >> stats = evaluate_fault_scenarios('../verify/fault_scenarios_2000.csv')
%
%   输入场景向量顺序固定为 [G1..G10, L1..L46, T1..T29]，0=故障，1=良好。
%   处理规则:
%     1) 发电机故障：该机组 Pg 上下界均置为 0；
%     2) 线路故障：该支路退出 DC 网络，结果潮流记为 0；
%     3) 节点变压器故障：该非电源节点相连支路全部退出。若该节点有负荷，
%        节点功率平衡会使其负荷在 OPF 中被切除。

thisDir = fileparts(mfilename('fullpath'));
repoRoot = fileparts(thisDir);
verifyDir = fullfile(repoRoot, 'verify');

if nargin < 1 || isempty(scenarioCsv)
    scenarioCsv = fullfile(verifyDir, 'fault_scenarios_2000.csv');
end
if nargin < 2 || isempty(outSummaryCsv)
    outSummaryCsv = fullfile(verifyDir, 'fault_scenario_opf_summary_matlab.csv');
end
if nargin < 3 || isempty(outBusShedCsv)
    outBusShedCsv = fullfile(verifyDir, 'fault_scenario_bus_shed_matlab.csv');
end

if exist(scenarioCsv, 'file') ~= 2
    fp = fault_probability();
    monte_carlo_fault_scenarios(fp, 2000, 20260627, scenarioCsv);
end

tbl = readtable(scenarioCsv);
scenarioId = tbl{:,1};
states = tbl{:,2:end};
if size(states, 2) ~= 85
    error('evaluate_fault_scenarios:DimensionMismatch', ...
        '期望场景矩阵为 n x 85，当前为 %d 列。', size(states, 2));
end

mpc = case39_ehnw();
sc = weather_scenario();
[Pmax, Pmin] = derate_sources(mpc, sc);
[lbPg, ubPg] = source_dispatch_bounds(mpc, sc, Pmax, Pmin);
[loadBus, Dtotal, Dlevel] = load_temperature(mpc, sc);

ng = size(mpc.gen, 1);
nbr = size(mpc.branch, 1);
nScen = size(states, 1);
xfBus = setdiff((1:mpc.nBus)', mpc.gen(:,1));
if numel(xfBus) ~= 29
    error('evaluate_fault_scenarios:TransformerCount', ...
        '期望 29 个非电源节点变压器，当前为 %d。', numel(xfBus));
end

baseline = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbPg, ubPg, loadBus, Dtotal, Dlevel);
baselineShed = sum(baseline.shed(:));

status = cell(nScen, 1);
objective = NaN(nScen, 1);
genCost = NaN(nScen, 1);
shedCost = NaN(nScen, 1);
totalDemand = repmat(sum(Dtotal), nScen, 1);
servedLoad = NaN(nScen, 1);
totalShed = NaN(nScen, 1);
shedPct = NaN(nScen, 1);
shedLevel = NaN(nScen, numel(sc.level_frac));
nGenFault = zeros(nScen, 1);
nLineFaultDirect = zeros(nScen, 1);
nTransformerFault = zeros(nScen, 1);
nBranchOutageTotal = zeros(nScen, 1);
nBranchOutageByTransformer = zeros(nScen, 1);
failedGenerators = cell(nScen, 1);
failedLinesDirect = cell(nScen, 1);
failedTransformers = cell(nScen, 1);
failedTransformerBuses = cell(nScen, 1);
outagedBranchesTotal = cell(nScen, 1);
busShed = NaN(nScen, numel(loadBus));

for s = 1:nScen
    state = states(s, :);
    genAvailable = logical(state(1:ng))';
    directBranchAvailable = logical(state(ng+1:ng+nbr))';
    xfAvailable = logical(state(ng+nbr+1:end))';

    failedXfBus = xfBus(~xfAvailable);
    branchAvailable = directBranchAvailable;
    forcedByXf = false(nbr, 1);
    for l = 1:nbr
        if ismember(mpc.branch(l,1), failedXfBus) || ismember(mpc.branch(l,2), failedXfBus)
            forcedByXf(l) = branchAvailable(l);
            branchAvailable(l) = false;
        end
    end

    res = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbPg, ubPg, ...
        loadBus, Dtotal, Dlevel, genAvailable, branchAvailable);
    status{s} = res.status;

    genFaultIdx = find(~genAvailable);
    lineFaultIdx = find(~directBranchAvailable);
    xfFaultIdx = find(~xfAvailable);
    branchOutageIdx = find(~branchAvailable);

    nGenFault(s) = numel(genFaultIdx);
    nLineFaultDirect(s) = numel(lineFaultIdx);
    nTransformerFault(s) = numel(xfFaultIdx);
    nBranchOutageTotal(s) = numel(branchOutageIdx);
    nBranchOutageByTransformer(s) = nnz(forcedByXf);
    failedGenerators{s} = label_list('G', genFaultIdx);
    failedLinesDirect{s} = label_list('L', lineFaultIdx);
    failedTransformers{s} = label_list('T', xfFaultIdx);
    failedTransformerBuses{s} = number_list(failedXfBus);
    outagedBranchesTotal{s} = label_list('L', branchOutageIdx);

    if strcmpi(res.status, 'OPTIMAL')
        objective(s) = res.obj;
        genCost(s) = res.gen_cost;
        shedCost(s) = res.shed_cost;
        shedLevel(s, :) = sum(res.shed, 1);
        totalShed(s) = sum(res.shed(:));
        servedLoad(s) = totalDemand(s) - totalShed(s);
        shedPct(s) = totalShed(s) / totalDemand(s) * 100;
        busShed(s, :) = sum(res.shed, 2)';
    end

    if s == 1 || mod(s, 100) == 0 || s == nScen
        fprintf('已求解 %d/%d 个故障场景。\n', s, nScen);
    end
end

summary = table(scenarioId, status, objective, genCost, shedCost, totalDemand, ...
    servedLoad, totalShed, shedPct, shedLevel(:,1), shedLevel(:,2), shedLevel(:,3), ...
    nGenFault, nLineFaultDirect, nTransformerFault, nBranchOutageTotal, ...
    nBranchOutageByTransformer, failedGenerators, failedLinesDirect, ...
    failedTransformers, failedTransformerBuses, outagedBranchesTotal, ...
    'VariableNames', {'scenario','status','objective','gen_cost','shed_cost', ...
    'total_demand_MW','served_load_MW','total_shed_MW','shed_pct', ...
    'shed_level1_MW','shed_level2_MW','shed_level3_MW','n_gen_fault', ...
    'n_line_fault_direct','n_transformer_fault','n_branch_outage_total', ...
    'n_branch_outage_by_transformer','failed_generators','failed_lines_direct', ...
    'failed_transformers','failed_transformer_buses','outaged_branches_total'});
writetable(summary, outSummaryCsv);

busTbl = table(scenarioId, status, 'VariableNames', {'scenario','status'});
for i = 1:numel(loadBus)
    busTbl.(sprintf('bus_%d_shed_MW', loadBus(i))) = busShed(:, i);
end
writetable(busTbl, outBusShedCsv);

ok = strcmpi(status, 'OPTIMAL');
stats = struct();
stats.n_scenarios = nScen;
stats.n_optimal = nnz(ok);
stats.n_infeasible_or_other = nScen - nnz(ok);
stats.baseline_total_shed_MW = baselineShed;
stats.total_shed_MW = describe_distribution(totalShed(ok));
stats.incremental_shed_vs_baseline_MW = describe_distribution(totalShed(ok) - baselineShed);
stats.level1_shed_fraction = mean(shedLevel(ok,1) > 1e-5);
stats.level2_shed_fraction = mean(shedLevel(ok,2) > 1e-5);
stats.any_incremental_shed_fraction = mean((totalShed(ok) - baselineShed) > 1e-5);
stats.summary_csv = outSummaryCsv;
stats.bus_shed_csv = outBusShedCsv;

fprintf('结果已写入:\n  %s\n  %s\n', outSummaryCsv, outBusShedCsv);
fprintf('可解场景 %d/%d；平均切负荷 %.3f MW；95%%分位 %.3f MW。\n', ...
    stats.n_optimal, nScen, stats.total_shed_MW.mean, stats.total_shed_MW.p95);
end


function s = label_list(prefix, idx)
if isempty(idx)
    s = '';
    return;
end
parts = cell(1, numel(idx));
for i = 1:numel(idx)
    parts{i} = sprintf('%s%d', prefix, idx(i));
end
s = strjoin(parts, ';');
end


function s = number_list(values)
if isempty(values)
    s = '';
    return;
end
parts = cell(1, numel(values));
for i = 1:numel(values)
    parts{i} = sprintf('%d', values(i));
end
s = strjoin(parts, ';');
end


function d = describe_distribution(x)
x = x(isfinite(x));
if isempty(x)
    d = struct();
    return;
end
d.count = numel(x);
d.min = min(x);
d.mean = mean(x);
d.std = std(x, 1);
d.p05 = percentile_value(x, 5);
d.p25 = percentile_value(x, 25);
d.median = percentile_value(x, 50);
d.p75 = percentile_value(x, 75);
d.p90 = percentile_value(x, 90);
d.p95 = percentile_value(x, 95);
d.p99 = percentile_value(x, 99);
d.max = max(x);
end


function y = percentile_value(x, p)
x = sort(x(:));
if numel(x) == 1
    y = x;
    return;
end
pos = 1 + (numel(x)-1) * p/100;
lo = floor(pos); hi = ceil(pos);
if lo == hi
    y = x(lo);
else
    y = x(lo) + (x(hi)-x(lo)) * (pos-lo);
end
end
