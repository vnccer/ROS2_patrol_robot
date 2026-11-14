#include <memory>
#include <string>
#include <chrono>
#include "std_msgs/msg/string.hpp"
#include "rclcpp/rclcpp.hpp"
#include "patrol_interfaces/msg/mission_status.hpp"
#include "std_srvs/srv/trigger.hpp"

// 自己的节点类，继承 ROS2 节点的基本能力。
class PatrolNode : public rclcpp::Node
{
public:
  explicit PatrolNode(const std::string &node_name) : Node(node_name)
  {
    RCLCPP_INFO(this->get_logger(), "Patrol node started.");

    // 创建状态订阅器
    status_sub_ = this->create_subscription<patrol_interfaces::msg::MissionStatus>(
      "/patrol/status", 10,
      [this](patrol_interfaces::msg::MissionStatus::ConstSharedPtr m)
      {
        on_status(m); // 调用刚刚写好的private中的状态订阅成员函数，把m传进入
      }
    );

    // 创建摘要发布器
    summary_pub_ = this->create_publisher<std_msgs::msg::String>(
      "/patrol/summary", 10 //指定了向/patrol/summary主题发布消息，队列长度为10
    );

    // 创建定时器
    summary_timer_ = this->create_wall_timer( // this表示当前的PatrolNode对象，create_wall_timer是ROS2的定时器函数
      std::chrono::seconds(1), // C++标准库::时间相关功能::秒类型(1s)
      [this]()
      {
        publish_summary(); // 到时间后调用publish_summary函数
      }
    );

    // 创建清零统计服务
    reset_count_service_ = this->create_service<std_srvs::srv::Trigger>(
      "/patrol/monitor/reset_count",
      [this](
        std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response)
      {
        status_received_count_ = 0;
        response->success = true;
        response->message = "Status received reset.";
      }
    );

  }

private:
  rclcpp::Subscription<patrol_interfaces::msg::MissionStatus>::SharedPtr status_sub_; // 保存订阅对象
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr summary_pub_; // 保存发布器对象
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr reset_count_service_; // 保存服务对象
  rclcpp::TimerBase::SharedPtr summary_timer_; // 保存定时器对象
  std::string last_state_; // 保存上一次的状态，避免重复打印
  unsigned int status_received_count_{0}; // 保存收到过多少条状态消息
  patrol_interfaces::msg::MissionStatus::ConstSharedPtr last_status_; // 保存上一次的完整状态消息
  bool has_status_{false}; // 是否已经收到过状态消息

  // 状态回调函数，处理收到的状态消息，累加计数、保存最新消息、比较状态名是否变化，若变化则打印received和state
  void on_status(patrol_interfaces::msg::MissionStatus::ConstSharedPtr m) {
    ++status_received_count_;
    last_status_ = m;
    has_status_ = true;
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
