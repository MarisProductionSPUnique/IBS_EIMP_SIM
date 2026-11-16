# IBS / EIMP Oracle API Lab

Separate standalone Flask training service. Does not connect to a real Oracle database and does not modify the existing IBS_EIMP_SIM service.

30 scenario buttons generate synthetic API failures and correlated Apache access, Tomcat application, catalina.out and Oracle-simulator logs. Apache error log stays empty unless a reverse-proxy transport failure is simulated (none in this basic version).

Run: `pip install -r requirements.txt && python app.py`.
Render root directory: `IBS_EIMP_Oracle_API_Lab`.
Build command: `pip install -r requirements.txt`.
Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app`.
Open `/api/scenarios`, `/api/simulate/transfer-duplicate` (POST), `/api/logs/IBS`, or `/api/download/logs.zip`.

Note: in-memory generated logs reset on process restart. This is not a persistent incident store. Download ZIP after practice.
