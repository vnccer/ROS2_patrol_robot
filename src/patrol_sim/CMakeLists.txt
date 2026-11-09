cmake_minimum_required(VERSION 3.19)
project(patrol_sim)
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
ament_python_install_package(${PROJECT_NAME})
# Windows transfers may drop executable bits. Install links to prepared build copies
# with explicit permissions, while the Python package itself remains symlinked.
set(patrol_node_scripts "")
foreach(script lightweight_sim velocity_guard control_panel)
  set(prepared "${CMAKE_CURRENT_BINARY_DIR}/scripts/${script}")
  configure_file("scripts/${script}" "${prepared}" COPYONLY)
  file(CHMOD "${prepared}" PERMISSIONS
    OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE)
  list(APPEND patrol_node_scripts "${prepared}")
endforeach()
install(PROGRAMS ${patrol_node_scripts} DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY web DESTINATION share/${PROJECT_NAME})
ament_package()
