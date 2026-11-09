import csv
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from report_metrics import summarize

def test_metrics_preserve_unfinished_and_use_first_latency(tmp_path):
    path = tmp_path/'records.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['ros_sec','monotonic_sec','kind','task_id','detail','value'])
        for kind,ident,detail,value in [('accepted','a','',0),('accepted','b','',0),('accepted','c','',0),
              ('dispatched','a','',.2),('dispatched','a','',4),('arrived','a','',8),
              ('completed','a','',0),('expired','b','',0),('duplicate','a','',0),
              ('cancel_requested','patrol/1','preempt',0),('dispatched','patrol/1','',0)]:
            w.writerow([0,0,kind,ident,detail,value])
    result = summarize(path)
    assert result['events_accepted']==3
    assert result['events_completed']==1
    assert result['events_expired']==1
    assert result['events_pending_or_interrupted']==1
    assert result['first_dispatch_latency']['mean_sec']==.2
    assert result['patrol_redispatched_target_ids']==1
