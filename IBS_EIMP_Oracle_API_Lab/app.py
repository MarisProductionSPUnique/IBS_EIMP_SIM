from flask import Flask, jsonify, request, Response
from datetime import datetime, timezone
import uuid, io, zipfile, threading

app = Flask(__name__)
lock = threading.Lock()
events = []
SCENARIOS = [
 ("IBS","transfer-duplicate","POST","/api/transfers","ORA-00001","unique constraint (IBS_APP.UK_TRANSACTION_REFERENCE) violated",409),
 ("IBS","transfer-deadlock","POST","/api/transfers","ORA-00060","deadlock detected while waiting for resource",500),
 ("IBS","account-locked","POST","/api/accounts/login","ORA-28000","the account is locked",503),
 ("IBS","invalid-credentials","POST","/api/accounts/login","ORA-01017","invalid username/password; logon denied",503),
 ("IBS","missing-table","GET","/api/accounts","ORA-00942","table or view does not exist",500),
 ("IBS","missing-field","POST","/api/accounts","ORA-01400","cannot insert NULL into IBS_APP.ACCOUNTS.ACCOUNT_NUMBER",400),
 ("IBS","foreign-key","POST","/api/beneficiaries","ORA-02291","integrity constraint violated - parent key not found",409),
 ("IBS","listener","GET","/api/accounts","ORA-12514","listener does not currently know of service requested",503),
 ("IBS","tablespace","POST","/api/transfers","ORA-01653","unable to extend table IBS_APP.BANK_TRANSACTIONS",507),
 ("IBS","snapshot","GET","/api/reports/daily","ORA-01555","snapshot too old",500),
 ("IBS","invalid-trigger","POST","/api/transfers","ORA-04098","trigger IBS_APP.TRG_TRANSACTION_AUDIT is invalid",500),
 ("IBS","connection-pool","GET","/api/accounts","ORA-12541","TNS:no listener",503),
 ("IBS","insufficient-privileges","GET","/api/accounts","ORA-01031","insufficient privileges",403),
 ("IBS","invalid-number","POST","/api/transfers","ORA-01722","invalid number",400),
 ("IBS","resource-busy","POST","/api/transfers","ORA-00054","resource busy and acquire with NOWAIT specified",409),
 ("EIMP","claim-duplicate","POST","/api/claims","ORA-00001","unique constraint (EIMP_APP.UK_CLAIM_REFERENCE) violated",409),
 ("EIMP","claim-deadlock","POST","/api/claims","ORA-00060","deadlock detected while waiting for resource",500),
 ("EIMP","policy-missing","GET","/api/policies","ORA-00942","table or view does not exist",500),
 ("EIMP","premium-null","POST","/api/premiums","ORA-01400","cannot insert NULL into EIMP_APP.PREMIUM_PAYMENTS.AMOUNT",400),
 ("EIMP","claim-parent","POST","/api/claims","ORA-02291","integrity constraint violated - parent key not found",409),
 ("EIMP","listener","GET","/api/policies","ORA-12514","listener does not currently know of service requested",503),
 ("EIMP","account-locked","POST","/api/policies","ORA-28000","the account is locked",503),
 ("EIMP","wrong-password","GET","/api/policies","ORA-01017","invalid username/password; logon denied",503),
 ("EIMP","settlement-space","POST","/api/settlements","ORA-01653","unable to extend table EIMP_APP.CLAIM_SETTLEMENTS",507),
 ("EIMP","snapshot","GET","/api/reports/claims","ORA-01555","snapshot too old",500),
 ("EIMP","invalid-trigger","POST","/api/claims","ORA-04098","trigger EIMP_APP.TRG_CLAIM_AUDIT is invalid",500),
 ("EIMP","pool-exhausted","GET","/api/policies","ORA-12541","TNS:no listener",503),
 ("EIMP","privileges","GET","/api/policies","ORA-01031","insufficient privileges",403),
 ("EIMP","invalid-number","POST","/api/premiums","ORA-01722","invalid number",400),
 ("EIMP","resource-busy","POST","/api/settlements","ORA-00054","resource busy and acquire with NOWAIT specified",409),
 ("EIMP","invalid-date","POST","/api/policies","ORA-01861","literal does not match format string",400),
]
def emit(s, request_id):
    project, key, method, path, code, message, status = s
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    apache = f'{now} {method} {path} HTTP/1.1 {status} reqId={request_id}'
    java = f'{now} ERROR {project}Service requestId={request_id} java.sql.SQLException: {code}: {message}'
    oracle = f'{now} SIMULATED requestId={request_id} {code}: {message}'
    tomcat = f'{now} ERROR JDBC requestId={request_id} {code}: {message}' if code in ("ORA-12514","ORA-12541","ORA-01017","ORA-28000") else ""
    entry = dict(project=project,scenario=key,requestId=request_id,method=method,path=path,status=status,oracleError=code,detail=message,access=apache,application=java,oracle=oracle,catalina=tomcat)
    with lock:
        events.append(entry)
        if len(events)>2000: del events[:-2000]
    return entry
@app.get("/")
def home():
    return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>IBS EIMP Oracle API Lab</title><style>body{font:16px system-ui;max-width:960px;margin:2em auto;padding:0 1em;background:#f7f8fa}button{padding:9px;margin:5px;cursor:pointer}pre{white-space:pre-wrap;background:#151b2b;color:#eee;padding:16px;border-radius:8px}section{background:white;padding:14px;border-radius:8px;margin:10px 0}</style></head><body><h1>IBS &amp; EIMP Oracle API Support Lab</h1><p>Training simulator: Oracle, Apache and Tomcat logs are synthetic, not live server logs.</p><a href="/api/download/logs.zip">Download generated logs ZIP</a><div id="scenarios"></div><h2>Latest API response</h2><pre id="result">Choose a scenario above</pre><script>fetch('/api/scenarios').then(r=>r.json()).then(rows=>{let target=document.getElementById('scenarios');for(let p of ['IBS','EIMP']){let s=document.createElement('section');let h=document.createElement('h2');h.textContent=p;s.append(h);rows.filter(x=>x.project===p).forEach(x=>{let b=document.createElement('button');b.textContent=x.scenario+' ('+x.oracleError+')';b.onclick=async()=>{let r=await fetch('/api/simulate/'+x.scenario,{method:'POST'});document.getElementById('result').textContent=JSON.stringify(await r.json(),null,2)+'\\nHTTP '+r.status};s.append(b)});target.append(s)}})</script></body></html>"""
@app.get("/health")
def health(): return jsonify(status="ok",mode="simulated")
@app.get("/api/scenarios")
def scenarios(): return jsonify([dict(project=x[0],scenario=x[1],method=x[2],path=x[3],oracleError=x[4],httpStatus=x[6]) for x in SCENARIOS])
@app.route("/api/simulate/<key>",methods=["POST"])
def simulate(key):
    s=next((x for x in SCENARIOS if x[1]==key),None)
    if not s:return jsonify(error="Unknown scenario"),404
    reqid=request.headers.get("X-Request-ID") or str(uuid.uuid4())
    e=emit(s,reqid)
    return jsonify(requestId=reqid,scenario=key,oracleError=e["oracleError"],error="Simulated API failure",message=e["detail"],logUrl="/api/logs/"+e["project"]),e["status"]
@app.get("/api/logs/<project>")
def logs(project):
    if project.upper() not in ("IBS","EIMP"):return jsonify(error="Unknown project"),404
    with lock: rows=[e for e in events if e["project"]==project.upper()]
    return jsonify(rows)
@app.get("/api/download/logs.zip")
def download():
    buf=io.BytesIO()
    with lock: rows=list(events)
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for project in ("IBS","EIMP"):
            selected=[e for e in rows if e["project"]==project]
            root=f"{project}_Server_Lab"
            prefix=project.lower()
            entries={
                f"{root}/webserver/var/log/httpd/{prefix}_access_log": "access",
                f"{root}/webserver/var/log/httpd/{prefix}_error_log": None,
                f"{root}/appserver/opt/tomcat/logs/application.log":"application",
                f"{root}/appserver/opt/tomcat/logs/catalina.out":"catalina",
                f"{root}/database/logs/oracle_simulator.log":"oracle"
            }
            for path,field in entries.items():
                lines=[e[field] for e in selected if field and e[field]]
                z.writestr(path,"\n".join(lines)+("\n" if lines else ""))
    return Response(buf.getvalue(),mimetype="application/zip",headers={"Content-Disposition":"attachment; filename=IBS_EIMP_generated_logs.zip"})
if __name__=="__main__":app.run(host="0.0.0.0",port=5000)
