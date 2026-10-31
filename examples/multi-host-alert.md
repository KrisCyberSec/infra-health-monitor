# Multi-Host Sample Alert

## lab-server-01 (web)
**Severity:** High  
**Issue:** Disk usage at 95% (baseline 40-75%)  
**Services:** nginx running, sshd running  
**Suggested action:** Investigate /var/log and large files. Consider log rotation or cleanup.

## lab-db-01 (database)
**Severity:** Critical  
**Issue:** postgres service failed  
**Other metrics:** CPU 41%, memory 67%, disk 62% (all normal)  
**Suggested action:** Check postgres logs (`journalctl -u postgres` or `/var/log/postgresql/`), restart service if safe, and investigate root cause.

**Overall:** Immediate attention required on database host.
