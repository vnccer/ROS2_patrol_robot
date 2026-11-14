#include "patrol_manager/mission.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

static unsigned checks=0;
static void check(bool ok,const char *message) {
  ++checks; if(!ok) throw std::runtime_error(message);
}
static patrol::Mission make(unsigned retries=1) {
  patrol::Config c; c.waypoints={{1,1,0},{7,1,0}}; c.max_retries=retries; return patrol::Mission(c);
}
static patrol::Task event(const std::string &id,int priority=50,double ttl=100,double handling=1) {
  patrol::Task t; t.id=id;t.priority=priority;t.expires=ttl;t.handling=handling;t.pose={2,2,0};return t;
}
int main() {
  try {
    {auto m=make();m.tick(0,false);check(!m.flying,"no navigation before readiness");
      m.tick(1);check(m.active->id=="patrol/0","first patrol point");
      m.result(m.token,true,2);m.tick(2.5);check(m.patrol_index==0,"dwell must complete");
      m.tick(3);check(m.patrol_index==1&&m.patrol_completed==1,"advance completed point only");}
    {auto m=make();m.tick(0);auto old=m.token;m.submit(event("alarm"),1);m.tick(1);
      check(m.cancelling&&!m.permit(),"preemption stops motion before cancellation result");
      m.tick(2);check(m.token==old,"no new goal while cancelling");
      m.result(old,false,2);m.tick(2);check(m.active->id=="alarm","event follows terminal old goal");
      m.result(old,true,2.1);check(m.flying,"old result cannot finish new goal");
      m.result(m.token,true,3);m.tick(4);m.tick(4.1);
      check(m.events_completed==1&&m.active->id=="patrol/0","resume unfinished patrol point");}
    {auto m=make();m.submit(event("a",20),0);m.submit(event("b",20),0);m.tick(0);
      check(m.active->id=="a","equal priority FIFO");m.submit(event("urgent",100),1);m.tick(1);
      m.result(m.token,false,1.1);m.tick(1.2);check(m.active->id=="urgent","higher priority event preempts event");
      m.result(m.token,true,2);m.tick(3);m.tick(3.1);check(m.active->id=="a","interrupted event retains order");}
    {auto m=make();check(m.submit(event("same"),0),"accept first ID");
      check(!m.submit(event("same",100),1),"duplicate cannot raise priority");
      m.tick(1);m.result(m.token,true,2);m.tick(3);
      check(!m.submit(event("same"),4),"dedup includes completed events");}
    {auto m=make();m.pause(true,0);m.submit(event("short",50,1),0);m.tick(1);
      check(m.queue.empty(),"pending TTL expires even during pause");m.pause(false,2);m.tick(2);
      check(!m.active->event,"expired event never dispatches");}
    {auto m=make();m.tick(0);m.pause(true,1);check(m.cancelling,"pause cancels navigation");
      m.result(m.token,false,1.1);m.trip("sensor lost",2);
      check(!m.recover(false),"unhealthy recovery refused");check(m.recover(true),"healthy recovery accepted");
      m.tick(3);check(m.paused&&!m.flying,"recovery preserves manual pause");
      m.pause(false,4);m.tick(4);check(m.active->id=="patrol/0","resume preserves patrol cursor");}
    {auto m=make();m.tick(0);m.pause(true,1);m.tick(5);
      check(!m.fault.empty()&&m.flying,"cancel timeout latches fault without releasing old goal");
      check(!m.recover(true),"cannot recover while old goal unresolved");
      m.result(m.token,false,6);check(m.recover(true),"terminal late cancel permits recovery");}
    {auto m=make(1);m.submit(event("fail"),0);m.tick(0);m.result(m.token,false,1);m.tick(2);
      check(m.active->retries==1,"retry budget consumed");m.result(m.token,false,3);
      check(m.tasks_failed==1&&!m.active,"event failure recorded and patrol can resume");m.tick(4);
      check(!m.active->event,"patrol resumes after event retries exhausted");}
    {auto m=make(0);m.tick(0);m.result(m.token,false,1);
      check(!m.fault.empty()&&m.patrol_index==0,"failed patrol point never silently skipped");
      m.recover(true);m.tick(2);check(m.active->id=="patrol/0","recover retries failed patrol point");}
    {auto m=make();m.cfg.goal_timeout=2;m.tick(0);m.tick(3);
      check(m.cancelling&&!m.permit(),"goal deadline cancels");m.result(m.token,false,3.1);m.tick(4);
      check(m.active->retries==1,"navigation deadline uses bounded retries");}
    {auto m=make();m.submit(event("handling",50,100,10),0);m.tick(0);m.result(m.token,true,1);
      m.pause(true,2);check(!m.handling&&m.queue.size()==1,"pause requeues handling event");
      m.pause(false,3);m.tick(3);check(m.flying&&m.active->id=="handling","handling restart re-navigates");}
    {auto m=make();auto t=event("bad");t.pose.x=std::numeric_limits<double>::quiet_NaN();
      check(!m.submit(t,0),"reject nonfinite event");check(!m.submit(event("patrol/fake"),0),"reserve patrol ID prefix");
      check(!m.submit(event("bad-priority",0),0),"reject zero event priority");
      m.cfg.max_queue=1;m.submit(event("full1"),0);check(!m.submit(event("full2"),0),"bounded queue");}
    {auto m=make();m.cfg.max_ids=1;m.submit(event("one"),0);
      check(!m.submit(event("two"),1),"bounded process-lifetime dedup history");}
    // 验证空队列取消报警
    {auto m=make();
      check(!m.cancel_pending("missing"),"empty queue cancellation returns false");
      check(m.queue.empty(),"empty queue remains empty");}
    // 验证不存在的ID、删除中间任务、撤销记录、去重与剩余任务顺序
    {auto m=make();m.submit(event("a",20),0);m.submit(event("b",80),0);m.submit(event("c",20),0);
      check(!m.cancel_pending("missing"),"unknown ID returns false");
      check(m.queue.size()==3 && m.queue[0].id=="a" && m.queue[1].id=="b" && m.queue[2].id=="c","unkown ID preserves queue");
      // 清理掉前面接收报警产生的记录，单独检查撤销记录
      m.drain();
      check(m.cancel_pending("b"),"cancel middle pending event");
      check(m.queue.size()==2 && m.queue[0].id=="a" && m.queue[1].id=="c","remaining queue order is preserved");
      auto effects = m.drain();
      check(effects.size()==1 && effects[0].kind==patrol::Effect::Record && effects[0].name=="pending_cancelled" && effects[0].task.id=="b","cancellation record has correct type and ID");
      check(!m.submit(event("b"),1),"cancelled ID remains deduplicated");
      m.tick(1);
      check(m.active && m.active->id=="a","first remaining event dispatches first");
      m.result(m.token,true,2);
      m.tick(3);
      m.tick(3.1);
      check(m.active && m.active->id=="c","equal priority FIFO survives cancellation");
    }
    // 验证活动任务不受影响
    {auto m=make();m.submit(event("running",80),0);m.submit(event("waiting",20),0);m.tick(0);
      const auto old_token=m.token;
      check(!m.cancel_pending("running"),"active event cannot be cancelled as pending");
      check(m.queue.size()==1&&m.queue[0].id=="waiting","active ID request preserves pending queue");
      // 清掉旧效果，单独检查撤销 waiting 的结果。
      m.drain();check(m.cancel_pending("waiting"),"pending event can be cancelled during navigation");
      check(m.queue.empty(),"cancelled pending event is removed");
      check(m.active&&m.active->id=="running"&&m.flying&&!m.cancelling&&m.token==old_token,"active navigation remains unchanged");
      auto effects=m.drain();
      check(effects.size()==1&&effects[0].kind==patrol::Effect::Record&&effects[0].name=="pending_cancelled"&&effects[0].task.id=="waiting","pending cancellation emits only its record");}
    // 验证“被抢占后重新排队的报警”也可以撤销
    {auto m=make();m.submit(event("low",20),0);m.tick(0);const auto interrupted_token=m.token;
      m.submit(event("urgent",80),1);m.tick(1);
      check(m.cancelling,"urgent event starts preemption");
      // 模拟旧导航终结：low 重新入队，再派发 urgent。
      m.result(interrupted_token,false,1.1);m.tick(1.2);
      check(m.active&&m.active->id=="urgent"&&m.queue.size()==1&&m.queue[0].id=="low","interrupted event is back in pending queue");
      const auto urgent_token=m.token;
      m.drain();check(m.cancel_pending("low"),"interrupted pending event can be cancelled");
      check(m.queue.empty()&&m.active&&m.active->id=="urgent"&&m.flying&&!m.cancelling&&m.token==urgent_token,"urgent navigation continues after pending removal");
      auto effects=m.drain();
      check(effects.size()==1&&effects[0].kind==patrol::Effect::Record&&effects[0].name=="pending_cancelled"&&effects[0].task.id=="low","interrupted pending cancellation records the correct ID");}
    std::cout<<"PASS: "<<checks<<" mission invariants\n";return 0;
  } catch(const std::exception &e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
