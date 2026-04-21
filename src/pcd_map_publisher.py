#!/usr/bin/env python3
import io
from typing import Dict, List, Tuple

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField


TYPE_TO_NUMPY = {
    ("F", 4): np.float32,
    ("F", 8): np.float64,
    ("I", 1): np.int8,
    ("I", 2): np.int16,
    ("I", 4): np.int32,
    ("I", 8): np.int64,
    ("U", 1): np.uint8,
    ("U", 2): np.uint16,
    ("U", 4): np.uint32,
    ("U", 8): np.uint64,
}

TYPE_TO_ROS = {
    ("I", 1): PointField.INT8,
    ("U", 1): PointField.UINT8,
    ("I", 2): PointField.INT16,
    ("U", 2): PointField.UINT16,
    ("I", 4): PointField.INT32,
    ("U", 4): PointField.UINT32,
    ("F", 4): PointField.FLOAT32,
    ("F", 8): PointField.FLOAT64,
}


def _parse_pcd_header(raw: bytes) -> Tuple[Dict[str, str], int]:
    header: Dict[str, str] = {}
    stream = io.BytesIO(raw)
    offset = 0

    while True:
        line = stream.readline()
        if not line:
            raise RuntimeError("Invalid PCD: missing DATA line")
        offset += len(line)
        stripped = line.decode("utf-8", errors="ignore").strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(maxsplit=1)
        key = parts[0].upper()
        value = parts[1] if len(parts) > 1 else ""
        header[key] = value
        if key == "DATA":
            break
    return header, offset


def _build_layout(header: Dict[str, str]) -> Tuple[np.dtype, List[PointField], int]:
    fields = header.get("FIELDS", "").split()
    sizes = [int(v) for v in header.get("SIZE", "").split()]
    types = header.get("TYPE", "").split()
    counts = [int(v) for v in header.get("COUNT", "").split()] if "COUNT" in header else [1] * len(fields)

    if not fields or not (len(fields) == len(sizes) == len(types) == len(counts)):
        raise RuntimeError("Invalid PCD header: FIELDS/SIZE/TYPE/COUNT mismatch")

    dtype_fields = []
    ros_fields: List[PointField] = []
    offset = 0

    for name, size, type_code, count in zip(fields, sizes, types, counts):
        key = (type_code, size)
        if key not in TYPE_TO_NUMPY or key not in TYPE_TO_ROS:
            raise RuntimeError(f"Unsupported PCD field type: {type_code}{size} for field {name}")
        base_dtype = np.dtype(TYPE_TO_NUMPY[key])
        if count == 1:
            dtype_fields.append((name, base_dtype))
        else:
            dtype_fields.append((name, base_dtype, (count,)))

        ros_fields.append(
            PointField(
                name=name,
                offset=offset,
                datatype=TYPE_TO_ROS[key],
                count=count,
            )
        )
        offset += size * count

    return np.dtype(dtype_fields, align=False), ros_fields, offset


def load_pcd_as_pointcloud2(path: str, frame_id: str) -> PointCloud2:
    with open(path, "rb") as f:
        raw = f.read()

    header, data_offset = _parse_pcd_header(raw)
    np_dtype, ros_fields, point_step = _build_layout(header)

    width = int(header.get("WIDTH", "0"))
    height = int(header.get("HEIGHT", "1"))
    points = int(header.get("POINTS", "0")) if "POINTS" in header else width * height
    if points <= 0:
        points = width * height
    if points <= 0:
        raise RuntimeError("Invalid PCD header: points/width/height cannot be zero")

    data_type = header.get("DATA", "").strip().lower()
    payload = raw[data_offset:]

    if data_type == "ascii":
        text = payload.decode("utf-8", errors="ignore")
        matrix = np.loadtxt(io.StringIO(text), dtype=np.float64)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        expected_cols = int(sum(int(v) for v in header.get("COUNT", "").split())) if "COUNT" in header else len(ros_fields)
        if matrix.shape[1] != expected_cols:
            raise RuntimeError(f"ASCII PCD columns mismatch: got {matrix.shape[1]}, expect {expected_cols}")
        if matrix.shape[0] != points:
            points = matrix.shape[0]
            width = points
            height = 1

        structured = np.zeros(points, dtype=np_dtype)
        col_idx = 0
        for field in ros_fields:
            name = field.name
            count = int(field.count)
            if count == 1:
                structured[name] = matrix[:, col_idx].astype(structured[name].dtype, copy=False)
            else:
                structured[name] = matrix[:, col_idx:col_idx + count].astype(structured[name].dtype, copy=False)
            col_idx += count
        data_bytes = structured.tobytes()
    elif data_type == "binary":
        expected_bytes = points * point_step
        if len(payload) < expected_bytes:
            raise RuntimeError(f"Binary PCD data too short: {len(payload)} < {expected_bytes}")
        structured = np.frombuffer(payload[:expected_bytes], dtype=np_dtype, count=points)
        data_bytes = structured.tobytes()
    else:
        raise RuntimeError(f"Unsupported PCD DATA type: {data_type}")

    msg = PointCloud2()
    msg.header.frame_id = frame_id
    msg.height = height
    msg.width = width
    msg.fields = ros_fields
    msg.is_bigendian = False
    msg.point_step = point_step
    msg.row_step = point_step * width
    msg.is_dense = True
    msg.data = data_bytes
    return msg


class PcdMapPublisher(Node):
    def __init__(self) -> None:
        super().__init__("pcd_map_publisher")

        self.declare_parameter("file_name", "")
        self.declare_parameter("tf_frame", "map")
        self.declare_parameter("cloud_topic", "cloud_pcd")
        self.declare_parameter("publishing_period_ms", 3000)
        # Compatibility with existing launch files.
        self.declare_parameter("period_ms_", 0)

        file_name = self.get_parameter("file_name").get_parameter_value().string_value
        tf_frame = self.get_parameter("tf_frame").get_parameter_value().string_value
        cloud_topic = self.get_parameter("cloud_topic").get_parameter_value().string_value
        publishing_period_ms = int(self.get_parameter("publishing_period_ms").value)
        period_ms_compat = int(self.get_parameter("period_ms_").value)
        if period_ms_compat > 0:
            publishing_period_ms = period_ms_compat

        if not file_name:
            raise RuntimeError("Parameter 'file_name' is required")

        self.cloud_msg = load_pcd_as_pointcloud2(file_name, tf_frame)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.pub = self.create_publisher(PointCloud2, cloud_topic, qos)
        self.timer = self.create_timer(publishing_period_ms / 1000.0, self._publish)

        self.get_logger().info(
            f"Loaded PCD once from '{file_name}', publishing on '{cloud_topic}' every {publishing_period_ms} ms."
        )
        self._publish()

    def _publish(self) -> None:
        self.cloud_msg.header.stamp = self.get_clock().now().to_msg()
        self.pub.publish(self.cloud_msg)


def main() -> None:
    rclpy.init()
    node = PcdMapPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
