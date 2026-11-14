#include <memory>
#include <string>
#include <chrono>
#include "std_msgs/msg/string.hpp"
#include "rclcpp/rclcpp.hpp"
#include "patrol_interfaces/msg/mission_status.hpp"

// 自己的节点类，继承 ROS2 节点的基本能力。
class PatrolNode : public rclcpp::Node
{
public:
  // 创建对象时执行构造函数，先用 node_name 初始化父类节点。
  explicit PatrolNode(const std::string &node_name) : Node(node_name)
  {
    RCLCPP_INFO(this->get_logger(), "Patrol node started.");

    // 创建状态订阅(/patrol/status是节点的输入topic)
    status_sub_ = this->create_subscription<patrol_interfaces::msg::MissionStatus>(
      "/patrol/status", 10,
      [this](patrol_interfaces::msg::MissionStatus::ConstSharedPtr m)
      {
        on_status(m); // 调用刚刚写好的private中的状态订阅成员函数，把m传进入
      }
    );

    // 创建摘要发布器(/patrol/summary是节点的输出topic)
    summary_pub_ = this->create_publisher<std_msgs::msg::String>(
      "/patrol/summary", 10 //指定了向/patrol/summary主题发布消息，队列长度为10
    );

    // 创建定时器，每隔1秒调用一次publish_summary函数
    summary_timer_ = this->create_wall_timer( // this表示当前的PatrolNode对象，create_wall_timer是ROS2的定时器函数
      std::chrono::seconds(1), // C++标准库::时间相关功能::秒类型(1s)
      [this]()
      {
        publish_summary(); // 到时间后调用publish_summary函数
      }
    );
  }

private:
  // 状态订阅的成员变量
  rclcpp::Subscription<patrol_interfaces::msg::MissionStatus>::SharedPtr status_sub_; // 保存订阅对象的成员变量
  std::string last_state_; // 保存上一次的状态，避免重复打印
  unsigned int status_received_count_{0}; // 保存收到过多少条状态消息
  patrol_interfaces::msg::MissionStatus::ConstSharedPtr last_status_; // 保存上一次的完整状态消息

  // 定时摘要发布的成员变量
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr summary_pub_; // 保存发布器对象
  rclcpp::TimerBase::SharedPtr summary_timer_; // 保存定时器对象
  bool has_status_{false}; // 是否已经收到过状态消息


  // 状态回调函数，处理收到的状态消息
  void on_status(patrol_interfaces::msg::MissionStatus::ConstSharedPtr m) {
    ++status_received_count_; // 接收计数加一
    last_status_ = m; // 把这次消息保存到 last_status_
    has_status_ = true; // 把“收到过消息”的标志设为真
    if (m->state != last_state_) // 比较状态名，发生变化时打印日志并更新 last_state_
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

  // 定时器回调函数，用于发布状态摘要
  void publish_summary(){
    std_msgs::msg::String msg; // 先准备一个空的消息对象，其中有字段data用于保存字符串
    if (!has_status_){
      msg.data = "NO_STATUS";
    } else {
      msg.data =
        "state=" + last_status_->state +
        " active_id=" + last_status_->active_id +
        " queue_size=" + std::to_string(last_status_->queue_size) +
        " received=" + std::to_string(status_received_count_);
    }
    summary_pub_->publish(msg); // 让summary_pub_指向的发布器调用它的publish函数，发布msg消息
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
