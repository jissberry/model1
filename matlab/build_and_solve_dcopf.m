function res = build_and_solve_dcopf(mpc, sc, Pmax, Pmin, lbPg, ubPg, loadBus, Dtotal, Dlevel)
%BUILD_AND_SOLVE_DCOPF  第二步：构建并用 Gurobi 求解极热场景源-荷失衡 DC-OPF
%
%   决策变量  x = [ Pg(ng) ; theta(nb) ; shed(nL*nLevel) ]
%
%   目标:  min  sum_g (c2_g*Pg^2 + c1_g*Pg) + sum_{l,k} VOLL_k*shed_{l,k}
%
%   约束:
%     (1) 直流潮流节点功率平衡(等式)
%     (2) 源侧分类型调度约束(变量界):
%           火电: Pmin<=Pg<=Pmax(T) 且爬坡; 水电:0<=Pg<=Pmax且电量/爬坡
%           风电/光伏: 0<=Pg<=Pmax(v,G,T)
%     (3) 切负荷区间:             0 <= shed_{l,k} <= D_{l,k}(T)
%     (4) 线路潮流约束
%     (5) 平衡节点相角:           theta_slack = 0
%
%   需要 Gurobi 的 MATLAB 接口 (gurobi.m 在路径中)。

base = mpc.baseMVA;
nb   = mpc.nBus;
ng   = size(mpc.gen, 1);
nL   = numel(loadBus);
nLev = numel(sc.level_frac);

% 变量索引
iPg = @(g) g;
iTh = @(n) ng + n;                       % 母线编号 1..nb 连续
iSh = @(l,k) ng + nb + (k-1)*nL + l;
nvar = ng + nb + nL*nLev;

% 负荷节点 -> 行位置 映射
busToLoadPos = zeros(nb, 1);
for l = 1:nL
    busToLoadPos(loadBus(l)) = l;
end

% ---- 构建 Bbus（节点电纳矩阵） ----
Bbus = zeros(nb, nb);
nbr  = size(mpc.branch, 1);
bser = zeros(nbr, 1);
fb   = mpc.branch(:,1);  tb = mpc.branch(:,2);
for l = 1:nbr
    x   = mpc.branch(l,3);
    tap = mpc.branch(l,5);  if tap == 0, tap = 1; end
    b   = 1/(x*tap);
    bser(l) = b;
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

A = sparse(I, J, V, row, nvar);

% ---- 变量上下界 ----
lb = -inf(nvar,1);
ub =  inf(nvar,1);
% Pg — 源侧分类型调度区间（lbPg/ubPg 已含降容、最小出力、爬坡、水电电量）
lb(1:ng)   = lbPg;
ub(1:ng)   = ubPg;
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

params.OutputFlag = 1;
params.QCPDual    = 0;

gres = gurobi(model, params);

% ---- 解析结果 ----
res.status   = gres.status;
res.obj      = gres.objval;
x            = gres.x;
res.Pg       = x(1:ng);
res.theta    = x(ng+1 : ng+nb);
res.shed     = reshape(x(ng+nb+1:end), nL, nLev);
res.Pmax     = Pmax;  res.Pmin = Pmin;
res.lbPg     = lbPg;  res.ubPg = ubPg;
res.loadBus  = loadBus; res.Dtotal = Dtotal; res.Dlevel = Dlevel;
res.bser     = bser;  res.fb = fb;  res.tb = tb;
res.rateA    = mpc.branch(:,4);
res.gen_cost = sum(c2.*res.Pg.^2 + c1.*res.Pg);
res.shed_cost= sum(sum(res.shed .* repmat(sc.voll, nL, 1)));

end
