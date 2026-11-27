#include <iostream>
#include <limits>
#include <stdexcept>

#include "patrol_manager/feedback_path.hpp"

static unsigned checks = 0;

static void check(bool ok, const char *message) {
  ++checks;
  if (!ok) {
    throw std::runtime_error(message);
  }
}

static void near(std::optional<double> value, double expected, const char *message) {
  check(value && std::abs(*value - expected) < 1e-8, message);
}

int main() {
  try {
    patrol::FeedbackPath path;
    path.reset(5, 100, "map", {6, 0});
    check(!path.remaining(5, 200, "map", {0, 0}),
          "no numeric distance before a current plan");
    check(!path.update(5, 90, "map", {{0, 0}, {6, 0}}),
          "reject old stamp even for a matching endpoint");
    check(!path.update(5, 100, "map", {{0, 0}, {6, 0}}),
          "equal dispatch stamp is conservatively ambiguous");
    check(!path.update(5, 110, "map", {{0, 0}, {0.28, 0}}),
          "reject previous goal path with fresh delivery");
    check(!path.update(5, 110, "odom", {{0, 0}, {6, 0}}), "reject wrong plan frame");
    check(!path.update(4, 110, "map", {{0, 0}, {6, 0}}), "reject old navigation token");
    check(!path.update(5, 110, "map", {}), "reject empty path");
    check(!path.remaining(5, 1000000, "map", {0, 0}),
          "waiting longer never enables a stale fallback");
    check(path.update(5, 110, "map", {{0, 0}, {6, 0}}),
          "accept fresh matching goal path");
    check(!path.remaining(5, 109, "map", {0, 0}),
          "reject position older than accepted plan");
    near(path.remaining(5, 110, "map", {0, 0}), 6.0,
         "new goal starts at six metres, not old 0.28");
    near(path.remaining(5, 111, "map", {2, 0}), 4.0,
         "distance decreases along fresh path");
    check(!path.remaining(4, 111, "map", {2, 0}),
          "late old callback cannot read new goal distance");
    check(!path.remaining(5, 111, "odom", {2, 0}),
          "pose and path must share coordinates");

    path.reset(6, 200, "map", {6, 0});
    check(!path.remaining(6, 300, "map", {2, 0}),
          "retry of same target clears cached distance");
    check(!path.update(6, 110, "map", {{0, 0}, {6, 0}}),
          "same target still requires a newly generated path");
    check(path.update(6, 210, "map", {{0, 0}, {6, 0}}), "retry accepts its fresh plan");
    near(path.remaining(6, 211, "map", {2, 0}), 4.0, "retry computes its own distance");

    path.reset(7, 300, "map", {4, 3});
    check(path.update(7, 310, "map", {{0, 0}, {0, 3}, {4, 3}}), "accept bent route");
    near(path.remaining(7, 311, "map", {0, 0}), 7.0,
         "use route length rather than five metre straight line");
    near(path.remaining(7, 311, "map", {0, 1}), 6.0,
         "projection handles position between path samples");
    near(path.remaining(7, 311, "map", {-1, 1}), 7.0,
         "include connector from robot to current route");
    near(path.remaining(7, 311, "map", {4, 3}), 0.0,
         "zero is valid at the actual new endpoint");
    check(!path.update(7, 309, "map", {{0, 0}, {4, 3}}),
          "out-of-order plan cannot replace current route");
    near(path.remaining(7, 311, "map", {0, 0}), 7.0,
         "rejected plan preserves accepted route");
    check(path.update(7, 320, "map", {{0, 0}, {4, 0}, {4, 3}}),
          "accept replan for current target");
    check(!path.remaining(7, 319, "map", {2, 0}),
          "replan also waits for a fresh position");
    near(path.remaining(7, 321, "map", {2, 0}), 5.0,
         "new route replaces old path geometry");

    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double inf = std::numeric_limits<double>::infinity();
    check(!path.update(7, 330, "map", {{nan, 0}, {4, 3}}),
          "reject nonfinite path coordinate");
    check(!path.update(7, 330, "map", {{0, inf}, {4, 3}}),
          "reject infinite path coordinate");
    check(!path.remaining(7, 321, "map", {nan, 0}), "reject nonfinite position");
    check(!path.update(7, 330, "map", {{0, 0}, {4.51, 3}}),
          "reject endpoint outside planner tolerance");

    path.reset(8, 400, "map", {6, 0});
    check(path.update(8, 410, "map", {{0, 0}, {6, 0}, {6, 0}}),
          "duplicate adjacent samples are allowed");
    near(path.remaining(8, 411, "map", {2, 0}), 4.0,
         "duplicate samples cannot divide by zero");
    check(path.update(8, 420, "map", {{5.75, 0}}),
          "accept single point within planner endpoint tolerance");
    near(path.remaining(8, 421, "map", {5.5, 0}), 0.25,
         "single point route includes current position gap");

    path.reset(9, 500, "map", {10, 0});
    check(!path.remaining(8, 600, "map", {5, 0}),
          "preempted token cannot report progress");
    check(!path.update(9, 490, "map", {{0, 0}, {10, 0}}),
          "old plan for repeated coordinates remains stale");
    check(!path.update(9, 510, "map", {{0, 0}, {6, 0}}),
          "previous task endpoint cannot unlock new task");
    check(path.update(9, 510, "map", {{0, 0}, {10, 0}}),
          "new task unlocks only with its matching plan");
    near(path.remaining(9, 511, "map", {5, 0}), 5.0,
         "new task reports fresh progress");

    std::cout << "PASS: " << checks << " feedback path checks\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
