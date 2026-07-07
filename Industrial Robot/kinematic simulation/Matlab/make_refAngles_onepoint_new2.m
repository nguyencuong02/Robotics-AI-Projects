function make_refAngles_onepoint_new2()
clc;

%% ===== Hình học =====
geom.d1 = 0.085;
geom.a2 = 0.155;
geom.a3 = 0.155;
geom.d4 = 0.100;

%% ===== Orientation tool hướng xuống =====
R = [1 0 0;
     0 1 0;
     0 0 -1];

%% ===== Khởi tạo quỹ đạo tổng =====
t_all = [];
q_all = [];

t_cur = 0;                       % thời gian bắt đầu
q_cur = [0 0 0 0 0 0];           % joint ban đầu (gripper open)

%% ===== HÀM CON addMoveL: tự nối lệnh MoveL =====
    function addMoveL(p, t_hold, varargin)
        % p      : [px py pz]
        % t_hold : thời gian giữ (s)
        % varargin (tùy chọn): g_new (giá trị gripper mới)
        [t_seg, q_seg] = MoveL(p, R, geom, t_cur, t_hold, q_cur, varargin{:});
        % nối vào quỹ đạo tổng
        t_all = [t_all; t_seg];
        q_all = [q_all; q_seg];
        % cập nhật trạng thái hiện tại
        t_cur = t_seg(end);
        q_cur = q_seg(end,:);
    end

%% ===== VIẾT KỊCH BẢN MOVE =====
% cú pháp:
%   addMoveL([x y z], t_hold);          % giữ gripper như cũ
%   addMoveL([x y z], t_hold, g_new);   % đổi gripper = g_new

addMoveL([0.18  0.18  0.30], 5);        % đến trên điểm 1, giữ gripper
addMoveL([0.18  0.18  0.30], 5, pi);    % at same pose, đóng kẹp = pi

addMoveL([0.18  0.18  0.05], 5);        % hạ xuống, giữ kẹp
addMoveL([0.18  0.18  0.05], 5, 0);     % mở kẹp

addMoveL([0.18  0.18  0.30], 5);        % nhấc lên

addMoveL([0.18 -0.18  0.30], 5);        % sang vị trí 2
addMoveL([0.18 -0.18  0.00], 5);        % hạ xuống

addMoveL([0.18 -0.18  0.00], 5, pi);    % đóng kẹp
addMoveL([0.18 -0.18  0.30], 5, pi);    % nhấc lên, vẫn đóng (lưu ý: dùng 0.30, không phải 30.0)

%% ===== refAngles =====
refAngles.time               = t_all;
refAngles.signals.values     = q_all;
refAngles.signals.dimensions = 6;

assignin('base','refAngles', refAngles);
disp('Đã tạo refAngles với addMoveL, không cần quản lý t1,q1,...');

end
