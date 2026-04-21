

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    
    
    package_path = get_package_share_directory("fast_lio_localization")
    default_config_path = os.path.join(package_path, "config")
    default_rviz_config_path = os.path.join(package_path, "rviz", "fastlio_localization.rviz")
    
    rviz_use = LaunchConfiguration("rviz")
    pcd_map_topic = LaunchConfiguration("pcd_map_topic")
    pcd_map_path = LaunchConfiguration("map")
    
    declare_rviz = DeclareLaunchArgument(
        "rviz",
        default_value="true",
        description="启用RViz可视化"
    )
    
    declare_map_path = DeclareLaunchArgument(
        "map",
        default_value="",
        description="PCD地图文件路径"
    )

    declare_pcd_map_topic = DeclareLaunchArgument(
        "pcd_map_topic",
        default_value="/cloud_pcd",
        description="PCD地图话题名"
    )
    
    
    
    
    # PCD地图发布器（两者共享）
    pcd_publisher_node = Node(
        package="fast_lio_localization",
        executable="pcd_map_publisher",
        name="map_publisher",
        output="screen",
        parameters=[
            {
                "file_name": pcd_map_path,
                "tf_frame": "map",
                "cloud_topic": pcd_map_topic,
                "publishing_period_ms": 500,
            }
        ],
        remappings=[("cloud_pcd", pcd_map_topic)]
    )
    
    
    
    # RViz可视化
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_cfg],
        condition=IfCondition(rviz_use)
    )
    
    ld = LaunchDescription()
    
    ld.add_action(pcd_publisher_node)


    return ld