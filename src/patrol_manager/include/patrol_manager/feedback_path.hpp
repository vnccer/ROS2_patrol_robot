#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace patrol {

struct FeedbackPoint { double x, y; };

// 只用于显示进度，不参与派发、取消或到达判断。
// /plan 没有 Action UUID，按派发时间、坐标系及终点关联当前目标。
class FeedbackPath {
public:
  void reset(uint64_t token, int64_t goal_stamp_ns, std::string frame, FeedbackPoint goal) {
    token_=token; goal_stamp_ns_=goal_stamp_ns; frame_=std::move(frame); goal_=goal;
    plan_stamp_ns_=-1; points_.clear(); suffix_.clear();
  }

  bool update(uint64_t token, int64_t stamp_ns, const std::string &frame,
              std::vector<FeedbackPoint> points) {
    if(token!=token_ || frame.empty() || frame!=frame_ || points.empty() ||
       stamp_ns<=goal_stamp_ns_ || stamp_ns<=plan_stamp_ns_ || !finite(goal_)) return false;
    for(const auto &point:points) if(!finite(point)) return false;
    // 与当前 Navfn 的 0.5 m 规划终点容差一致，不是机器人到达判据。
    if(distance(points.back(),goal_)>0.5) return false;
    std::vector<double> suffix(points.size(),0.0);
    for(size_t i=points.size()-1;i>0;--i) {
      suffix[i-1]=suffix[i]+distance(points[i-1],points[i]);
      if(!std::isfinite(suffix[i-1])) return false;
    }
    points_=std::move(points); suffix_=std::move(suffix); plan_stamp_ns_=stamp_ns;
    return true;
  }

  std::optional<double> remaining(uint64_t token, int64_t pose_stamp_ns,
                                  const std::string &frame, FeedbackPoint pose) const {
    // 位置也须更新到这条路径之后，避免混用早于新路径生成的反馈。
    if(token!=token_ || points_.empty() || frame!=frame_ || !finite(pose) ||
       pose_stamp_ns<plan_stamp_ns_) return std::nullopt;
    if(points_.size()==1) {
      const double value=distance(pose,points_.front());
      return std::isfinite(value) ? std::optional<double>(value) : std::nullopt;
    }
    double nearest=std::numeric_limits<double>::infinity(), result=0.0;
    for(size_t i=0;i+1<points_.size();++i) {
      const auto &a=points_[i]; const auto &b=points_[i+1];
      const double length=distance(a,b);
      const double ux=length>0 ? (b.x-a.x)/length : 0.0;
      const double uy=length>0 ? (b.y-a.y)/length : 0.0;
      const double along=std::clamp((pose.x-a.x)*ux+(pose.y-a.y)*uy,0.0,length);
      const FeedbackPoint projection{a.x+along*ux,a.y+along*uy};
      const double connector=distance(pose,projection);
      const double value=connector+(length-along)+suffix_[i+1];
      if(!std::isfinite(connector) || !std::isfinite(value)) return std::nullopt;
      if(connector<nearest) {nearest=connector; result=value;}
    }
    return result;
  }

private:
  static bool finite(FeedbackPoint p) {return std::isfinite(p.x)&&std::isfinite(p.y);}
  static double distance(FeedbackPoint a, FeedbackPoint b) {return std::hypot(a.x-b.x,a.y-b.y);}
  uint64_t token_{0};
  int64_t goal_stamp_ns_{0},plan_stamp_ns_{-1};
  std::string frame_;
  FeedbackPoint goal_{0,0};
  std::vector<FeedbackPoint> points_;
  std::vector<double> suffix_;
};

} // namespace patrol
