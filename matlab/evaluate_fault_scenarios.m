function stats = evaluate_fault_scenarios(scenarioCsv, outSummaryCsv)
%EVALUATE_FAULT_SCENARIOS  遍历热故障场景并求解故障后 DC-OPF/MIQP
%
%   基准源-荷失衡OPF: 不施加爬坡约束（未知上一时刻出力）；
%   故障后OPF: 施加爬坡约束，爬坡基准为基准OPF得到的各机组出力；
%   火电: 通过u_i启停变量处理孤岛最小出力过剩；水电无启停变量。

thisDir = fileparts(mfilename('fullpath'));
repoRoot = fileparts(thisDir);
verifyDir = fullfile(repoRoot, 'verify');

if nargin < 1 || isempty(scenarioCsv)
    scenarioCsv = fullfile(verifyDir, 'fault_scenarios_2000.csv');
end
if nargin < 2 || isempty(outSummaryCsv)
    outSummaryCsv = fullfile(verifyDir, 'fault_scenario_opf_summary_matlab.csv');
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
[loadBus, Dtotal, Dlevel] = load_temperature(mpc, sc);

% 1) 基准源-荷失衡OPF：忽略爬坡
[lb0, ub0] = source_dispatch_bounds(mpc, sc, Pmax, Pmin, 'useRamp', false);
baseline = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lb0, ub0, loadBus, Dtotal, Dlevel);
baselinePg = baseline.Pg;
baselineShed = sum(baseline.shed(:));

% 2) 故障后OPF：以基准Pg作为爬坡基准
[lbFault, ubFault] = source_dispatch_bounds(mpc, sc, Pmax, Pmin, ...
    'useRamp', true, 'Pg0Override', baselinePg);

ng = size(mpc.gen, 1);
nbr = size(mpc.branch, 1);
nScen = size(states, 1);
xfBus = setdiff((1:mpc.nBus)', mpc.gen(:,1));

status = cell(nScen, 1);
objective = NaN(nScen, 1);
totalShed = NaN(nScen, 1);
shedPct = NaN(nScen, 1);
nGenFault = zeros(nScen, 1);
nLineFaultDirect = zeros(nScen, 1);
nTransformerFault = zeros(nScen, 1);
nBranchOutageTotal = zeros(nScen, 1);
nThermalOff = zeros(nScen, 1);

for s = 1:nScen
    state = states(s, :);
    genAvailable = logical(state(1:ng))';
    directBranchAvailable = logical(state(ng+1:ng+nbr))';
    xfAvailable = logical(state(ng+nbr+1:end))';

    failedXfBus = xfBus(~xfAvailable);
    branchAvailable = directBranchAvailable;
    for l = 1:nbr
        if ismember(mpc.branch(l,1), failedXfBus) || ismember(mpc.branch(l,2), failedXfBus)
            branchAvailable(l) = false;
        end
    end

    res = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbFault, ubFault, ...
        loadBus, Dtotal, Dlevel, genAvailable, branchAvailable);
    status{s} = res.status;
    nGenFault(s) = nnz(~genAvailable);
    nLineFaultDirect(s) = nnz(~directBranchAvailable);
    nTransformerFault(s) = nnz(~xfAvailable);
    nBranchOutageTotal(s) = nnz(~branchAvailable);
    if isfield(res, 'unit_on')
        nThermalOff(s) = nnz(mpc.gen(:,2) == 1 & res.unit_on(:) < 0.5);
    end

    if strcmpi(res.status, 'OPTIMAL')
        objective(s) = res.obj;
        totalShed(s) = sum(res.shed(:));
        shedPct(s) = totalShed(s) / sum(Dtotal) * 100;
    end

    if s == 1 || mod(s, 100) == 0 || s == nScen
        fprintf('已求解 %d/%d 个故障场景。\n', s, nScen);
    end
end

summary = table(scenarioId, status, objective, totalShed, shedPct, ...
    nGenFault, nLineFaultDirect, nTransformerFault, nBranchOutageTotal, nThermalOff, ...
    'VariableNames', {'scenario','status','objective','total_shed_MW','shed_pct', ...
    'n_gen_fault','n_line_fault_direct','n_transformer_fault','n_branch_outage_total','n_thermal_off'});
writetable(summary, outSummaryCsv);

ok = strcmpi(status, 'OPTIMAL');
stats = struct();
stats.n_scenarios = nScen;
stats.n_optimal = nnz(ok);
stats.n_infeasible_or_other = nScen - nnz(ok);
stats.baseline_uses_ramp = false;
stats.fault_opf_uses_ramp = true;
stats.fault_ramp_reference = 'baseline OPF Pg';
stats.baseline_total_shed_MW = baselineShed;
stats.mean_total_shed_MW = mean(totalShed(ok));
stats.p95_total_shed_MW = percentile_value(totalShed(ok), 95);
stats.max_total_shed_MW = max(totalShed(ok));
stats.summary_csv = outSummaryCsv;

fprintf('结果已写入: %s\n', outSummaryCsv);
fprintf('可解场景 %d/%d；平均切负荷 %.3f MW；95%%分位 %.3f MW。\n', ...
    stats.n_optimal, nScen, stats.mean_total_shed_MW, stats.p95_total_shed_MW);
end


function y = percentile_value(x, p)
x = sort(x(isfinite(x)));
if isempty(x)
    y = NaN;
    return;
end
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
