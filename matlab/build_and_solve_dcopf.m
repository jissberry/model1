function res = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbPg, ubPg, loadBus, Dtotal, Dlevel, genAvailable, branchAvailable)
%BUILD_AND_SOLVE_DCOPF  第二步：构建并用 Gurobi 求解极热场景源-荷失衡 DC-OPF
%
%   决策变量  x = [ Pg(ng) ; u_th(nTh) ; theta(nb) ; shed(nL*nLevel) ]
%   其中 u_th 仅用于火电机组启停状态；水电不设置启停变量。
%
%   目标:  min  sum_g (c2_g*Pg^2 + c1_g*Pg) + sum_{l,k} VOLL_k*shed_{l,k}
%
%   约束:
%     (1) 直流潮流节点功率平衡(等式)
%     (2) 源侧分类型调度约束:
%           火电: u*Pdisp_min<=Pg<=u*Pdisp_max；u为0/1启停变量
%           水电: 0<=Pg<=Pmax且电量/可选爬坡（无启停变量）
%           风电/光伏: 0<=Pg<=Pmax(v,G,T)
%     (3) 切负荷区间:             0 <= shed_{l,k} <= D_{l,k}(T)
%     (4) 线路潮流约束
%     (5) 平衡节点相角:           theta_slack = 0
%
%   需要 Gurobi 的 MATLAB 接口 (gurobi.m 在路径中)。

base = mpc.baseMVA;
nb   = mpc.nBus;
ng   = size(mpc.gen, 1);
nbr  = size(mpc.branch, 1);
nL   = numel(loadBus);
nLev = numel(sc.level_frac);
thermalIdx = find(mpc.gen(:,2) == 1);
nTh = numel(thermalIdx);

if nargin < 10 || isempty(genAvailable)
    genAvailable = true(ng, 1);
end
if nargin < 11 || isempty(branchAvailable)
    branchAvailable = true(nbr, 1);
end
genAvailable = logical(genAvailable(:));
branchAvailable = logical(branchAvailable(:));
if numel(genAvailable) ~= ng
    error('build_and_solve_dcopf:InvalidGenMask', ...
        'genAvailable 长度应为 %d，当前为 %d。', ng, numel(genAvailable));
end
if numel(branchAvailable) ~= nbr
    error('build_and_solve_dcopf:InvalidBranchMask', ...
        'branchAvailable 长度应为 %d，当前为 %d。', nbr, numel(branchAvailable));
end

% 故障机组最大出力为0；火电故障等价于强制u=0，非火电故障直接Pg=0。
Pmax = Pmax(:); Pmin = Pmin(:); lbPg = lbPg(:); ubPg = ubPg(:);
Pmax(~genAvailable) = 0;
Pmin(~genAvailable) = 0;
lbPg(~genAvailable) = 0;
ubPg(~genAvailable) = 0;

% 变量索引
iPg = @(g) g;
iU  = @(k) ng + k;                       % 火电启停变量 k=1..nTh
iTh = @(n) ng + nTh + n;                 % 母线编号 1..nb 连续
iSh = @(l,k) ng + nTh + nb + (k-1)*nL + l;
nvar = ng + nTh + nb + nL*nLev;

% 负荷节点 -> 行位置 映射
busToLoadPos = zeros(nb, 1);
for l = 1:nL
    busToLoadPos(loadBus(l)) = l;
end

% ---- 构建 Bbus（节点电纳矩阵） ----
Bbus = zeros(nb, nb);
bser = zeros(nbr, 1);
fb   = mpc.branch(:,1);  tb = mpc.branch(:,2);
for l = 1:nbr
    x   = mpc.branch(l,3);
    tap = mpc.branch(l,5);  if tap == 0, tap = 1; end
    b   = 1/(x*tap);
    bser(l) = b;
    if ~branchAvailable(l)
        continue;
    end
    i = fb(l);  j = tb(l);
    Bbus(i,i) = Bbus(i,i) + b;
    Bbus(j,j) = Bbus(j,j) + b;
    Bbus(i,j) = Bbus(i,j) - b;
    Bbus(j,i) = Bbus(j,i) - b;
end

% ---- 约束三元组(行,列,值) ----
I = []; J = []; V = [];
rhs = []; sense = '';
row = 0;

% (1) 节点功率平衡 nb 行（等式）
for n = 1:nb
    row = row + 1;
    % base*Bbus(n,:) 对 theta
    for m = 1:nb
        if Bbus(n,m) ~= 0
            I(end+1)=row; J(end+1)=iTh(m); V(end+1)= base*Bbus(n,m); %#ok<*AGROW>
        end
    end
    % -Pg@n
    gidx = find(mpc.gen(:,1) == n);
    for gg = gidx'
        I(end+1)=row; J(end+1)=iPg(gg); V(end+1)= -1;
    end
    % -shed@n
    l = busToLoadPos(n);
    Dn = 0;
    if l > 0
        Dn = Dtotal(l);
        for k = 1:nLev
            I(end+1)=row; J(end+1)=iSh(l,k); V(end+1)= -1;
        end
    end
    rhs(end+1) = -Dn;
    sense(end+1) = '=';
end

% (4) 线路潮流约束 2*nbr 行
for l = 1:nbr
    if ~branchAvailable(l)
        continue;
    end
    i = fb(l);  j = tb(l);
    coef = base*bser(l);
    rateA = mpc.branch(l,4);
    % f <= rateA
    row = row + 1;
    I(end+1)=row; J(end+1)=iTh(i); V(end+1)= coef;
    I(end+1)=row; J(end+1)=iTh(j); V(end+1)=-coef;
    rhs(end+1)=  rateA;  sense(end+1)='<';
    % f >= -rateA
    row = row + 1;
    I(end+1)=row; J(end+1)=iTh(i); V(end+1)= coef;
    I(end+1)=row; J(end+1)=iTh(j); V(end+1)=-coef;
    rhs(end+1)= -rateA;  sense(end+1)='>';
end

% (2a) 火电启停约束：u_i*lbPg_i <= Pg_i <= u_i*ubPg_i
%      u_i=0 时 Pg_i=0；u_i=1 时 Pg_i 落在含降容/爬坡后的调度区间。
for k = 1:nTh
    g = thermalIdx(k);
    % Pg_i - ub_i*u_i <= 0
    row = row + 1;
    I(end+1)=row; J(end+1)=iPg(g); V(end+1)=1;
    I(end+1)=row; J(end+1)=iU(k);  V(end+1)=-ubPg(g);
    rhs(end+1)=0; sense(end+1)='<';
    % Pg_i - lb_i*u_i >= 0
    row = row + 1;
    I(end+1)=row; J(end+1)=iPg(g); V(end+1)=1;
    I(end+1)=row; J(end+1)=iU(k);  V(end+1)=-lbPg(g);
    rhs(end+1)=0; sense(end+1)='>';
end

A = sparse(I, J, V, row, nvar);

% ---- 变量上下界 ----
lb = -inf(nvar,1);
ub =  inf(nvar,1);
% Pg — 非火电直接使用连续调度区间；火电下界由 u_i*lbPg_i 约束给出
lb(1:ng)   = lbPg;
ub(1:ng)   = ubPg;
lb(thermalIdx) = 0;
% u_th — 火电启停变量
for k = 1:nTh
    lb(iU(k)) = 0;
    ub(iU(k)) = 1;
    if ~genAvailable(thermalIdx(k))
        ub(iU(k)) = 0;
    end
end
% theta 自由，平衡节点固定为 0
lb(iTh(mpc.slackBus)) = 0;
ub(iTh(mpc.slackBus)) = 0;
% shed
for l = 1:nL
    for k = 1:nLev
        lb(iSh(l,k)) = 0;
        ub(iSh(l,k)) = Dlevel(l,k);
    end
end

% ---- 目标函数 ----
obj = zeros(nvar,1);
c2  = mpc.gen(:,6);  c1 = mpc.gen(:,7);
obj(1:ng) = c1;
for l = 1:nL
    for k = 1:nLev
        obj(iSh(l,k)) = sc.voll(k);
    end
end
% 二次项 Q（对角，仅 Pg）
Qdiag = zeros(nvar,1);
Qdiag(1:ng) = c2;
Q = spdiags(Qdiag, 0, nvar, nvar);

% ---- 组装 Gurobi 模型并求解 ----
model.A          = A;
model.rhs        = rhs(:);
model.sense      = sense;
model.lb         = lb;
model.ub         = ub;
model.obj        = obj;
model.Q          = Q;
model.modelsense = 'min';
model.vtype      = repmat('C', nvar, 1);
for k = 1:nTh
    model.vtype(iU(k)) = 'B';
end

params.OutputFlag = 1;
params.QCPDual    = 0;

gres = gurobi(model, params);

% ---- 解析结果 ----
res.status   = gres.status;
if ~isfield(gres, 'x')
    res.obj      = NaN;
    res.Pg       = NaN(ng, 1);
    res.uThermal = NaN(nTh, 1);
    res.unit_on  = NaN(ng, 1);
    res.thermalIdx = thermalIdx;
    res.theta    = NaN(nb, 1);
    res.shed     = NaN(nL, nLev);
    res.Pmax     = Pmax;  res.Pmin = Pmin;
    res.lbPg     = lbPg;  res.ubPg = ubPg;
    res.loadBus  = loadBus; res.Dtotal = Dtotal; res.Dlevel = Dlevel;
    res.bser     = bser;  res.fb = fb;  res.tb = tb;
    res.rateA    = mpc.branch(:,4);
    res.branchAvailable = branchAvailable;
    res.branch_flow = zeros(nbr, 1);
    res.genAvailable = genAvailable;
    res.gen_cost = NaN;
    res.shed_cost = NaN;
    return;
end
x            = gres.x;
res.obj      = gres.objval;
res.Pg       = x(1:ng);
res.uThermal = x(ng+1 : ng+nTh);
res.unit_on  = ones(ng, 1);
res.unit_on(thermalIdx) = res.uThermal;
res.thermalIdx = thermalIdx;
res.theta    = x(ng+nTh+1 : ng+nTh+nb);
res.shed     = reshape(x(ng+nTh+nb+1:end), nL, nLev);
res.Pmax     = Pmax;  res.Pmin = Pmin;
res.lbPg     = lbPg;  res.ubPg = ubPg;
res.loadBus  = loadBus; res.Dtotal = Dtotal; res.Dlevel = Dlevel;
res.bser     = bser;  res.fb = fb;  res.tb = tb;
res.rateA    = mpc.branch(:,4);
res.branchAvailable = branchAvailable;
res.branch_flow = zeros(nbr, 1);
for l = 1:nbr
    if branchAvailable(l)
        res.branch_flow(l) = base*bser(l)*(res.theta(fb(l))-res.theta(tb(l)));
    end
end
res.genAvailable = genAvailable;
res.gen_cost = sum(c2.*res.Pg.^2 + c1.*res.Pg);
res.shed_cost= sum(sum(res.shed .* repmat(sc.voll, nL, 1)));

end
