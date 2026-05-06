



1、mid360测试
# 调整为实际先验地图保存位置
    ros2 launch fast_lio_localization mid360_localization.launch.py \
        map:=/home/unitree/go2_patrol/map/test.pcd \
        rviz:=true


python3 -m pip show numpy

python3 -m pip show open3d
python3 -m pip show tf_transformations

apt list --installed | grep numpy


python3 - <<'PY'
import numpy
print("version:", numpy.__version__)
print("path:", numpy.__file__)
PY





# 一起飞，里程计就飞出去，排查方向

1、ros2 topic echo /livox/imu 
    1、重点比较电机关闭 vs 开启时，以下数值变化
        linear_acceleration
            ros2 topic echo /livox/imu | grep -A 3 linear_acceleration
        angular_velocity
            ros2 topic echo /livox/imu | grep -A 3 angular_velocity

2、调整yaml文件中的acc_cov/gyr_cov 参数
    增大协方差 = 更不信IMU
    调到1，再调到5


3、电机转，但不离地
    看 odom 是否已经开始飘，如果飘 → 振动问题实锤


4、看下时间是否同步
    1、开2个终端
    2、看时间戳是否非常接近
    ros2 topic echo /livox/imu --once
    ros2 topic echo /livox/lidar --once