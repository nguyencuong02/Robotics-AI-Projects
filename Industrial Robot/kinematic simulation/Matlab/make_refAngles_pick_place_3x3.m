function make_refAngles_pick_place_3x3()
clc;

%% ===== Hình học robot =====
geom.d1 = 0.085;
geom.a2 = 0.155;
geom.a3 = 0.155;
geom.d4 = 0.100;

%% ===== Orientation tool hướng xuống =====
R = [1 0 0;
     0 1 0;
     0 0 -1];

%% ===== Tham số PICK & PLACE =====
z_safe   = 0.15;   % cao an toàn
z_pick   = 0.05;   % cao gắp
z_place  = 0.1;   % cao đặt của layer 0
dz       = 0.05;   % độ tăng cao theo mỗi layer

% Điểm pick (một vị trí cố định)
pick_xy  = [0.15  -0.15];
pick_abv = [pick_xy  z_safe];
pick_pos = [pick_xy  z_pick];

% Lưới 3x3: gốc (ô 1,1), khoảng cách giữa các ô
place_origin = [0.1  0.1];   % tâm ô (hàng 1, cột 1)
dx = 0.02;    % bước theo trục X (cột)
dy = 0.02;    % bước theo trục Y (hàng)

%% ===== Khởi tạo quỹ đạo tổng =====
t_all = [];
q_all = [];

t_cur = 0;
q_cur = [0 0 0 0 0 0];   % joint ban đầu (gripper open)

%% ===== HÀM CON: addMoveL =====
    function addMove(p, t_hold, varargin)
        [t_seg, q_seg] = Move(p, R, geom, t_cur, t_hold, q_cur, varargin{:});
        t_all = [t_all; t_seg];
        q_all = [q_all; q_seg];
        t_cur = t_seg(end);
        q_cur = q_seg(end,:);
    end

%% ===== CHƯƠNG TRÌNH PICK & PLACE 3×3×3 =====
t_move  = 3;     % thời gian cho mỗi lệnh MoveL
g_open  = pi;    % gripper mở
g_close = 0;     % gripper đóng

for layer = 0:2       % 3 tầng
    for row = 0:2     % 3 hàng
        for col = 0:2 % 3 cột
            
            %% ==== 1) PICK cố định ====
            addMove(pick_abv, t_move, g_open);
            addMove(pick_pos, t_move);
            addMove(pick_pos, t_move, g_close);
            addMove(pick_abv, t_move);
            
            %% ==== 2) PLACE tại ô (row,col,layer) ====
            px = place_origin(1) + col*dx;
            py = place_origin(2) + row*dy;
            
            pz_abv = z_safe  + layer*dz;
            pz_pos = z_place + layer*dz;
            
            place_abv = [px, py, pz_abv];
            place_pos = [px, py, pz_pos];
            
            addMove(place_abv, t_move);
            addMove(place_pos, t_move);
            addMove(place_pos, t_move, g_open);
            addMove(place_abv, t_move);
        end
    end
end

%% ===== Xuất refAngles =====
refAngles.time               = t_all;
refAngles.signals.values     = q_all;
refAngles.signals.dimensions = 6;

assignin('base','refAngles', refAngles);
disp('Đã tạo refAngles: PICK, PLACE 3×3×3.');

end
