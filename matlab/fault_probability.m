function fp_res = fault_probability(res, mpc, sc, doPrint)
%FAULT_PROBABILITY  极热条件下变压器/电源/线路故障概率（基于运行基准状态）
%
%   用法:
%     >> fp = fault_probability()                      % 自动加载并求解/使用参考解
%     >> fp = fault_probability(res, mpc, sc)           % 用指定的基准状态结果
%     >> fp = fault_probability(res, mpc, sc, false)    % 仅计算，不打印
%
%   在第二步 DC-OPF 求解得到的系统运行基准状态(发电机出力 Pg、变压器/线路潮流)
%   基础上，建立三类元件在极热(高温+无风+强辐照)条件下的故障概率模型：
%     A. 变压器  —— IEEE C57.91 热点温度 + Arrhenius 老化加速 (W. Li 2002)
%     B. 电源    —— 比例风险(Cox)/Logistic 应力相关强迫停运率
%     C. 线路    —— IEEE Std 738 导线温度 + 温度/过载应力指数模型
%
%   关键：变压器功率->负载比 K；发电机出力 Pg->出力率 ℓ；线路潮流->电流/负载比。
%   并结合极热场景赋值(40°C, 2 m/s, 900 W/m²)。
%
%   与 verify/fault_probability.py 数值一致；详见 docs/04。

if nargin == 0
    mpc = case39_ehnw();
    sc  = weather_scenario();
    try
        fprintf('>> 正在调用 Gurobi 求解 DC-OPF 获取基准状态 ...\n');
        res = run_extreme_heat_opf('verbose', false);
        fprintf('>> 求解成功。\n');
    catch ME
        fprintf('>> Gurobi 不可用 (%s)，使用 baseline_state_ref。\n', ME.message);
        ref = baseline_state_ref();
        res = ref_to_res(ref, mpc, sc);
    end
elseif nargin < 3
    error('fault_probability:InvalidInput', ...
        '用法: fault_probability() 或 fault_probability(res, mpc, sc)');
end
if nargin < 4 || isempty(doPrint)
    doPrint = true;
end

% 若缺少支路潮流，由相角补算
if ~isfield(res, 'branch_flow') || isempty(res.branch_flow)
    res = enrich_branch_flows(mpc, res);
end

fp = fault_params();
Ta = sc.T_amb; v = sc.wind_speed; G = sc.irradiance;

%% ---------- A. 变压器 ----------
nbr = size(mpc.branch,1);
xf = struct('L',{},'fbus',{},'tbus',{},'rateA',{},'flow',{}, ...
            'K',{},'thetaH',{},'FAA',{},'lambda_yr',{},'Pf',{});
for l = 1:nbr
    tap = mpc.branch(l,5);
    if tap == 0, continue; end
    f = mpc.branch(l,1); t = mpc.branch(l,2);
    rateA = mpc.branch(l,4);
    flow = res.branch_flow(l);
    K = abs(flow)/rateA;
    thetaH = xf_hotspot(K, Ta, fp);
    FAA = xf_faa(thetaH, fp);
    lam_yr = fp.xf_lambda0_yr * FAA;
    Pf = pf_from_rate(lam_yr, fp);
    xf(end+1) = struct('L',l,'fbus',f,'tbus',t,'rateA',rateA,'flow',flow, ...
        'K',K,'thetaH',thetaH,'FAA',FAA,'lambda_yr',lam_yr,'Pf',Pf); %#ok<AGROW>
end

%% ---------- B. 电源 ----------
Tcell = Ta + (sc.NOCT - 20)/800 * G;
ng = numel(res.Pg);
typeName = {'火电','水电','风电','光伏'};
gen = struct('G',{},'bus',{},'type',{},'Prated',{},'Pg',{}, ...
             'ell',{},'Teff',{},'lambda0_yr',{},'stress',{},'lambda_yr',{},'Pf',{});
for g = 1:ng
    bus = mpc.gen(g,1); tc = mpc.gen(g,2); fc = mpc.gen(g,3);
    prated = mpc.gen(g,4);
    ell = 0; if prated>0, ell = max(res.Pg(g)/prated, 0); end
    if tc == 1   % 火电
        if fc == 2, key = 'gas'; fn = '-gas'; else, key = 'coal'; fn = '-coal'; end
        Teff = Ta;
    elseif tc == 2
        key = 'hydro'; fn = ''; Teff = Ta;
    elseif tc == 3
        key = 'wind'; fn = ''; Teff = Ta;
    else
        key = 'solar'; fn = ''; Teff = Tcell;
    end
    lam0 = fp.gen_lambda0_yr.(key);
    aT = fp.gen_aT.(key); aL = fp.gen_aL.(key);
    stress = aT*(Teff - fp.gen_T0) + aL*ell;
    lam_yr = lam0 * exp(stress);
    Pf = pf_from_rate(lam_yr, fp);
    gen(end+1) = struct('G',g,'bus',bus,'type',[typeName{tc} fn], ...
        'Prated',prated,'Pg',res.Pg(g),'ell',ell,'Teff',Teff, ...
        'lambda0_yr',lam0,'stress',stress,'lambda_yr',lam_yr,'Pf',Pf); %#ok<AGROW>
end

%% ---------- C. 线路 ----------
I_R = rated_current(fp);
ln = struct('L',{},'fbus',{},'tbus',{},'rateA',{},'flow',{}, ...
            'beta',{},'I',{},'Tc',{},'stress',{},'lambda_yr',{},'Pf',{});
for l = 1:nbr
    if mpc.branch(l,5) ~= 0, continue; end
    f = mpc.branch(l,1); t = mpc.branch(l,2);
    rateA = mpc.branch(l,4);
    flow = res.branch_flow(l);
    beta = abs(flow)/rateA;
    I = beta * I_R;
    Tc = conductor_temperature(I, Ta, v, G, fp);
    overT = max(Tc - fp.ln_Tc_ref, 0);
    overS = max(beta - 1, 0);
    stress = fp.ln_bT*overT + fp.ln_bS*overS;
    lam_yr = fp.ln_lambda0_yr * exp(stress);
    Pf = pf_from_rate(lam_yr, fp);
    ln(end+1) = struct('L',l,'fbus',f,'tbus',t,'rateA',rateA,'flow',flow, ...
        'beta',beta,'I',I,'Tc',Tc,'stress',stress,'lambda_yr',lam_yr,'Pf',Pf); %#ok<AGROW>
end

fp_res = struct();
fp_res.scenario = struct('T_amb',Ta,'wind',v,'irradiance',G, ...
    't_expose_h',fp.t_expose_h,'I_rated_A',I_R);
fp_res.transformers = xf;
fp_res.generators = gen;
fp_res.lines = ln;

if doPrint
    print_fault_probabilities(fp_res);
end

end

% =======================================================================
% 模型函数
% =======================================================================
function thetaH = xf_hotspot(K, Ta, fp)
% IEEE C57.91-2011 稳态热点温度
    dTO = fp.xf_dTO_rated * ((K.^2*fp.xf_R + 1)/(fp.xf_R + 1)).^fp.xf_n;
    dH  = fp.xf_dH_rated * K.^(2*fp.xf_m);
    thetaH = Ta + dTO + dH;
end

function FAA = xf_faa(thetaH, fp)
% Arrhenius 老化加速因子 (IEEE C57.91-2011, B=15000)
    B = fp.xf_B_arr; ref = fp.xf_theta_ref;
    FAA = exp(B/(ref+273) - B/(thetaH+273));
end

function I_R = rated_current(fp)
% 基准天气下使导线达连续运行温度(75°C)的额定电流
    Tc = fp.rate_Tc; Ta = fp.rate_Ta; v = fp.rate_v; G = fp.rate_G;
    D = fp.cond_D;
    qs = fp.cond_absorp * G * D;
    % 复用 conductor_temperature 内部同款散热式（此处直接重算）
    qcv = qc_local(Tc, Ta, v, fp);
    qrv = qr_local(Tc, Ta, fp);
    Rcv = fp.cond_R25 + (fp.cond_R75-fp.cond_R25)/50*(Tc-25);
    I_R = sqrt(max(qcv + qrv - qs, 0)/Rcv);
end

function q = qc_local(Tc, Ta, v, fp)
    D = fp.cond_D; Tfilm = 0.5*(Tc+Ta);
    kf = 2.424e-2 + 7.477e-5*Tfilm - 4.407e-9*Tfilm.^2;
    muf = (1.458e-6*(Tfilm+273).^1.5)./(Tfilm+273+383.4);
    rhof = 1.293./(1+0.00367*Tfilm);
    Nre = D*rhof*max(v,0)/muf;
    qc_f1 = (1.01 + 1.347*Nre.^0.52).*kf.*(Tc-Ta);
    qc_f2 = 0.754*Nre.^0.6.*kf.*(Tc-Ta);
    qc_nat = 3.645*rhof.^0.5*D^0.75.*max(Tc-Ta,0).^1.25;
    q = max([qc_f1, qc_f2, qc_nat]);
end

function q = qr_local(Tc, Ta, fp)
    D = fp.cond_D; eps = fp.cond_emiss;
    q = 17.8*D*eps*( ((Tc+273)/100).^4 - ((Ta+273)/100).^4 );
end

function Pf = pf_from_rate(lambda_yr, fp)
% 由年故障率得到评估窗口内故障概率 Pf = 1 - exp(-λ·Δt)
    lam_h = lambda_yr / 8760;
    Pf = 1 - exp(-lam_h * fp.t_expose_h);
end
