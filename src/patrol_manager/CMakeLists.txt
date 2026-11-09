cmake_minimum_required(VERSION 3.8)
project(patrol_manager)

# 当前任务管理器使用 C++17。
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找构建工具和节点代码使用的 ROS2 库。
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(nav2_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(lifecycle_msgs REQUIRED)
find_package(patrol_interfaces REQUIRED)

# 编译巡检与事件响应任务管理器。
add_executable(mission_manager src/mission_node.cpp)
target_include_directories(mission_manager PRIVATE include)
ament_target_dependencies(mission_manager rclcpp rclcpp_action geometry_msgs std_srvs
  nav2_msgs nav_msgs std_msgs lifecycle_msgs patrol_interfaces)

# 将程序安装到 ROS2 可以通过 ros2 run 找到的位置。
install(TARGETS mission_manager
  DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY include/ DESTINATION include)
include(CTest)
if(BUILD_TESTING)
  enable_testing()
  add_executable(test_mission test/test_mission.cpp)
  target_include_directories(test_mission PRIVATE include)
  add_test(NAME mission_core COMMAND test_mission)
endif()

ament_package()
