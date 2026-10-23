#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"

// 自己的节点类，继承 ROS2 节点的基本能力。

class PatrolNode : public rclcpp::Node
{
public:
  // 创建对象时执行构造函数，先用 node_name 初始化父类节点。
  explicit PatrolNode(const std::string &node_name)
  : Node(node_name)
  {
    RCLCPP_INFO(this->get_logger(), "Patrol node started.");
  }
};

int main(int argc, char **argv)
{
  // 初始化 ROS2，随后创建自己的节点对象。
  rclcpp::init(argc, argv);
  auto node = std::make_shared<PatrolNode>("patrol_node");

  // 等待并处理回调，直到收到退出请求，例如按下 Ctrl+C。
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
