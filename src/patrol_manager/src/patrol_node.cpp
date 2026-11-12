#include <memory>
#include <string>
#include "patrol_interfaces/msg/mission_status.hpp"

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
    // 创建订阅
    status_sub_ = this->create_subscription<patrol_interfaces::msg::MissionStatus>(
      "/patrol/status",
      10,
      [this](patrol_interfaces::msg::MissionStatus::ConstSharedPtr m)
      {
        // 调用刚刚写好的private中的订阅成员函数，把m传进入
        on_status(m);
      }
    );
  }

private:
  
  std::string last_state_; // 保存上一次的状态，避免重复打印
  rclcpp::Subscription<patrol_interfaces::msg::MissionStatus>::SharedPtr status_sub_; // 保存订阅对象的成员变量
  unsigned int status_received_count_{0}; // 保存收到过多少条状态消息
  patrol_interfaces::msg::MissionStatus::ConstSharedPtr last_status_; // 保存上一次的完整状态消息

  // 处理收到的状态消息
  void on_status(patrol_interfaces::msg::MissionStatus::ConstSharedPtr m) {
    ++status_received_count_;
    last_status_ = m; // 保存最新的状态消息
    if (m->state != last_state_)
    {
      // 打印收到的状态
      RCLCPP_INFO(
        this->get_logger(),
        "received=%u state=%s",
        status_received_count_,
        m->state.c_str()
      );
      // 保存当前状态，供下一次回调比较
      last_state_ = m->state;
    }
  }
}; // 整个class类结束，需要分号闭合

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
