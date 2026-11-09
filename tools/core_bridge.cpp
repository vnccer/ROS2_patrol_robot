// Portable preview adapter. The scheduler is exactly the ROS manager's mission.hpp.
#include "patrol_manager/mission.hpp"
#include <iostream>
#include <sstream>

static std::string json(const std::string &s) {
  std::string out="\"";
  for(unsigned char c:s) {
    if(c=='"'||c=='\\') {out+='\\'; out+=static_cast<char>(c);}
    else if(c>=32) out+=static_cast<char>(c);
  }
  return out+'"';
}
int main() {
  patrol::Config config; config.waypoints={{1,1,0},{7,1,1.57},{7,7,3.14},{1,7,-1.57}};
  patrol::Mission m(config);
  std::string line;
  while(std::getline(std::cin,line)) {
    std::istringstream in(line); std::string op; double now=0; in>>op>>now;
    if(op=="tick") {bool ready=true; in>>ready; m.tick(now,ready);}
    else if(op=="event") {
      patrol::Task t; in>>t.id>>t.priority>>t.pose.x>>t.pose.y>>t.expires>>t.handling;
      m.submit(t,now);
    }
    else if(op=="result") {uint64_t token=0;bool success=false;in>>token>>success;m.result(token,success,now);}
    else if(op=="pause") {bool paused=false;in>>paused;m.pause(paused,now);}
    else if(op=="trip") {std::string reason;std::getline(in,reason);m.trip(reason,now);}
    else if(op=="recover") {bool healthy=false;in>>healthy;m.recover(healthy);}
    else if(op=="config") {double timeout=90,dwell=1;in>>timeout>>dwell;if(timeout>=1&&dwell>=0){m.cfg.goal_timeout=timeout;m.cfg.patrol_dwell=dwell;}}
    std::cout<<"{\"status\":{\"state\":"<<json(m.state())<<",\"active_id\":"<<json(m.active?m.active->id:"")
      <<",\"active_priority\":"<<(m.active?m.active->priority:0)<<",\"patrol_index\":"<<m.patrol_index
      <<",\"queue_size\":"<<m.queue.size()<<",\"patrol_completed\":"<<m.patrol_completed
      <<",\"events_completed\":"<<m.events_completed<<",\"tasks_failed\":"<<m.tasks_failed
      <<",\"paused\":"<<(m.paused?"true":"false")<<",\"motion_permitted\":"<<(m.permit()?"true":"false")
      <<",\"fault\":"<<json(m.fault)<<"},\"effects\":[";
    bool first=true;
    for(const auto &e:m.drain()) {
      if(!first) std::cout<<',';
      first=false;
      std::cout<<"{\"type\":"<<e.kind<<",\"token\":"<<e.token<<",\"id\":"<<json(e.task.id)
        <<",\"x\":"<<e.task.pose.x<<",\"y\":"<<e.task.pose.y<<",\"yaw\":"<<e.task.pose.yaw
        <<",\"kind\":"<<json(e.name)<<",\"detail\":"<<json(e.detail)<<",\"value\":"<<e.value<<'}';
    }
    std::cout<<"]}"<<std::endl;
  }
}
