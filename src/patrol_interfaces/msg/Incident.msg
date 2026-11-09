# ID must be unique for a manager process. A repeated ID is ignored.
string id
uint8 priority
geometry_msgs/PoseStamped target
# Pending TTL measured by local monotonic receipt time, not the message stamp.
float64 ttl_sec
float64 handling_sec
string description
