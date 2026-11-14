from flask import Flask, jsonify, render_template, request, Response
from datetime import datetime, timezone
from collections import defaultdict
import uuid, os

app = Flask(__name__)
# Teaching simulator: all incidents and logs are synthetic; sessions are isolated by browser-provided UUID.
SCENARIOS = {'IBS': [('balance_ok', 'Balance enquiry success', 200, 'Balance returned', 'INFO', 'Balance enquiry completed'), ('login_401', 'Invalid login', 401, 'Invalid credentials', 'WARN', 'AuthenticationException: bad credentials'), ('transfer_500', 'Transfer database connection failure', 500, 'Database unavailable', 'ERROR', 'java.sql.SQLRecoverableException: ORA-17002: IO Error: Connection refused'), ('balance_504', 'Balance API gateway timeout', 504, 'Upstream timed out', 'ERROR', 'java.net.SocketTimeoutException: Read timed out'), ('account_400', 'Missing account type', 400, 'accountType required', 'WARN', 'MethodArgumentNotValidException: accountType is required'), ('admin_403', 'Admin permission denied', 403, 'Forbidden', 'WARN', 'org.springframework.security.access.AccessDeniedException: ROLE_ADMIN required'), ('transfer_409', 'Duplicate transaction', 409, 'Duplicate transfer reference', 'ERROR', 'ORA-00001: unique constraint (IBS.UK_TXN_REF) violated'), ('service_503', 'Application unavailable', 503, 'Service unavailable', 'ERROR', 'org.springframework.web.client.ResourceAccessException: service unavailable'), ('proxy_502', 'Upstream connection refused', 502, 'Bad gateway', 'ERROR', 'java.net.ConnectException: Connection refused'), ('statement_404', 'Statement not found', 404, 'Statement missing', 'WARN', 'com.ibs.StatementNotFoundException: statement not found'), ('statement_oom', 'Statement generation heap exhausted', 500, 'Unable to generate statement', 'ERROR', 'java.lang.OutOfMemoryError: Java heap space'), ('report_stack', 'Recursive report stack overflow', 500, 'Report generation failed', 'ERROR', 'java.lang.StackOverflowError'), ('transfer_npe', 'Transfer null pointer', 500, 'Transfer processing error', 'ERROR', 'java.lang.NullPointerException: Cannot invoke Account.getId() because account is null'), ('db_pool', 'Connection pool exhausted', 503, 'Database pool busy', 'ERROR', 'java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 30000ms'), ('dns_fail', 'Payment service DNS failure', 503, 'Payment service unavailable', 'ERROR', 'java.net.UnknownHostException: payments.internal'), ('network_reset', 'Payment socket reset', 502, 'Upstream connection reset', 'ERROR', 'java.net.SocketException: Connection reset'), ('statement_file', 'Statement output file missing', 500, 'Statement file missing', 'ERROR', 'java.io.FileNotFoundException: /opt/ibs/statements/statement.pdf (No such file or directory)'), ('statement_permission', 'Statement folder permission denied', 500, 'Unable to write statement', 'ERROR', 'java.nio.file.AccessDeniedException: /opt/ibs/statements'), ('bean_failure', 'Spring bean initialization failure', 503, 'Application not ready', 'ERROR', 'org.springframework.beans.factory.BeanCreationException: Error creating bean with name transferService'), ('missing_bean', 'Missing Spring dependency', 503, 'Application initialization failed', 'ERROR', 'org.springframework.beans.factory.NoSuchBeanDefinitionException: No qualifying bean of type PaymentRepository'), ('port_busy', 'Tomcat connector port conflict', 503, 'Application startup failed', 'ERROR', 'java.net.BindException: Address already in use: bind'), ('thread_deadlock', 'Deadlocked account locks', 503, 'Transfer request blocked', 'ERROR', 'java.lang.IllegalStateException: Deadlock detected: AccountLock-A waits for AccountLock-B'), ('oracle_space', 'Oracle tablespace full', 500, 'Unable to save transfer', 'ERROR', 'java.sql.SQLException: ORA-01653: unable to extend table IBS.TRANSACTIONS'), ('oracle_listener', 'Oracle listener unavailable', 503, 'Database listener unavailable', 'ERROR', 'java.sql.SQLRecoverableException: ORA-12541: TNS:no listener'), ('batch_fail', 'End of day settlement batch failed', 500, 'Settlement batch failed', 'ERROR', 'java.sql.SQLException: ORA-00054: resource busy and acquire with NOWAIT specified')], 'EIMP': [('claim_ok', 'Claim enquiry success', 200, 'Claim status returned', 'INFO', 'Claim enquiry completed'), ('login_401', 'Insurance login invalid', 401, 'Invalid credentials', 'WARN', 'AuthenticationException: bad credentials'), ('claim_400', 'Missing policy number', 400, 'policyNumber required', 'WARN', 'MethodArgumentNotValidException: policyNumber must not be blank'), ('claim_404', 'Unknown claim', 404, 'Claim not found', 'WARN', 'com.eimp.ClaimNotFoundException: claim not found'), ('claim_npe', 'Claim assessor null pointer', 500, 'Claim processing failed', 'ERROR', 'java.lang.NullPointerException: Cannot invoke Assessor.getDecision() because assessor is null'), ('claim_timeout', 'Claim approval timeout', 504, 'Approval service timed out', 'ERROR', 'java.net.SocketTimeoutException: Read timed out'), ('upload_413', 'Claim document too large', 413, 'Maximum upload size exceeded', 'WARN', 'org.springframework.web.multipart.MaxUploadSizeExceededException: Maximum upload size exceeded'), ('premium_409', 'Duplicate premium reference', 409, 'Duplicate premium payment', 'ERROR', 'java.sql.SQLIntegrityConstraintViolationException: ORA-00001: unique constraint (EIMP.UK_PREMIUM_REF) violated'), ('renewal_502', 'Renewal gateway bad response', 502, 'Renewal upstream failure', 'ERROR', 'java.net.SocketException: Unexpected end of file from server'), ('policy_503', 'Policy service unavailable', 503, 'Policy service down', 'ERROR', 'java.net.ConnectException: Connection refused'), ('policy_oom', 'Policy PDF memory exhausted', 500, 'Policy PDF failed', 'ERROR', 'java.lang.OutOfMemoryError: GC overhead limit exceeded'), ('policy_stack', 'Policy mapping recursion', 500, 'Policy mapping failed', 'ERROR', 'java.lang.StackOverflowError'), ('claim_sql_timeout', 'Claims SQL query timeout', 503, 'Claims query timed out', 'ERROR', 'java.sql.SQLTimeoutException: ORA-01013: user requested cancel of current operation'), ('pool_exhausted', 'Claims DB connection pool exhausted', 503, 'Connection pool exhausted', 'ERROR', 'java.sql.SQLTransientConnectionException: HikariPool-2 - Connection is not available'), ('gateway_dns', 'Notification DNS failure', 503, 'Notification gateway not found', 'ERROR', 'java.net.UnknownHostException: notify.internal'), ('document_missing', 'Policy document missing', 500, 'Document retrieval failed', 'ERROR', 'java.io.FileNotFoundException: /opt/eimp/policies/POL100.pdf'), ('upload_denied', 'Claims upload permission denied', 500, 'Unable to save document', 'ERROR', 'java.nio.file.AccessDeniedException: /opt/eimp/uploads'), ('spring_bean', 'Claim processor bean failure', 503, 'Claims service startup failed', 'ERROR', 'org.springframework.beans.factory.BeanCreationException: Error creating bean with name claimProcessor'), ('spring_missing', 'Missing renewal repository bean', 503, 'Renewal service startup failed', 'ERROR', 'org.springframework.beans.factory.NoSuchBeanDefinitionException: No qualifying bean of type RenewalRepository'), ('tomcat_deploy', 'Tomcat WAR deployment failure', 503, 'Claims application deployment failed', 'ERROR', 'org.apache.catalina.LifecycleException: Failed to start component StandardContext[/claims]'), ('thread_block', 'Claim approval thread deadlock', 503, 'Claim processing blocked', 'ERROR', 'java.lang.IllegalStateException: Deadlock detected between ClaimLock and PolicyLock'), ('oracle_snapshot', 'Oracle snapshot too old', 500, 'Claims report failed', 'ERROR', 'java.sql.SQLException: ORA-01555: snapshot too old'), ('oracle_auth', 'Oracle invalid credentials', 503, 'Database login failed', 'ERROR', 'java.sql.SQLException: ORA-01017: invalid username/password; logon denied'), ('oracle_service', 'Oracle service not registered', 503, 'Database service unavailable', 'ERROR', 'java.sql.SQLRecoverableException: ORA-12514: TNS:listener does not currently know of service requested'), ('batch_recon', 'Premium reconciliation batch failed', 500, 'Premium reconciliation failed', 'ERROR', 'java.sql.SQLException: ORA-00054: resource busy and acquire with NOWAIT specified')]}
SCENARIO_MAP = {p:{r[0]:r for r in rows} for p,rows in SCENARIOS.items()}
STATE = defaultdict(lambda: {'logs': defaultdict(list), 'history': [], 'count': 0})
MAX_LINES = 1200
LOG_NAMES = ['access.log','error.log','application.log','catalina.out','database.log','batch.log','gc.log','thread_dump.log','startup.log']

def session_id():
    sid = request.headers.get('X-Lab-Session', '')
    if len(sid) > 80 or not sid or not all(c.isalnum() or c in '-_' for c in sid):
        return None
    return sid

def get_state():
    sid = session_id()
    return STATE[sid] if sid else None

def addlog(state, name, line):
    state['logs'][name].append(line)
    if len(state['logs'][name]) > MAX_LINES:
        state['logs'][name] = state['logs'][name][-MAX_LINES:]

@app.get('/')
def home(): return render_template('index.html')

@app.get('/api/scenarios')
def scenarios():
    return jsonify({p:[{'id':x[0], 'name':x[1], 'status':int(x[2])} for x in rows] for p,rows in SCENARIOS.items()})

@app.post('/api/simulate')
def simulate():
    state = get_state()
    if state is None: return jsonify(error='Missing or invalid X-Lab-Session'), 400
    body = request.get_json(silent=True) or {}
    project = body.get('project'); scenario = body.get('scenario')
    if project not in SCENARIO_MAP or scenario not in SCENARIO_MAP[project]:
        return jsonify(error='Unknown project or scenario'), 400
    key,name,status,message,level,reason = SCENARIO_MAP[project][scenario]
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    rid = f'{project}-REQ-{uuid.uuid4().hex[:8].upper()}'
    endpoint = '/api/' + ('banking' if project=='IBS' else 'insurance') + '/' + key.replace('_','/')
    method = 'POST' if any(x in key for x in ['transfer','login','claim_400','claim_500','account','document','premium']) else 'GET'
    ms = 5000 if status == 504 else 180 if status >= 500 else 48
    addlog(state,'access.log',f'{now} 127.0.0.1 "{method} {endpoint} HTTP/1.1" {status} {ms}ms requestId={rid}')
    addlog(state,'application.log',f'{now} INFO  [{rid}] {project} {name}: request received')
    addlog(state,'application.log',f'{now} INFO  [{rid}] Controller -> Service -> Repository processing started')
    addlog(state,'application.log',f'{now} {level:<5} [{rid}] {reason}')
    if level == 'ERROR':
        cls = reason.split(':')[0].strip()
        component = 'com.ibs' if project == 'IBS' else 'com.eimp'
        for frame in [f'at {component}.service.ProcessingService.execute(ProcessingService.java:142)',
                      f'at {component}.controller.RequestController.handle(RequestController.java:67)',
                      'at org.springframework.web.servlet.DispatcherServlet.doDispatch(DispatcherServlet.java:1089)',
                      'at org.apache.catalina.core.ApplicationFilterChain.doFilter(ApplicationFilterChain.java:162)']:
            addlog(state,'application.log',f'{now} ERROR [{rid}]     {frame}')
        if 'OutOfMemoryError' in reason:
            addlog(state,'gc.log',f'{now} [gc] [IBS/EIMP simulated] Pause Full (G1 Compaction Pause) 2048M->2047M(2048M)')
        if 'Deadlock' in reason:
            addlog(state,'thread_dump.log',f'{now} Found one Java-level deadlock [{rid}]: http-nio-8080-exec-3 BLOCKED waiting to lock AccountLock')
        if 'HikariPool' in reason:
            addlog(state,'application.log',f'{now} WARN  [{rid}] HikariPool - active=10 idle=0 waiting=15 max=10')
    addlog(state,'application.log',f'{now} INFO  [{rid}] Returning HTTP {status}')
    if int(status) >= 500:
        addlog(state,'error.log',f'{now} [error] [requestId={rid}] upstream request failed: {reason}')
        addlog(state,'catalina.out',f'{now} SEVERE [http-nio-8080-exec-3] [{rid}] {project} request failed: {reason}')
        if any(x in reason for x in ['ORA-', 'HikariPool', 'SQLException', 'SQLRecoverableException', 'SQLTransientConnectionException']):
            addlog(state,'database.log',f'{now} ERROR [{rid}] Simulated Oracle/database event: {reason}')
    elif int(status) == 409 and 'ORA-' in reason:
        addlog(state,'database.log',f'{now} ERROR [{rid}] {reason}')
    if 'batch' in key:
        addlog(state,'batch.log',f'{now} {level} [{rid}] job={project}_{key.upper()} status={"FAILED" if int(status)>=400 else "SUCCESS"} detail={reason}')
    if any(x in reason for x in ['BeanCreationException','NoSuchBeanDefinitionException','LifecycleException','BindException']):
        addlog(state,'startup.log',f'{now} SEVERE [{rid}] Application startup/deployment failure: {reason}')
    state['count'] += 1
    result={'project':project,'scenario':name,'requestId':rid,'method':method,'url':endpoint,'status':int(status),'response':{'message':message,'requestId':rid},'durationMs':ms,'timestamp':now}
    state['history'].insert(0,result)
    state['history'] = state['history'][:50]
    return jsonify(result)

@app.post('/api/http-test')
def http_test():
    # Same simulation as /api/simulate, but the HTTP response itself carries the chosen status.
    response = simulate()
    if isinstance(response, tuple):
        return response
    data = response.get_json()
    return jsonify(data), data['status'], {'X-Request-ID': data['requestId'], 'Cache-Control': 'no-store'}

@app.get('/api/logs/<name>')
def logs(name):
    state=get_state()
    if state is None: return jsonify(error='Missing session'),400
    if name not in LOG_NAMES:
        return jsonify(error='Unknown log'),404
    query=request.args.get('q','').lower()
    lines=state['logs'][name]
    if query: lines=[x for x in lines if query in x.lower()]
    return jsonify({'name':name,'lines':lines[-MAX_LINES:],'total':len(lines)})

@app.get('/api/history')
def history():
    state=get_state()
    if state is None: return jsonify(error='Missing session'),400
    return jsonify(state['history'])

@app.post('/api/reset')
def reset():
    sid=session_id()
    if not sid: return jsonify(error='Missing session'),400
    STATE.pop(sid,None)
    return jsonify(ok=True)

@app.get('/api/download/<name>')
def download(name):
    state=get_state()
    if state is None: return jsonify(error='Missing session'),400
    if name not in LOG_NAMES:
        return jsonify(error='Unknown log'),404
    return Response('\n'.join(state['logs'][name])+'\n',mimetype='text/plain',headers={'Content-Disposition':f'attachment; filename="{name}"'})

@app.get('/health')
def health(): return jsonify(status='UP', service='IBS-EIMP Simulation Lab')

from ibs_lab import register as register_ibs_lab
register_ibs_lab(app, get_state, addlog)

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=False)
