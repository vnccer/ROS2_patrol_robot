#include <memory>
#include <string>
#include <chrono>

#include "std_msgs/msg/string.hpp"
#include "rclcpp/rclcpp.hpp"

class PatrolNode : public rclcpp::Node {
public:
    explicit PatrolNode(const std::string &node_name) : Node(node_name) {
        RCLCPP_INFO(this->get_logger(), "Patrol node started");
    }
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<PatrolNode>("patrol_node");
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}