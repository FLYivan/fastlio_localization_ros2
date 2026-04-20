#!/bin/bash
# C++重写节点编译和测试脚本

set -e  # 遇到错误立即退出

echo "========================================="
echo "FAST-LIO C++ 节点编译和测试脚本"
echo "========================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查工作目录
WORKSPACE_ROOT="/home/simit/FAST_LIO_LOCALIZATION2"
if [ ! -d "$WORKSPACE_ROOT" ]; then
    echo -e "${RED}错误: 工作空间不存在: $WORKSPACE_ROOT${NC}"
    exit 1
fi

cd "$WORKSPACE_ROOT"

echo -e "\n${YELLOW}步骤 1: 清理之前的编译${NC}"
rm -rf build install log

echo -e "\n${YELLOW}步骤 2: 编译C++节点${NC}"
colcon build --symlink-install --packages-select fast_lio_localization

echo -e "\n${YELLOW}步骤 3: 检查编译结果${NC}"
if [ ! -f "install/fast_lio_localization/lib/fast_lio_localization/transform_fusion" ]; then
    echo -e "${RED}错误: transform_fusion 编译失败${NC}"
    exit 1
fi

if [ ! -f "install/fast_lio_localization/lib/fast_lio_localization/global_localization" ]; then
    echo -e "${RED}错误: global_localization 编译失败${NC}"
    exit 1
fi

echo -e "${GREEN}✓ transform_fusion 编译成功${NC}"
echo -e "${GREEN}✓ global_localization 编译成功${NC}"

# Source工作空间
echo -e "\n${YELLOW}步骤 4: Source工作空间${NC}"
source install/setup.bash

# 检查依赖库
echo -e "\n${YELLOW}步骤 5: 检查依赖库${NC}"
ldd install/fast_lio_localization/lib/fast_lio_localization/transform_fusion | grep "not found" && {
    echo -e "${RED}错误: transform_fusion 缺少依赖库${NC}"
    exit 1
}

ldd install/fast_lio_localization/lib/fast_lio_localization/global_localization | grep "not found" && {
    echo -e "${RED}错误: global_localization 缺少依赖库${NC}"
    exit 1
}

echo -e "${GREEN}✓ 所有依赖库检查通过${NC}"

# 创建启动测试脚本
echo -e "\n${YELLOW}步骤 6: 创建测试脚本${NC}"
cat > test_cpp_nodes.sh << 'EOF'
#!/bin/bash
# 测试C++节点

# 停止可能运行的节点
echo "停止所有FAST-LIO节点..."
pkill -f fastlio_mapping || true
pkill -f global_localization || true
pkill -f transform_fusion || true
sleep 2

# 启动LiDAR驱动（如果需要）
echo "启动LiDAR驱动..."
# ros2 launch livox_ros_driver2 msg_MID360_launch.py &
# sleep 3

# 启动C++节点
echo "启动C++版本的fastlio_mapping..."
ros2 run fast_lio_localization fastlio_mapping --ros-args \
  --params-file /home/simit/FAST_LIO_LOCALIZATION2/install/fast_lio_localization/share/fast_lio_localization/config/mid360.yaml &
FASTLIO_PID=$!
sleep 2

echo "启动C++版本的transform_fusion..."
ros2 run fast_lio_localization transform_fusion &
FUSION_PID=$!
sleep 2

echo "启动C++版本的global_localization..."
ros2 run fast_lio_localization global_localization --ros-args \
  -r pcd_map_path:=/home/simit/FAST_LIO_LOCALIZATION2/maps/12f_map.pcd &
LOCALIZATION_PID=$!
sleep 2

# 监控CPU使用率
echo ""
echo "========================================="
echo "C++节点性能监控 (10秒)"
echo "========================================="
for i in {1..10}; do
    clear
    echo "CPU使用率监控 - 第 $i/10 秒"
    echo "========================================="
    ps aux | grep -E "(fastlio_mapping|transform_fusion|global_localization)" | grep -v grep | \
        awk '{printf "%-25s CPU: %5.1f%%  MEM: %4.1f%%  PID: %d\n", $11, $3, $4, $2}'
    sleep 1
done

# 清理
echo ""
echo "测试完成，停止节点..."
kill $FASTLIO_PID $FUSION_PID $LOCALIZATION_PID 2>/dev/null || true

echo "测试脚本已保存到: test_cpp_nodes.sh"
EOF

chmod +x test_cpp_nodes.sh

echo -e "${GREEN}✓ 测试脚本创建成功: test_cpp_nodes.sh${NC}"

# 创建launch文件对比脚本
echo -e "\n${YELLOW}步骤 7: 创建launch测试脚本${NC}"
cat > launch_comparison.sh << 'EOF'
#!/bin/bash
# Python vs C++性能对比测试

echo "========================================="
echo "FAST-LIO Python vs C++ 性能对比"
echo "========================================="

# Python版本测试
echo ""
echo "测试Python版本 (10秒)..."
echo "启动Python节点..."
ros2 launch fast_lio_localization localization.launch.py \
  map:=/home/simit/FAST_LIO_LOCALIZATION2/maps/12f_map.pcd \
  rviz:=false &
LAUNCH_PID=$!
sleep 5

echo "监控Python版本CPU..."
for i in {1..5}; do
    ps aux | grep -E "(fastlio|transform_fusion|global_localization)" | \
        grep -v grep | grep python | awk '{sum+=$3; count++} END {print "平均CPU:", sum "%"}'
    sleep 1
done

# 停止Python版本
kill $LAUNCH_PID 2>/dev/null || true
pkill -f "python.*fast_lio_localization" || true
sleep 3

# C++版本测试
echo ""
echo "测试C++版本 (10秒)..."
echo "启动C++节点..."
# 这里需要修改launch文件或手动启动C++节点
echo "请手动启动C++节点或使用 test_cpp_nodes.sh"

echo ""
echo "对比测试完成"
EOF

chmod +x launch_comparison.sh

echo -e "${GREEN}✓ 对比测试脚本创建成功: launch_comparison.sh${NC}"

# 总结
echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}编译和准备完成！${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "下一步操作:"
echo ""
echo "1. 测试C++节点:"
echo "   ./test_cpp_nodes.sh"
echo ""
echo "2. 或手动启动单个节点:"
echo "   ros2 run fast_lio_localization transform_fusion"
echo "   ros2 run fast_lio_localization global_localization --ros-args -r pcd_map_path:=/path/to/map.pcd"
echo ""
echo "3. 性能对比:"
echo "   ./launch_comparison.sh"
echo ""
echo "4. 监控性能:"
echo "   watch -n 1 'ps aux | grep -E (fastlio|transform_fusion|global_localization)'"
echo ""
echo -e "${YELLOW}注意事项:${NC}"
echo "- C++节点会自动替代Python节点"
echo "- 确保已提供地图文件路径"
echo "- 如果遇到问题，检查日志: ~/.ros/log/"
echo ""
