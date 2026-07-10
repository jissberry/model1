function [lbPg, ubPg] = source_dispatch_bounds(mpc, sc, Pmax, Pmin, varargin)
%SOURCE_DISPATCH_BOUNDS  按机组类型计算调度可行区间
%
%   与 docs/01 源侧"调度区间特性与约束"一致，在单时段快照(dt_h)下：
%     火电: 开机时 Pmin <= Pg <= Pmax(T)；故障后OPF可叠加 |Pg-Pg0| <= R*dt；
%           启停变量 u 在 build_and_solve_dcopf.m 中施加
%     水电: 0 <= Pg <= Pmax         且 Pg*dt <= E_avail；故障后OPF可叠加爬坡
%     风电: 0 <= Pg <= Pmax(v)      （可弃风）
%     光伏: 0 <= Pg <= Pmax(G,T)    （可弃光）
%
%   mpc.genOps 列: [Pg0(MW), ramp_up_frac, ramp_down_frac, e_avail_frac]
%     e_avail_frac 仅水电使用，E_avail = e_avail_frac * Prated * dt_h (MWh)
%
%   可选参数:
%     'useRamp'    true/false，是否施加爬坡约束（默认 true，兼容旧调用）
%     'Pg0Override' ngx1，覆盖 genOps 中 Pg0；故障后OPF使用基准OPF出力

ng = size(mpc.gen, 1);
dt = sc.dt_h;
lbPg = zeros(ng, 1);
ubPg = zeros(ng, 1);

p = inputParser;
addParameter(p, 'useRamp', true, @islogical);
addParameter(p, 'Pg0Override', [], @(x) isempty(x) || numel(x) == ng);
parse(p, varargin{:});
useRamp = p.Results.useRamp;
Pg0Override = p.Results.Pg0Override;

for g = 1:ng
    typeCode = mpc.gen(g, 2);
    Prated   = mpc.gen(g, 4);
    if isempty(Pg0Override)
        Pg0  = mpc.genOps(g, 1);
    else
        Pg0v = Pg0Override(:);
        Pg0  = Pg0v(g);
    end
    rUp      = mpc.genOps(g, 2) * Prated;
    rDn      = mpc.genOps(g, 3) * Prated;

    switch typeCode
        case 1  % 火电：开机状态下的最小技术出力 + 高温降容上限；按需叠加爬坡
            lbPg(g) = Pmin(g);
            ubPg(g) = Pmax(g);
            if useRamp
                lbPg(g) = max(lbPg(g), Pg0 - rDn);
                ubPg(g) = min(ubPg(g), Pg0 + rUp);
            end

        case 2  % 水电：零下限 + 枯水上限 + 水库可用电量；按需叠加爬坡
            Eavail = mpc.genOps(g, 4) * Prated * dt;   % MWh
            PlimE  = Eavail / dt;                       % 本时段功率上限 MW
            lbPg(g) = 0;
            ubPg(g) = min(Pmax(g), PlimE);
            if useRamp
                lbPg(g) = max(lbPg(g), Pg0 - rDn);
                ubPg(g) = min(ubPg(g), Pg0 + rUp);
            end

        case 3  % 风电：不可调度，可弃风
            lbPg(g) = 0;
            ubPg(g) = Pmax(g);

        case 4  % 光伏：不可调度，可弃光
            lbPg(g) = 0;
            ubPg(g) = Pmax(g);

        otherwise
            error('未知机组类型: %d', typeCode);
    end

    if lbPg(g) > ubPg(g) + 1e-6
        error('机组 G%d 调度区间不可行: lb=%.2f > ub=%.2f', g, lbPg(g), ubPg(g));
    end
end

end
