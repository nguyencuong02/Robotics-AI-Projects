clc; clear; close all;

%% Tải cấu hình
config;

switch upper(controller_type)
    case 'PI'
        lb = [Kp_range(1) Ki_range(1)];
        ub = [Kp_range(2) Ki_range(2)];
        nvars = 2;
    case 'PD'
        lb = [Kp_range(1) Kd_range(1)];
        ub = [Kp_range(2) Kd_range(2)];
        nvars = 2;
    case 'PID'
        lb = [Kp_range(1) Ki_range(1) Kd_range(1)];
        ub = [Kp_range(2) Ki_range(2) Kd_range(2)];
        nvars = 3;
    otherwise
        error('controller_type phải là PI | PD | PID');
end

%% Tùy chọn GA
opts = optimoptions('ga', ...
    'PopulationSize',    ga_opts.PopulationSize, ...
    'MaxGenerations',    ga_opts.MaxGenerations, ...
    'CrossoverFraction', ga_opts.CrossoverFraction, ...
    'MutationFcn',       ga_opts.MutationFcn, ...
    'SelectionFcn',      @selectiontournament, ...
    'CrossoverFcn',      @crossovertwopoint, ...
    'PlotFcn',           {@gaplotbestf,@gaplotbestindiv}, ...
    'Display',           ga_opts.Display);

%% Chạy GA (minimize cost) KHÔNG có ràng buộc phi tuyến
[xbest, fval] = ga(@(x) cost_pid(x, controller_type, cost_type, STOP_TIME), ...
                   nvars, [], [], [], [], lb, ub, [], opts);

% Giải thích kết quả theo controller
switch upper(controller_type)
    case 'PI'
        Kp = xbest(1); Ki = xbest(2); Kd = 0;
    case 'PD'
        Kp = xbest(1); Ki = 0;        Kd = xbest(2);
    case 'PID'
        Kp = xbest(1); Ki = xbest(2); Kd = xbest(3);
end

fprintf('\n===== KẾT QUẢ TỐI ƯU (GA + Simulink) =====\n');
fprintf('Controller: %s | Cost: %s\n', upper(controller_type), upper(cost_type));
fprintf('Kp = %.6f, Ki = %.6f, Kd = %.6f\n', Kp, Ki, Kd);
fprintf('Best cost = %.6f\n', fval);

%% Mô phỏng lại và vẽ
assignin('base','Kp',Kp);
assignin('base','Ki',Ki);
assignin('base','Kd',Kd);

simOut = sim('pid_model','StopTime',num2str(STOP_TIME),'SaveOutput','on');
[t,y]  = extract_y(simOut);

figure;
plot(t,y,'b','LineWidth',1.6); hold on;
yline(1,'--r');
title(sprintf('Step response – %s (%s)', upper(controller_type), upper(cost_type)));
xlabel('Time (s)');
ylabel('Output');
grid on;

%% ====================== HÀM ======================
function J = cost_pid(x, controller_type, cost_type, STOP_TIME)
% Xếp tham số theo loại controller
switch upper(controller_type)
    case 'PI'
        Kp = x(1); Ki = x(2); Kd = 0;
    case 'PD'
        Kp = x(1); Ki = 0;    Kd = x(2);
    case 'PID'
        Kp = x(1); Ki = x(2); Kd = x(3);
    otherwise
        error('controller_type phải là PI | PD | PID');
end

% Đẩy vào workspace cho Simulink
assignin('base','Kp',Kp);
assignin('base','Ki',Ki);
assignin('base','Kd',Kd);

% Chạy mô phỏng
try
    simOut = sim('pid_model','StopTime',num2str(STOP_TIME),'SaveOutput','on');
    [t,y]  = extract_y(simOut);
    e      = 1 - y(:);

    switch upper(cost_type)
        case 'IAE'
            J = trapz(t, abs(e));
        case 'ITAE'
            J = trapz(t, t(:).*abs(e));
        case 'MSE'
            J = mean(e.^2);
        otherwise
            error('cost_type phải là IAE | ITAE | MSE');
    end

    % Phạt overshoot
    Mp = max(0, max(y) - 1);
    if any(~isfinite(y))
        J = 1e9;
    end
    J = J + 5*(Mp^2);

catch ME
    warning('Sim error: %s | %s', ME.identifier, ME.message);
    J = 1e9;
end
end

function [t,y] = extract_y(simOut)
% Hỗ trợ cả Structure và Dataset
if isa(simOut,'Simulink.SimulationOutput')
    yout = simOut.get('yout');
else
    yout = simOut.yout;
end

if isa(yout,'Simulink.SimulationData.Dataset')
    sig = yout{1}.Values;
    t = sig.Time;
    y = sig.Data;
elseif isstruct(yout) && isfield(yout,'time') && isfield(yout,'signals')
    t = yout.time;
    y = yout.signals.values;
else
    error('To Workspace phải xuất "yout" (Structure hoặc Dataset).');
end

t = t(:);
y = y(:);
end