function res = ref_to_res(ref, mpc, sc)
%REF_TO_RES  将 baseline_state_ref 转为 print_baseline_state 可用结构

[Pmax, Pmin, ~] = derate_sources(mpc, sc);
[lbPg, ubPg] = source_dispatch_bounds(mpc, sc, Pmax, Pmin);
[loadBus, Dtotal, Dlevel] = load_temperature(mpc, sc);

res = ref;
res.Pg = ref.Pg(:);
res.theta = ref.theta_deg(:) * pi/180;
res.Pmin = Pmin;
res.ubPg = ubPg;
res.lbPg = lbPg;
res.loadBus = loadBus(:);
res.Dtotal = Dtotal(:);
res.Dlevel = Dlevel;
res.shed = [ref.shed_L1(:), ref.shed_L2(:), ref.shed_L3(:)];
res.branch_flow = ref.branch_flow(:);
res.branch_loading = ref.branch_loading(:);
end
