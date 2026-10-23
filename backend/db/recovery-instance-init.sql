CREATE SCHEMA unishortlist_recovery;
CREATE TABLE unishortlist_recovery.instance_marker (
    marker text PRIMARY KEY
);
INSERT INTO unishortlist_recovery.instance_marker
VALUES ('uni-shortlist-isolated-recovery-db-v1');
