#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace patrol {
struct Pose { double x{0}, y{0}, yaw{0}; };
struct Task {
  std::string id;
  Pose pose;
  int priority{0};
  bool event{false};
  double received{0}, expires{0}, handling{0};
  unsigned retries{0};
  uint64_t order{0};
};
struct Config {
  std::vector<Pose> waypoints;
  double patrol_dwell{1}, goal_timeout{90}, cancel_timeout{3};
  unsigned max_retries{1}, max_queue{64}, max_ids{10000};
};
struct Effect {
  enum Kind { Start, Cancel, Record } kind;
  Task task;
  uint64_t token{0};
  std::string name, detail;
  double value{0};
};

// 纯业务核心：只管理任务。ROS 回调与仿真都通过同一套接口驱动它。
class Mission {
public:
  explicit Mission(Config config) : cfg(std::move(config)) {
    if (cfg.waypoints.empty() || !std::isfinite(cfg.goal_timeout) || cfg.goal_timeout <= 0 ||
        !std::isfinite(cfg.cancel_timeout) || cfg.cancel_timeout <= 0 ||
        !std::isfinite(cfg.patrol_dwell) || cfg.patrol_dwell<0 || cfg.max_queue==0)
      throw std::invalid_argument("invalid mission configuration");
    for (const auto &p:cfg.waypoints)
      if(!std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.yaw))
        throw std::invalid_argument("nonfinite waypoint");
  }
  Config cfg;
  std::optional<Task> active;
  std::vector<Task> queue;
  size_t patrol_index{0};
  uint64_t patrol_completed{0}, events_completed{0}, tasks_failed{0};
  bool paused{false}, flying{false}, cancelling{false}, handling{false};
  std::string fault;
  uint64_t token{0};

  void record(const std::string &name, const std::string &detail="", double value=0,
              const std::string &id="") {
    Effect e{}; e.kind=Effect::Record; e.name=name; e.detail=detail; e.value=value;
    e.task.id=id.empty() && active ? active->id : id; effects.push_back(e);
  }
  bool submit(Task t, double now) {
    if (t.id.empty() || t.id.size()>128 || t.id.rfind("patrol/",0)==0 ||
        t.priority<1 || t.priority>100 || !std::isfinite(t.expires) ||
        t.expires<=0 || t.expires>86400 || !std::isfinite(t.handling) ||
        t.handling<0 || t.handling>3600 || !std::isfinite(t.pose.x) ||
        !std::isfinite(t.pose.y) || !std::isfinite(t.pose.yaw)) {
      record("rejected", "invalid incident", 0, t.id); return false;
    }
    if (known.count(t.id)) { record("duplicate", "ignored",0,t.id); return false; }
    if (queue.size()>=cfg.max_queue || known.size()>=cfg.max_ids) {
      record("rejected", "queue or ID history full",0,t.id); return false;
    }
    known.insert(t.id); t.event=true; t.received=now; t.expires+=now;
    t.order=++sequence; queue.push_back(t); record("accepted","",0,t.id);
    return true;
  }
  void pause(bool value, double now) {
    if (value==paused) return;
    paused=value; record(value ? "paused" : "resumed");
    if (value) suspend(now,"pause");
  }
  void trip(const std::string &reason, double now) {
    if (!fault.empty()) return;
    fault=reason; record("fault",reason); suspend(now,"fault");
  }
  bool recover(bool healthy) {
    if (!healthy || flying || cancelling) return false;
    fault.clear(); record("recovered"); return true;
  }
  void tick(double now, bool ready=true) {
    for (auto it=queue.begin(); it!=queue.end();) {
      if (now>=it->expires) {record("expired","pending TTL",0,it->id); it=queue.erase(it);}
      else ++it;
    }
    if (cancelling) {
      if (now-cancel_at>cfg.cancel_timeout && fault.empty()) {
        fault="cancel acknowledgement timeout"; record("fault",fault);
      }
      return; // 旧导航没有终结结果前绝不发送新目标。
    }
    if (flying && now-started>cfg.goal_timeout) { suspend(now,"timeout"); return; }
    if (paused || !fault.empty()) return;
    if (active && !queue.empty() && best()->priority>active->priority) {
      suspend(now,"preempt"); return;
    }
    if (handling) {
      if (now>=handle_until) finish();
      return;
    }
    if (flying || !ready) return;
    if (!active) {
      if (!queue.empty()) {
        auto it=best(); active=*it; queue.erase(it);
      } else {
        Task t; t.id="patrol/"+std::to_string(patrol_index);
        t.pose=cfg.waypoints.at(patrol_index); t.handling=cfg.patrol_dwell; active=t;
      }
    }
    flying=true; started=now; ++token;
    Effect e{}; e.kind=Effect::Start; e.task=*active; e.token=token; effects.push_back(e);
    record("dispatched", "", active->event ? now-active->received : 0);
  }
  void result(uint64_t result_token, bool success, double now) {
    if (result_token!=token || !flying) return;
    flying=false;
    if (cancelling) {
      cancelling=false; record("cancelled",cancel_reason);
      // 若取消期间已成功抵达，抢占仍按原任务重派，保证单一路径管理恢复。
      if (cancel_reason=="timeout") failure();
      else requeue_active();
      return;
    }
    if (!success) { failure(); return; }
    handling=true; handle_until=now+active->handling;
    record("arrived","",active->event ? now-active->received : 0);
  }
  bool permit() const {return flying && !cancelling && !paused && fault.empty();}
  std::string state() const {
    if (!fault.empty()) return "FAULT";
    if (paused) return "PAUSED";
    if (cancelling) return "CANCELLING";
    if (handling) return active && active->event ? "HANDLING_EVENT" : "DWELLING";
    if (flying) return active && active->event ? "RESPONDING" : "PATROLLING";
    return "WAITING";
  }
  std::vector<Effect> drain() {auto out=std::move(effects); effects.clear(); return out;}

private:
  std::set<std::string> known;
  std::vector<Effect> effects;
  uint64_t sequence{0};
  double started{0}, cancel_at{0}, handle_until{0};
  std::string cancel_reason;
  std::vector<Task>::iterator best() {
    return std::min_element(queue.begin(),queue.end(),[](const Task&a,const Task&b){
      return a.priority!=b.priority ? a.priority>b.priority : a.order<b.order;
    });
  }
  void suspend(double now, const std::string &reason) {
    if (!active || cancelling) return;
    if (flying) {
      cancelling=true; cancel_at=now; cancel_reason=reason;
      Effect e{}; e.kind=Effect::Cancel; e.token=token; e.task=*active; effects.push_back(e);
      record("cancel_requested",reason);
    } else { handling=false; requeue_active(); }
  }
  void requeue_active() {
    if (active && active->event) queue.push_back(*active);
    active.reset(); handling=false;
    // patrol_index 未变：恢复时重新导航至未完成的巡逻点。
  }
  void failure() {
    record("navigation_failed");
    if (active && active->retries++<cfg.max_retries) {record("retry"); return;}
    ++tasks_failed; record("failed");
    if (active && active->event) active.reset();
    else { // 巡逻点失败不静默跳过，等待人工恢复后重试该点。
      if (active) active->retries=0;
      fault="patrol navigation retries exhausted"; record("fault",fault);
    }
  }
  void finish() {
    record("completed");
    if (active->event) ++events_completed;
    else {++patrol_completed; patrol_index=(patrol_index+1)%cfg.waypoints.size();}
    active.reset(); handling=false;
  }
};
} // namespace patrol
