# IBS / EIMP Local Unix Log Synchronization

The Flask simulator generates **synthetic** Java, Tomcat, Apache-style and Oracle-style events. It does not run those services or connect to an Oracle database.

## On your Ubuntu laptop

1. Ensure both `~/IBS_Server_Lab` and `~/EIMP_Server_Lab` exist.
2. Open the simulator in the browser and open Developer Tools (F12) > Console.
3. Run `sessionStorage.getItem('ibs_eimp_lab_session')`. Copy your session ID **privately**.
4. Download `sync_simulator_logs.py` from this repository to your laptop.
5. Run:

```bash
python3 sync_simulator_logs.py --session 'YOUR_PRIVATE_SESSION_ID'
```

6. In the **same browser tab/session**, trigger IBS and EIMP scenarios. The script polls every 30 seconds.
7. Inspect the local files:

```bash
tail -20 ~/IBS_Server_Lab/appserver/opt/tomcat/logs/application.log
grep -in 'ORA-' ~/IBS_Server_Lab/appserver/opt/tomcat/logs/application.log
grep -n 'IBS-REQ-' ~/IBS_Server_Lab/webserver/var/log/httpd/ibs_access_log
tail -20 ~/EIMP_Server_Lab/appserver/opt/tomcat/logs/application.log
```

Stop with Ctrl+C. This is a **single-session** sync: other students' separate browser sessions will not appear in your files. The session ID grants access to that session's synthetic logs. Never publish it. The agent appends to your existing lab logs, so back them up if needed.

### Limitations
- Current simulator data is in memory and resets when Render restarts; logs generated while the laptop is off can be lost.
- The simulator retains at most 1200 lines per log, so heavy traffic between polls can cause gaps.
- If a simulator session is reset, the sync agent may need to be restarted.
- Lines without a project-specific request ID (such as some GC events) are not synchronized.
- This does not enable instructor authentication or real Oracle database permissions. IBS_APP and IBS_USER_APP remain proposed database account names for the future Oracle integration.
