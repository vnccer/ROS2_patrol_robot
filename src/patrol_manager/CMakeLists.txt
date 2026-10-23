cmake_minimum_required(VERSION 3.8)
project(patrol_manager)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找构建工具和节点代码使用的 ROS2 库。
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

# 把源文件编译成名为 patrol_node 的可执行程序。
add_executable(patrol_node src/patrol_node.cpp)
ament_target_dependencies(patrol_node rclcpp)

# 将程序安装到 ROS2 可以通过 ros2 run 找到的位置。
install(TARGETS patrol_node
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
