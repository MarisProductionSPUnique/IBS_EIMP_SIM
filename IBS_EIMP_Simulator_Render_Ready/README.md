# IBS + EIMP Production Support Simulator — Render-ready package

This lightweight Flask app simulates 50 Java/Tomcat/Apache/Oracle support incidents:
25 IBS banking and 25 EIMP insurance. It serves *real HTTP responses* for students to inspect in browser Developer Tools, and generates **synthetic** correlated logs including:

- `access.log`, `error.log`, `application.log`, `catalina.out`, `database.log`
- `gc.log`, `thread_dump.log`, `startup.log`, `batch.log`

These are training examples, not log files from an actual Java/Tomcat or Oracle instance. The backend is Flask, and there are no real banking transactions.

## Run locally on Ubuntu

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

Visit http://localhost:5000/ and choose **Send actual HTTP status** to see 4xx and 5xx requests in **F12 → Network**.

## Deploy on Render (new web service)

1. Extract this ZIP. Create a **new GitHub repository** (e.g. `ibs-eimp-support-simulator`) and upload the **contents** of this folder directly to the repository root. Confirm `app.py`, `render.yaml`, `requirements.txt` and `templates/index.html` are present at those exact paths.
2. Sign in to https://dashboard.render.com/ and select **New → Web Service**. Connect the new repository, choose **Free** if your account is eligible.
3. Use **Python 3** runtime with **Build Command**: `pip install -r requirements.txt && python -m unittest discover -s tests -v`
4. Use **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 1 app:app`
5. Leave **Root Directory** blank (since application files are in the repository root). Deploy; Render will show the public `https://<service-name>.onrender.com` address.
6. Verify `https://<service-name>.onrender.com/health` responds with `{"status":"UP",...}`, and then open `/`.

Alternatively, use **New → Blueprint** and select your GitHub repository. The supplied `render.yaml` specifies the free Python web service. Deploying through either method is sufficient—do not create duplicate services unnecessarily.

### Important about your existing Render service

If you already have another app deployed on Render, **create a new service for this simulator** instead of replacing the source of an unrelated banking/demo app. A Dashboard deployment-history link is not itself a live URL for this simulator.

## Operational limitations

- Free Render services can sleep when idle, causing slow first requests.
- All logs and history live **in process memory**, with a separate randomly generated browser session ID. Logs reset on restart/redeploy and may be lost if Render spins the instance down.
- Single Gunicorn worker preserves in-memory consistency. This is a training setup, not a production-grade, durable log store.
- Do not send real credentials, financial records, or customer data to this demo.
- Timing displayed in the UI is **simulated backend duration**, not a measured 5-second delay.
- No instructor authentication is implemented; training sessions are isolated by guess-resistant browser session IDs, not a security mechanism.

## Class exercise

1. Select an IBS transfer DB failure (HTTP 500).
2. Click **Send actual HTTP status** and look at F12 → Network.
3. Copy the request ID and search it under `application.log`, `access.log`, and `database.log`.
4. Download files and run `grep -i 'error' application.log` or `grep 'IBS-REQ-' access.log` on Ubuntu.
5. Explain probable root cause, corrective action, and post-fix validation.
