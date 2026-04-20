# FAST_LIO_LOCALIZATION2 调试报告

**日期**: 2026-04-10  
**项目**: FAST_LIO_LOCALIZATION2 - 基于 FAST-LIO2 的实时 3D 全局定位系统  
**调试人员**: simit  
**环境**: ROS2 Humble, Ubuntu 22.04, Jetson (192.168.123.101), 笔记本 (192.168.123.102), 机器狗 (192.168.123.161)

---

## 📋 调试目标

1. 部署 FAST_LIO_LOCALIZATION2 到 Jetson 主机
2. 实现跨设备可视化（笔记本 RViz 显示 Jetson 的定位结果）
3. 集成机器狗系统数据，统一 ROS2 网络
4. 优化系统性能（CPU 占用、定位漂移）

---

## ✅ 已完成工作

### 1. 环境搭建与依赖安装

| 依赖项 | 状态 | 说明 |
|--------|------|------|
| ROS2 Humble | ✅ | 已安装，核心包完整 |
| PCL (libpcl-dev) | ✅ | 版本 1.12 |
| Eigen3 | ✅ | libeigen3-dev |
| Python 依赖 | ✅ | `tf-transformations` (apt), `ros2_numpy`, `open3d` |
| numpy | ✅ | 1.24.2（已降级符合要求） |
| ikd-Tree | ✅ | ros2 分支 submodule 已初始化 |
| matplotlibcpp.h | ✅ | 已安装 |
| **剪贴板工具** | ⚠️ **不可用** | `xclip` `xsel` 已安装，但 OpenCode 终端无法复制 |

**命令**:
```bash
sudo apt install ros-humble-tf-transformations
pip3 install ros2-numpy open3d
```

### 2. 代码修改

#### 2.1 `fast_lio_localization/global_localization.py`
- **问题**: Open3D 警告 `The 'intensity' field is not present`
- **修复**: 在 `msg_to_array` 方法中添加 `warnings` 过滤
- **位置**: 第 81-83 行

```python
def msg_to_array(self, pc_msg):
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="The 'intensity' field is not present")
        warnings.filterwarnings("ignore", message="The 'rgb' field is not present")
        pc_array = ros2_numpy.numpify(pc_msg)
    return pc_array["xyz"]
```

#### 2.2 `fast_lio_localization/transform_fusion.py`
- **问题**: `transform_fusion` 节点 CPU 占用 140%+，导致 TF 卡顿
- **原因**: 定时器频率 50Hz 过高
- **修复**: 降低 `freq_pub_localization` 从 50 → **10 Hz**
- **位置**: 第 31 行

```python
self.freq_pub_localization = 10  # 降低到 10Hz
self.timer = self.create_timer(1/self.freq_pub_localization, self.transform_fusion)
```

### 3. 脚本创建

| 脚本 | 功能 | 说明 |
|------|------|------|
| `start_livox.sh` | 启动 Livox MID360 驱动 | 设置 ROS_DOMAIN_ID=0 |
| `start_with_rviz.sh` | 本地启动（带 RViz） | 设置 ROS_DOMAIN_ID=0, `pcd_map_topic:=/cloud_pcd` |
| `start_without_rviz.sh` | 远程可视化启动 | 无 RViz，设置 ROS_DOMAIN_ID=0 |
| `restart_all.sh` | 重启所有节点 | 停止→清理→启动 |
| `monitor_system.sh` | 详细监控日志 | CSV 格式记录 |
| `monitor_fast.sh` | 轻量级监控 | 每 2 秒快速检查 |

### 4. 网络配置（ROS_DOMAIN_ID）

**问题**: 多设备ROS2通信需要相同 domain

**解决方案**:
- 统一所有系统使用 **ROS_DOMAIN_ID=0**（与机器狗一致）
- 设置 `ROS_LOCALHOST_ONLY=0` 允许网络发现
- 修改所有启动脚本，在 source 前设置环境变量

**验证**:
- ✅ Jetson → 笔记本: 话题可见
- ✅ 笔记本 → Jetson: 话题可见
- ✅ 笔记本 → 机器狗: 话题可见
- ❌ Jetson → 机器狗: **话题不可见**（待解决）

### 5. 地图文件

- 复制 `12f_map.pcd` 到 `~/FAST_LIO_LOCALIZATION2/maps/`
- 地图大小: 3.1MB, 56,412 个点
- RViz 配置: `fastlio_localization.rviz` 订阅 `/cloud_pcd`

---

## ⚠️ 未解决问题

### 1. Jetson 无法发现机器狗话题 ❌

**现象**:
- 笔记本 (192.168.123.102) 能看到机器狗话题 (`/lio_sam_ros2/...`, `/utlidar/...`)
- Jetson (192.168.123.101) 看不到机器狗话题

**已尝试**:
- ✅ 设置 `ROS_DOMAIN_ID=0`
- ✅ 设置 `ROS_LOCALHOST_ONLY=0`
- ✅ 清除 DDS 缓存 (`~/.fastdds`, `/tmp/fastdds*`)
- ✅ 检查网络接口（192.168.123.101 正常）

**可能原因**:
1. 机器狗板子设置了额外的 DDS 发现限制（如 `ROS_LOCALHOST_ONLY=1`）
2. 机器狗板子有防火墙阻止入站连接
3. Jetson 的 DDS 选择了错误的网络接口
4. 机器狗和 Jetson 之间网络隔离（路由器配置）

**待排查**:
- [ ] 检查机器狗板子的 `ROS_LOCALHOST_ONLY` 值
- [ ] 在 Jetson 上测试 `ping 192.168.123.161`
- [ ] 检查 Jetson 防火墙：`sudo ufw status`
- [ ] 在 Jetson 创建 DDS 配置文件强制发现

### 2. `transform_fusion` CPU 占用高 ⚠️

**现象**: 降低频率到 10Hz 后，仍需验证是否生效

**待验证**:
- [ ] 重启后检查 `ros2 param get /transform_fusion freq_pub_localization`
- [ ] 监控 CPU 占用是否降至 20-30%

### 3. Livox 驱动警告 `sequence size exceeds remaining buffer` ⚠️

**现象**: 驱动持续输出警告

**分析**:
- 消息定义 (`CustomMsg.msg`) 未修改
- 仅是配置和 launch 文件修改
- 可能是驱动本身已知问题

**影响**:
- ⚠️ 可能导致点云数据截断
- ✅ 但点云显示正常，功能未受影响

**建议**: 如果点云质量好，可暂时忽略

### 4. 定位漂移问题 🔄

**现象**: 剧烈移动后出现跳变，之后继续漂移

**分析**:
- 跳变是全局定位重定位成功（正常）
- 但继续漂移说明校正量不足

**可能原因**:
- ICP 频率太低 (0.5Hz)
- 匹配阈值太松 (`localization_threshold: 0.8`)
- 点云降采样过粗

**待调整**:
```yaml
global_localization:
  freq_localization: 1.0        # 提高到 1Hz
  localization_threshold: 0.9   # 更严格匹配
  scan_voxel_size: 0.08         # 保留更多细节
  map_voxel_size: 0.3
```

---

## 📊 当前状态

**环境限制**: ⚠️ 剪贴板工具在 OpenCode 终端中不可用（尽管系统已安装 `xclip`/`xsel`），命令无法直接复制粘贴，需手动输入。

| 设备 | IP | 角色 | ROS_DOMAIN_ID | 状态 |
|------|-----|------|---------------|------|
| **Jetson** | 192.168.123.101 | FAST_LIO 定位系统 | **0** | ✅ 运行中 |
| **笔记本** | 192.168.123.102 | RViz 可视化 | **0** | ✅ 可显示 |
| **机器狗** | 192.168.123.161 | 机器狗系统 | **0** (假设) | ✅ 运行中 |

**网络连通性**:
- ✅ 笔记本 ↔ Jetson: 双向可见
- ✅ 笔记本 ↔ 机器狗: 双向可见
- ❌ Jetson ↔ 机器狗: **单向不可见**（待解决）

**话题发布**:
- ✅ `/cloud_pcd` - 地图 (0.33Hz)
- ✅ `/livox/lidar` - 雷达输入 (10Hz)
- ✅ `/Odometry` - 里程计 (~11Hz)
- ⏳ `/localization` - 等待初始位姿
- ❌ 机器狗话题 - Jetson 不可见

**终端限制**:
- ⚠️ OpenCode 终端无法复制粘贴（剪贴板不可用）
- ✅ 系统已安装 `xclip` `xsel`
- ✅ 在图形化终端可正常使用

---

## 🎯 下一步计划

### 优先级 1: 解决 Jetson → 机器狗 通信

1. **获取机器狗板子 ROS_DOMAIN_ID** (需要密码或远程协助)
2. **检查机器狗防火墙** (`sudo ufw allow 7400:7500/udp`)
3. **在 Jetson 创建 DDS 配置文件**强制发现所有节点
4. **测试 ping 和端口连通性** (`nc -zv 192.168.123.161 7400`)

### 优先级 2: 优化定位性能

1. 重启系统验证 `transform_fusion` 频率修改
2. 调整 `global_localization` 参数（提高频率和阈值）
3. 测试移动机器人，观察漂移是否改善

### 优先级 3: 功能验证

1. 在笔记本 RViz 中发布初始位姿
2. 观察 `/localization` 输出是否稳定
3. 对比 `/Odometry` 和 `/localization` 差异（验证重定位效果）

---

## 📝 调试命令速查

### 环境设置
```bash
export ROS_DOMAIN_ID=0
export ROS_LOCALHOST_ONLY=0
source ~/FAST_LIO_LOCALIZATION2/install/setup.bash
```

### 启动系统
```bash
# Jetson 终端1: 雷达
cd ~/FAST_LIO_LOCALIZATION2
./start_livox.sh

# Jetson 终端2: 定位
./start_without_rviz.sh

# 笔记本终端: RViz
rviz2 -d ~/fastlio_localization.rviz
```

### 监控
```bash
# 快速监控
./monitor_fast.sh

# 查看节点
ros2 node list

# 查看话题频率
ros2 topic hz /Odometry
ros2 topic hz /localization
```

### 停止所有进程
```bash
pkill -9 -f "fastlio_mapping"
pkill -9 -f "global_localization"
pkill -9 -f "transform_fusion"
pkill -9 -f "livox_ros_driver2"
```

---

## 🔧 已知问题记录

| 问题 | 影响 | 解决方案 | 状态 |
|------|------|----------|------|
| `sequence size exceeds remaining buffer` | 点云可能截断 | 暂时忽略，功能正常 | ⚠️ 待修复 |
| `transform_fusion` CPU 140% | TF 卡顿 | 降低频率到 10Hz | ✅ 已修改 |
| Open3D 警告 | 日志刷屏 | 添加 warnings 过滤 | ✅ 已修复 |
| 剪贴板工具 | OpenCode 无法复制 | 已安装 `xclip` `xsel` | ✅ 已安装 |
| Jetson 看不到机器狗 | 无法统一显示 | 待排查 DDS 配置 | ❌ 待解决 |

---

## 📈 性能指标

| 指标 | 值 | 说明 |
|------|-----|------|
| `fastlio_mapping` CPU | ~40% | 正常（ICP计算） |
| `global_localization` CPU | ~20% | 正常 |
| `transform_fusion` CPU | ~140% | 过高（待验证修改后） |
| `livox_ros_driver2` CPU | ~40% | 正常 |
| `/Odometry` 频率 | ~11 Hz | 正常 |
| `/localization` 频率 | 0 Hz | 未启动/未定位 |
| 内存占用 | ~580MB | 正常 |

---

## 📚 参考资源

- [FAST-LIO2 论文](https://github.com/hku-mars/FAST_LIO)
- [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2)
- [ROS2 DDS 配置](https://docs.ros.org/en/humble/How-To-Guides/DDS-Configuration.html)

---

**最后更新**: 2026-04-10 17:00 CST  
**下次调试**: 待解决 Jetson → 机器狗 通信问题
