function res = enrich_branch_flows(mpc, res)
%ENRICH_BRANCH_FLOWS  由节点相角计算各支路/变压器有功潮流与负载率
%
%   DC 潮流:  P_ij = S_B * b_ij * (theta_i - theta_j)
%             b_ij = 1 / (x_ij * tap_ij)

base = mpc.baseMVA;
nbr  = size(mpc.branch, 1);
fb   = mpc.branch(:, 1);
tb   = mpc.branch(:, 2);

res.branch_flow    = zeros(nbr, 1);
res.branch_loading = zeros(nbr, 1);
res.branch_tap     = mpc.branch(:, 5);
res.is_transformer = res.branch_tap ~= 0;

for l = 1:nbr
    i = fb(l);  j = tb(l);
    x = mpc.branch(l, 3);
    tap = res.branch_tap(l);  if tap == 0, tap = 1; end
    bser = 1 / (x * tap);
    flow = base * bser * (res.theta(i) - res.theta(j));
    rateA = mpc.branch(l, 4);
    res.branch_flow(l) = flow;
    res.branch_loading(l) = abs(flow) / rateA * 100;
end

res.fb = fb;
res.tb = tb;
res.rateA = mpc.branch(:, 4);

end
