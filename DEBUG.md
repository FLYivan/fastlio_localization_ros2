



1、mid360测试
# 调整为实际先验地图保存位置
    ros2 launch fast_lio_localization mid360_localization.launch.py \
        map:=/home/unitree/go2_patrol/map/test.pcd \
        rviz:=true