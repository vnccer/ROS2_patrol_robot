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
    std::cout<<"PASS: "<<checks<<" mission invariants\n";return 0;
  } catch(const std::exception &e) {std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
