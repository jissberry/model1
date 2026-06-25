function [Pmax, Pmin, typeName] = derate_sources(mpc, sc)
%DERATE_SOURCES  第一步-A：极热无风条件下四类机组最大出力(降容)与出力区间
%
%   输入: mpc 算例数据, sc 气象场景
%   输出: Pmax(ng x1) 高温降容后最大出力, Pmin(ng x1) 最小技术出力,
%         typeName  各机组类型中文名(cell)
%
%   四类机组最大出力公式：
%   1) 火电 thermal:  Pmax = Prated * [1 - alpha*(T - Tref)]+
%   2) 水电 hydro  :  Pmax = k_hydro * Prated         (枯水/低水头折减)
%   3) 风电 wind   :  分段风速-功率曲线；无风(v<v_ci) 时 ≈ 0
%   4) 光伏 solar  :  Pmax = Prated*(G/Gstc)*[1+gamma*(Tcell-Tstc)]

ng = size(mpc.gen, 1);
Pmax = zeros(ng, 1);
Pmin = zeros(ng, 1);
typeName = cell(ng, 1);

for g = 1:ng
    typeCode  = mpc.gen(g, 2);
    fuelCode  = mpc.gen(g, 3);
    Prated    = mpc.gen(g, 4);
    pmin_frac = mpc.gen(g, 5);

    switch typeCode
        case 1  % 火电
            if fuelCode == 2
                alpha = sc.alpha_gas;  typeName{g} = '火电-燃气';
            else
                alpha = sc.alpha_coal; typeName{g} = '火电-燃煤';
            end
            derate = 1 - alpha * max(0, sc.T_amb - sc.T_ref_thermal);
            Pmax(g) = Prated * max(0, derate);

        case 2  % 水电
            typeName{g} = '水电';
            Pmax(g) = sc.k_hydro * Prated;

        case 3  % 风电
            typeName{g} = '风电';
            v = sc.wind_speed;
            if v < sc.v_cut_in || v > sc.v_cut_out
                frac = 0;
            elseif v < sc.v_rated
                frac = (v^3 - sc.v_cut_in^3) / (sc.v_rated^3 - sc.v_cut_in^3);
            else
                frac = 1;
            end
            Pmax(g) = Prated * frac;

        case 4  % 光伏
            typeName{g} = '光伏';
            Tcell = sc.T_amb + (sc.NOCT - 20)/800 * sc.irradiance;
            frac  = (sc.irradiance / sc.G_stc) * ...
                    (1 + sc.gamma_pv * (Tcell - sc.T_stc));
            Pmax(g) = Prated * max(0, frac);

        otherwise
            error('未知机组类型代码: %d', typeCode);
    end

    % 最小技术出力（火电/水电按额定比例；风光为 0，可弃风弃光）
    % 高温降容后若 Pmax < 名义 Pmin，则取 Pmin = min(Pmin, Pmax) 保证可行
    Pmin(g) = min(pmin_frac * Prated, Pmax(g));
end

end
