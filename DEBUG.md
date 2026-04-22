

1、参考hesai.yaml,修改yaml文件
2、参考hesai_localization.launch.py
    1、mid360不需要 start_lidar_launch_file/transform_node
    2、修改declare_config_file

3、测试命令

    ros2 launch fast_lio_localization pcd_load_test.launch.py \
     map:=/path/to/map.pcd


    ros2 launch fast_lio_localization hesai_localization.launch.py \
         map:=/path/to/map.pcd


    ros2 launch fast_lio_localization utlidar_localization.launch.py \
        map:=/home/unitree/go2_patrol/map/test.pcd \
        config_file:=l1_test.yaml