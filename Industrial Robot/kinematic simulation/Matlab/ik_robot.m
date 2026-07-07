function q5d = ik_robot(p, R, geom)
% p   : [px py pz]
% R   : ma trận quay 3x3 (các vector n, o, a)
% geom: struct với các tham số hình học (d1,a2,a3,d4)

px = p(1); py = p(2); pz = p(3);

d1 = geom.d1;
a2 = geom.a2;
a3 = geom.a3;
d4 = geom.d4;

% Ma trận R = [n o a]
nx = R(1,1); ny = R(2,1); nz = R(3,1);  %#ok<NASGU>
ox = R(1,2); oy = R(2,2); oz = R(3,2);  %#ok<NASGU>
ax = R(1,3); ay = R(2,3); az = R(3,3);

%% ===== θ1 =====
theta1 = atan2(py, px);
c1 = cos(theta1); s1 = sin(theta1);

%% ===== θ5 (dùng n,o) =====
theta5 = atan2( s1*nx - c1*ny, s1*ox - c1*oy );
theta5 = theta5 - 2*pi/3;

%% ===== S234, C234 từ vector a =====
S234 = c1*ax + s1*ay;
C234 = -az;

%% ===== m, n =====
m = c1*px + s1*py - S234*d4;
n = pz - d1 + C234*d4;

%% ===== θ3 =====
k = (m^2 + n^2 - a3^2 - a2^2) / (2*a2*a3);  % cos(theta3)
k = max(min(k,1),-1);

s3 = -sqrt(max(0,1-k^2));   % nhánh -, nếu muốn nhánh kia thì cho s3 = +sqrt(...)
theta3 = atan2(s3, k);

%% ===== θ2 =====
u = a3*cos(theta3) + a2;
v = a3*sin(theta3);

theta2 = atan2( n*u - m*v, ...
                m*u - n*v );

%% ===== θ4 =====
theta234 = atan2(S234, C234);       % = atan2(c1*ax + s1*ay, -az)
theta4   = theta234 - theta2 - theta3-pi/2;

%% Gói lại và chuẩn hoá về (-pi, pi]
q5d = [theta1 theta2 theta3 theta4 theta5];
q5d = atan2(sin(q5d), cos(q5d));

end
