function [xfBus, xfP] = node_xf_power(mpc, res)
%NODE_XF_POWER  非电源节点变压器通过功率（来自基准状态）
%
%   建模假设（后续分析）：每个非电源节点配置一台同型号变压器；
%   变压器负载功率取该节点实际供电负荷 P_served（无负荷节点取 0）。
%
%   [xfBus, xfP] = node_xf_power(mpc, res)
%     xfBus  非电源节点编号 (1 x nTx)
%     xfP    各节点变压器通过功率 (MW)

genBuses = mpc.gen(:,1);
loadBus = res.loadBus(:);
shed = res.shed;
if size(shed, 1) ~= numel(loadBus)
    shed = shed';
end
lbMap = containers.Map(loadBus, 1:numel(loadBus));

xfBus = zeros(1, mpc.nBus);
xfP   = zeros(1, mpc.nBus);
n = 0;
for b = 1:mpc.nBus
    if any(genBuses == b)
        continue;
    end
    P = 0;
    if isKey(lbMap, b)
        k = lbMap(b);
        P = res.Dtotal(k) - sum(shed(k, :));
    end
    n = n + 1;
    xfBus(n) = b;
    xfP(n)   = max(P, 0);
end
xfBus = xfBus(1:n);
xfP   = xfP(1:n);

end
