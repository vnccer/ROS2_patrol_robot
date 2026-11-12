#include <chrono>
#include <csignal>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <unistd.h>
#include "patrol_manager/mission.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "nav2_msgs/action/navigate_to_pose.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_srvs/srv/set_bool.hpp"
#include "std_srvs/srv/trigger.hpp"
#include "lifecycle_msgs/srv/get_state.hpp"
#include "patrol_interfaces/msg/incident.hpp"
#include "patrol_interfaces/msg/mission_status.hpp"
#include "patrol_interfaces/msg/task_record.hpp"

// 三个using让后面的写法更简短
using namespace std::chrono_literals; // 允许写50ms
using Nav = nav2_msgs::action::NavigateToPose; // 起别名Nav
using Handle = rclcpp_action::ClientGoalHandle<Nav>; // 起别名 Handle

// A signal only requests exit. Keep ROS valid until the current callback ends.
static volatile std::sig_atomic_t stop_requested = 0;
static void request_stop(int) { stop_requested = 1; }

// 两个static定义仅供当前.cpp文件使用的辅助函数
static double wall_now() { //wall_now()返回单调时钟的秒数
  return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
static std::string csv(const std::string &s) { //csv()给字符串加引号，并处理内部引号，方便正确写入CSV文件
  std::string o="\""; for (char c:s) {if(c=='"')o+='"'; o+=c;} return o+'"';
}

// ROS 适配层：接警、调用 Nav2、记录结果；任务切换规则位于 mission.hpp。
/*
public和private的访问权限不同，public类外部可以访问，private类外部不能直接访问
  public中只有一个构造函数MissionNode：读取设置、创建任务管理核心、准备日至文件、建立ROS2通信、启动定时器
  private有两类内容：
    一类是运行过程中需要一直保存的东西
    另一类是管理员内部使用的工作函数

两者配合例如：
  // public 的构造函数里：安排每隔 50ms 做一次检查
  timer_ = create_wall_timer(50ms, [this]{ tick(); });
  // private 里：具体写“检查时要做什么”
  void tick() {
    // 检查、处理任务、记录日志……
  }
*/
class MissionNode : public rclcpp::Node {
public:
  MissionNode(): Node("mission_manager") {
    patrol::Config c;
    auto points=declare_parameter<std::vector<double>>("waypoints",{1.,1.,0.,7.,1.,0.,7.,7.,0.,1.,7.,0.});
    if(points.empty() || points.size()%3) throw std::runtime_error("waypoints must be x,y,yaw triples");
    for(size_t i=0;i<points.size();i+=3) {
      for(size_t j=i;j<i+3;++j) if(!std::isfinite(points[j])) throw std::runtime_error("nonfinite waypoint");
      c.waypoints.push_back({points[i],points[i+1],points[i+2]});
    }
    c.patrol_dwell=declare_parameter("patrol_dwell_sec",1.0);
    c.goal_timeout=declare_parameter("goal_timeout_sec",90.0);
    c.cancel_timeout=declare_parameter("cancel_timeout_sec",3.0);
    auto retries=declare_parameter("max_retries",1);
    auto queue_size=declare_parameter("max_queue",64);
    if(retries<0 || retries>10 || queue_size<1 || queue_size>1000 || c.patrol_dwell<0)
      throw std::runtime_error("invalid mission limits");
    c.max_retries=static_cast<unsigned>(retries); c.max_queue=static_cast<unsigned>(queue_size);
    odom_timeout_=declare_parameter("odom_timeout_sec",1.0);
    frame_=declare_parameter<std::string>("global_frame","map");
    if(odom_timeout_<=0) throw std::runtime_error("invalid odometry timeout");
    mission_=std::make_unique<patrol::Mission>(c);
    std::string root=declare_parameter<std::string>("log_directory","");
    if(root.empty()) {
      const char *home=std::getenv("HOME"); root=std::string(home?home:"/tmp")+"/.ros/patrol_runs";
    }
    auto epoch=std::chrono::system_clock::now().time_since_epoch();
    auto run=std::to_string(std::chrono::duration_cast<std::chrono::milliseconds>(epoch).count())+"-"+std::to_string(getpid());
    std::filesystem::create_directories(root+"/"+run);
    log_.open(root+"/"+run+"/records.csv");
    if(!log_) throw std::runtime_error("cannot open audit log");
    log_<<"ros_sec,monotonic_sec,kind,task_id,detail,value\n";
    RCLCPP_INFO(get_logger(),"Audit: %s/%s/records.csv",root.c_str(),run.c_str());

    nav_=rclcpp_action::create_client<Nav>(this,"navigate_to_pose");
    lifecycle_=create_client<lifecycle_msgs::srv::GetState>("bt_navigator/get_state");
    status_=create_publisher<patrol_interfaces::msg::MissionStatus>("patrol/status",10);
    record_=create_publisher<patrol_interfaces::msg::TaskRecord>("patrol/records",100);
    permit_=create_publisher<std_msgs::msg::Bool>("patrol/motion_permit",10);
    odom_=create_subscription<nav_msgs::msg::Odometry>("odom",rclcpp::SensorDataQoS(),
      [this](nav_msgs::msg::Odometry::ConstSharedPtr m){
        const auto &p=m->pose.pose.position; const auto &q=m->pose.pose.orientation;
        double norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w;
        if(std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(norm)&&norm>0.5&&norm<1.5) {
          last_odom_=wall_now(); seen_odom_=true;
        }
      });
    incidents_=create_subscription<patrol_interfaces::msg::Incident>("patrol/incidents",50,
      [this](patrol_interfaces::msg::Incident::ConstSharedPtr m){
        on_incident(m);
      });
    pause_=create_service<std_srvs::srv::SetBool>("patrol/set_paused",
      [this](std_srvs::srv::SetBool::Request::SharedPtr req,std_srvs::srv::SetBool::Response::SharedPtr res){
        mission_->pause(req->data,wall_now()); publish_permit();
        res->success=true; res->message="Pause updated; status confirms navigation cancellation.";
      });
    estop_=create_service<std_srvs::srv::Trigger>("patrol/emergency_stop",
      [this](std_srvs::srv::Trigger::Request::SharedPtr,std_srvs::srv::Trigger::Response::SharedPtr res){
        mission_->trip("operator emergency stop",wall_now()); publish_permit();
        res->success=true; res->message="Fault latched; use recover after checking health.";
      });
    shutdown_=create_service<std_srvs::srv::Trigger>("patrol/prepare_shutdown",
      [this](std_srvs::srv::Trigger::Request::SharedPtr,std_srvs::srv::Trigger::Response::SharedPtr res){
        mission_->pause(true,wall_now()); publish_permit();
        // A pause acknowledgement alone does not mean the action has finished.
        res->success=!mission_->flying;
        res->message=res->success?"Ready to shut down.":"Waiting for navigation cancellation.";
      });
    recover_=create_service<std_srvs::srv::Trigger>("patrol/recover",
      [this](std_srvs::srv::Trigger::Request::SharedPtr,std_srvs::srv::Trigger::Response::SharedPtr res){
        res->success=mission_->recover(healthy()&&nav_ready());
        res->message=res->success?"Fault cleared; manual pause preserved.":"Need fresh odometry, active Nav2 and a terminal old goal.";
      });
    parameters_=add_on_set_parameters_callback([this](const std::vector<rclcpp::Parameter>& ps){
      rcl_interfaces::msg::SetParametersResult r; r.successful=true;
      for(const auto &p:ps) {
        if(p.get_name()!="patrol_dwell_sec"&&p.get_name()!="goal_timeout_sec") {
          r.successful=false; r.reason="Only dwell and goal timeout are live editable; restart for other settings."; return r;
        }
        if(p.get_type()!=rclcpp::ParameterType::PARAMETER_DOUBLE || !std::isfinite(p.as_double()) ||
          p.as_double()<(p.get_name()=="goal_timeout_sec"?1.:0.) || p.as_double()>3600) {
          r.successful=false; r.reason="Invalid numeric range"; return r;
        }
      }
      for(const auto &p:ps) {
        if(p.get_name()=="patrol_dwell_sec") mission_->cfg.patrol_dwell=p.as_double();
        else mission_->cfg.goal_timeout=p.as_double();
      }
      return r;
    });
    // 单线程执行器串行处理回调，核心状态无需跨线程锁。
    timer_=create_wall_timer(50ms,[this]{tick();});
  }
private:
  std::unique_ptr<patrol::Mission> mission_;
  rclcpp_action::Client<Nav>::SharedPtr nav_;
  Handle::SharedPtr handle_;
  rclcpp::Client<lifecycle_msgs::srv::GetState>::SharedPtr lifecycle_;
  rclcpp::Publisher<patrol_interfaces::msg::MissionStatus>::SharedPtr status_;
  rclcpp::Publisher<patrol_interfaces::msg::TaskRecord>::SharedPtr record_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr permit_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_;
  rclcpp::Subscription<patrol_interfaces::msg::Incident>::SharedPtr incidents_;
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr pause_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr estop_,recover_,shutdown_;
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr parameters_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::ofstream log_;
  bool seen_odom_{false}, life_active_{false}, life_pending_{false};
  double last_odom_{0}, odom_timeout_{1}, life_poll_{0}, life_reply_{0};
  int64_t life_request_id_{0};
  std::string frame_;
  bool healthy() const {return seen_odom_&&wall_now()-last_odom_<odom_timeout_;}
  bool nav_ready() const {return life_active_&&wall_now()-life_reply_<3&&nav_->action_server_is_ready();} 
  // 计数器成员变量
  unsigned int incident_received_count_{0};
  
  // 报警处理提取成成员函数
  void on_incident(patrol_interfaces::msg::Incident::ConstSharedPtr m) {
    ++incident_received_count_;
    RCLCPP_INFO(
      get_logger(),
      "received=%u id=%s priority=%d",
      incident_received_count_,
      m->id.c_str(),
      m->priority
    );
    auto &q=m->target.pose.orientation;
    double norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w;
    if(m->target.header.frame_id!=frame_ || !std::isfinite(norm) || std::abs(norm-1)>0.05) {
      mission_->record("rejected","坐标系必须为map, 姿态四元数必须经过归一化",0,m->id); return;
    }
    patrol::Task t; t.id=m->id; t.priority=m->priority;
    t.pose={m->target.pose.position.x,m->target.pose.position.y,
      std::atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))};
    t.expires=m->ttl_sec; t.handling=m->handling_sec;
    mission_->submit(t,wall_now());
  }

  void publish_permit() {
    std_msgs::msg::Bool m; m.data=mission_->permit()&&healthy()&&nav_ready(); permit_->publish(m);
  }
  void cancel() {
    if(!handle_) return; // 等待 goal_response 后立即取消。
    try {nav_->async_cancel_goal(handle_);} catch(const std::exception &e) {mission_->trip(e.what(),wall_now());}
  }
  void start(const patrol::Effect &e) {
    Nav::Goal goal;
    goal.pose.header.frame_id=frame_; goal.pose.header.stamp=now();
    goal.pose.pose.position.x=e.task.pose.x; goal.pose.pose.position.y=e.task.pose.y;
    goal.pose.pose.orientation.z=std::sin(e.task.pose.yaw/2);
    goal.pose.pose.orientation.w=std::cos(e.task.pose.yaw/2);
    const auto token=e.token;
    auto options=rclcpp_action::Client<Nav>::SendGoalOptions();
    options.goal_response_callback=[this,token](Handle::SharedPtr h){
      if(token!=mission_->token) return;
      handle_=h;
      if(!h) mission_->result(token,false,wall_now());
      else if(mission_->cancelling) cancel();
    };
    options.result_callback=[this,token](const Handle::WrappedResult &r){
      if(token!=mission_->token) return;
      handle_.reset(); mission_->result(token,r.code==rclcpp_action::ResultCode::SUCCEEDED,wall_now());
    };
    try {nav_->async_send_goal(goal,options);}
    catch(const std::exception &err) {
      mission_->result(token,false,wall_now()); mission_->trip(err.what(),wall_now());
    }
  }
  void tick() {
    const double t=wall_now();
    if(life_pending_ && t-life_poll_>2) {
      lifecycle_->remove_pending_request(life_request_id_); life_pending_=false; life_active_=false;
    }
    if(t-life_poll_>1 && !life_pending_ && lifecycle_->service_is_ready()) {
      life_pending_=true; life_poll_=t;
      auto request=lifecycle_->async_send_request(std::make_shared<lifecycle_msgs::srv::GetState::Request>(),
        [this](rclcpp::Client<lifecycle_msgs::srv::GetState>::SharedFuture f){
          life_pending_=false; life_reply_=wall_now(); life_active_=f.get()->current_state.id==3;
        });
      life_request_id_=request.request_id;
    }
    if(seen_odom_&&!healthy()) mission_->trip("odometry timeout",t);
    if(mission_->flying && !nav_ready()) mission_->trip("Nav2 lifecycle or server lost",t);
    mission_->tick(t,healthy()&&nav_ready());
    for(const auto &e:mission_->drain()) {
      if(e.kind==patrol::Effect::Start) start(e);
      else if(e.kind==patrol::Effect::Cancel) cancel();
      else {
        patrol_interfaces::msg::TaskRecord m;
        m.stamp=now(); m.monotonic_sec=t; m.kind=e.name; m.task_id=e.task.id; m.detail=e.detail; m.value=e.value;
        record_->publish(m);
        log_<<std::setprecision(15)<<now().seconds()<<','<<t<<','<<csv(e.name)<<','<<csv(e.task.id)<<','<<csv(e.detail)<<','<<e.value<<'\n';
        log_.flush(); RCLCPP_INFO(get_logger(),"%s %s %s",e.name.c_str(),e.task.id.c_str(),e.detail.c_str());
      }
    }
    if(!log_) mission_->trip("audit log write failed",t);
    publish_permit();
    patrol_interfaces::msg::MissionStatus s; s.stamp=now(); s.state=mission_->state();
    if(mission_->active) {s.active_id=mission_->active->id; s.active_priority=static_cast<uint8_t>(mission_->active->priority);}
    s.patrol_index=static_cast<uint32_t>(mission_->patrol_index); s.queue_size=static_cast<uint32_t>(mission_->queue.size());
    s.patrol_completed=mission_->patrol_completed; s.events_completed=mission_->events_completed;
    s.tasks_failed=mission_->tasks_failed; s.paused=mission_->paused; s.fault=mission_->fault;
    s.motion_permitted=mission_->permit()&&healthy()&&nav_ready(); status_->publish(s);
  }
};
int main(int argc,char **argv) {
  rclcpp::init(argc,argv,rclcpp::InitOptions(),rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT,request_stop);
  std::signal(SIGTERM,request_stop);
  try {
    auto node=std::make_shared<MissionNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    while(rclcpp::ok() && !stop_requested) executor.spin_once(100ms);
    executor.remove_node(node);
  }
  catch(const std::exception &e) {RCLCPP_FATAL(rclcpp::get_logger("mission_manager"),"%s",e.what()); rclcpp::shutdown(); return 1;}
  rclcpp::shutdown(); return 0;
}
