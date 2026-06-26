function Tc = conductor_temperature(I, Ta, v, G, fp)
%CONDUCTOR_TEMPERATURE  由电流与天气按 IEEE Std 738 稳态热平衡求解导线温度
%
%   Tc = conductor_temperature(I, Ta, v, G, fp)
%
%   热平衡:  I^2 * R(Tc) + qs = qc(Tc) + qr(Tc)
%     qc 对流散热 (强迫低/高风速两式与自然对流取大者)
%     qr 辐射散热
%     qs 太阳辐射吸热
%   用二分法在 [Ta, 300] 内求根。
%
%   输入:
%     I  电流 (A)；Ta 环境温度 (°C)；v 风速 (m/s)；G 辐照度 (W/m^2)
%     fp 故障概率参数结构体 (见 fault_probability.m)
%   输出:
%     Tc 导线温度 (°C)

    D   = fp.cond_D;
    qs  = fp.cond_absorp * G * D;          % 投影面积 A'=D, 入射角 90°(最不利)

    balance = @(Tcx) I.^2 .* Rc(Tcx, fp) + qs ...
        - qc(Tcx, Ta, v, fp) - qr(Tcx, Ta, fp);

    lo = Ta; hi = 300.0;
    flo = balance(lo); fhi = balance(hi);
    if flo * fhi > 0
        if abs(flo) < abs(fhi), Tc = lo; else, Tc = hi; end
        return;
    end
    for k = 1:100
        mid = 0.5*(lo+hi);
        fm = balance(mid);
        if abs(fm) < 1e-6, Tc = mid; return; end
        if flo*fm <= 0
            hi = mid; fhi = fm;
        else
            lo = mid; flo = fm;
        end
    end
    Tc = 0.5*(lo+hi);
end

function R = Rc(Tc, fp)
% 导线电阻随温度线性插值/外推 (Ω/m)
    R = fp.cond_R25 + (fp.cond_R75 - fp.cond_R25)/(75.0-25.0) * (Tc - 25.0);
end

function q = qc(Tc, Ta, v, fp)
% 对流散热 (W/m): 强迫对流(低/高风速)与自然对流取大者
    D = fp.cond_D;
    Tfilm = 0.5*(Tc + Ta);
    [kf, muf, rhof] = air_props(Tfilm);
    Nre = D * rhof * max(v,0) / muf;
    qc_f1 = (1.01 + 1.347*Nre.^0.52) .* kf .* (Tc - Ta);
    qc_f2 = 0.754*Nre.^0.6 .* kf .* (Tc - Ta);
    qc_forced = max(qc_f1, qc_f2);
    qc_nat = 3.645*rhof.^0.5 * D^0.75 .* max(Tc - Ta, 0).^1.25;
    q = max(qc_forced, qc_nat);
end

function q = qr(Tc, Ta, fp)
% 辐射散热 (W/m)
    D = fp.cond_D; eps = fp.cond_emiss;
    q = 17.8*D*eps * ( ((Tc+273)/100).^4 - ((Ta+273)/100).^4 );
end

function [kf, muf, rhof] = air_props(Tf)
% IEEE Std 738-2012 海平面空气物性(随膜温变化)
    kf   = 2.424e-2 + 7.477e-5*Tf - 4.407e-9*Tf.^2;          % W/(m·K)
    muf  = (1.458e-6*(Tf+273).^1.5) ./ (Tf+273+383.4);       % kg/(m·s)
    rhof = 1.293 ./ (1 + 0.00367*Tf);                        % kg/m^3 (海平面)
end
