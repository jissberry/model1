function mc = monte_carlo_fault_scenarios(fp_res, nScen, seed, outCsv)
%MONTE_CARLO_FAULT_SCENARIOS  基于元件故障概率生成0/1蒙特卡洛故障场景
%
%   用法:
%     >> mc = monte_carlo_fault_scenarios()
%     >> mc = monte_carlo_fault_scenarios(fp_res)
%     >> mc = monte_carlo_fault_scenarios(fp_res, 2000, 20260627, 'fault_scenarios_2000.csv')
%
%   输出:
%     mc.states: nScen x 85 的0/1矩阵，0=故障，1=良好
%     mc.labels: 85维向量标签，顺序固定为 [G1..G10, L1..L46, T1..T29]
%     mc.prob_failure: 与 labels 对应的故障概率
%
%   抽样规则:
%     对元件 e，若 rand < p_e 则故障(0)，否则良好(1)。

if nargin < 1 || isempty(fp_res)
    fp_res = fault_probability();
end
if nargin < 2 || isempty(nScen)
    nScen = 2000;
end
if nargin < 3 || isempty(seed)
    seed = 20260627;
end
if nargin < 4
    outCsv = '';
end

gen = fp_res.generators;
ln  = fp_res.lines;
xf  = fp_res.transformers;

nGen = numel(gen);
nLine = numel(ln);
nXf = numel(xf);
nComp = nGen + nLine + nXf;
if nGen ~= 10 || nLine ~= 46 || nXf ~= 29
    error('monte_carlo_fault_scenarios:DimensionMismatch', ...
        '期望 10台发电机 + 46条线路 + 29台变压器 = 85维；当前为 %d + %d + %d。', ...
        nGen, nLine, nXf);
end

labels = cell(1, nComp);
prob_failure = zeros(1, nComp);
idx = 0;
for i = 1:nGen
    idx = idx + 1;
    labels{idx} = sprintf('G%d', gen(i).G);
    prob_failure(idx) = gen(i).Pf;
end
for i = 1:nLine
    idx = idx + 1;
    labels{idx} = sprintf('L%d', ln(i).L);
    prob_failure(idx) = ln(i).Pf;
end
for i = 1:nXf
    idx = idx + 1;
    labels{idx} = sprintf('T%d', xf(i).Tx);
    prob_failure(idx) = xf(i).Pf;
end

rng(seed, 'twister');
u = rand(nScen, nComp);
states = double(u >= repmat(prob_failure, nScen, 1));  % 0=故障, 1=良好

mc = struct();
mc.n_scenarios = nScen;
mc.seed = seed;
mc.order = '[G1..G10, L1..L46, T1..T29]';
mc.labels = labels;
mc.prob_failure = prob_failure;
mc.states = states;

if ~isempty(outCsv)
    write_scenarios_csv(outCsv, labels, states);
end

fprintf('已生成 %d 个故障场景，每个场景为 %d 维0/1向量（0=故障，1=良好）。\n', nScen, nComp);
fprintf('向量顺序: %s\n', mc.order);
fprintf('样例场景1: ');
fprintf('%d ', states(1,:));
fprintf('\n');
end

function write_scenarios_csv(outCsv, labels, states)
fid = fopen(outCsv, 'w');
if fid < 0
    error('monte_carlo_fault_scenarios:CannotWrite', '无法写入 %s', outCsv);
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, 'scenario');
for i = 1:numel(labels)
    fprintf(fid, ',%s', labels{i});
end
fprintf(fid, '\n');
for s = 1:size(states,1)
    fprintf(fid, '%d', s);
    fprintf(fid, ',%d', states(s,:));
    fprintf(fid, '\n');
end
end
