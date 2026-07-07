%% ========== CONFIG CHO GA–PID + SIMULINK ==========

% ---- Plant: G(s) = k / (s^2 + a1*s + a2)
k  = 2;        % hệ số khuếch đại
a1 = 12;       % hệ số s^1
a2 = 20.02;    % hệ số tự do

% chuyển vào workspace để Simulink dùng trong Transfer Fcn block
assignin('base','numPlant',[k]);
assignin('base','denPlant',[a1 a2]);

% ---- Bộ điều khiển ----
controller_type = 'PID';     % 'PI' | 'PD' | 'PID'

% ---- Chuẩn đánh giá ----
cost_type = 'ITAE';          % 'IAE' | 'ITAE' | 'MSE'

% ---- Miền tìm kiếm PID ----
Kp_range = [0 100];
Ki_range = [0 100];
Kd_range = [0 50];

% ---- Thời gian mô phỏng ----
STOP_TIME = 5;               % (s)

% ---- Tùy chọn GA ----
ga_opts.PopulationSize    = 20;     % số cá thể
ga_opts.MaxGenerations    = 5;     % số thế hệ
ga_opts.CrossoverFraction = 0.8;    % Pc
ga_opts.MutationFcn       = {@mutationuniform, 0.01};  % Pm
ga_opts.SelectionFcn      = @selectiontournament;       % SUS (ổn định)
ga_opts.Display           = 'iter';
