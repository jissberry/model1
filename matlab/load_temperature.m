function [loadBus, Dtotal, Dlevel] = load_temperature(mpc, sc)
%LOAD_TEMPERATURE  第一步-B：极热条件下的荷侧温度响应与等级拆分
%
%   节点温度修正总需求:
%       D(T) = rho_rigid*Pd0 + rho_cool*Pd0*[1 + beta*(T - T_L0)]+
%   其中 rho_rigid = 1 - rho_cool（刚性基荷与温度无关；温敏空调负荷随温升增长）。
%
%   再按供电可靠性等级(一/二/三级)比例拆分，用于差异化切负荷惩罚。
%
%   输出: loadBus(nL x1) 负荷节点编号
%         Dtotal(nL x1)  各节点温度修正后总需求(MW)
%         Dlevel(nL x3)  各节点一/二/三级需求(MW)

loadBus = mpc.busPd0(:, 1);
Pd0     = mpc.busPd0(:, 2);
nL      = numel(loadBus);

rho_cool  = sc.rho_cool;
rho_rigid = 1 - rho_cool;
cool_factor = 1 + sc.beta_load * max(0, sc.T_amb - sc.T_L0);

Dtotal = rho_rigid .* Pd0 + rho_cool .* Pd0 .* cool_factor;

Dlevel = Dtotal * sc.level_frac;   % (nL x1) * (1 x3) = (nL x3)

end
