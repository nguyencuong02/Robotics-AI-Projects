function [t_seg, q_seg] = Move(p, R, geom, t_start, t_hold, q_prev, varargin)
% MoveL_cmd: đi thẳng tới điểm p, giữ hoặc đổi gripper
%
% p        : [px py pz]
% R        : 3x3 orientation (n,o,a)
% geom     : struct d1,a2,a3,d4
% t_start  : thời điểm bắt đầu
% t_hold   : thời gian giữ
% q_prev   : 1x6, giá trị joint trước đó
%
% OPTIONAL:
%   g_new  : giá trị gripper mong muốn
%
% Output:
%   t_seg : [2x1]
%   q_seg : [2x6]

    % IK cho 5 khớp đầu
    q5 = ik_robot(p, R, geom);

    % Nếu có tham số gripper → dùng giá trị mới
    if ~isempty(varargin)
        g_val = varargin{1};
    else
        g_val = q_prev(6);   % giữ nguyên kẹp
    end

    q_target = [q5 g_val];

    % tạo đoạn lệnh
    t_seg = [t_start; t_start + t_hold];
    q_seg = [q_prev; q_target];
end
