"""Training-only IBS Oracle table, incident and batch job simulation for the Flask simulator.

No Oracle connection is made here. All data is synthetic and kept in browser-session memory.
"""
from datetime import datetime, timezone, timedelta
import time
import uuid

from flask import jsonify, render_template, request

SCENARIOS = [
    ('login_locked', 'Locked internet banking login', 401, 'IBS_USER_APP.IBS_USER', 'ORA-20111: Internet banking user is locked', 'Check failed login count and account status; unlock only through the approved workflow.'),
    ('otp_expired', 'Expired fund-transfer OTP', 401, 'IBS_USER_APP.IBS_OTP_CHALLENGE', 'OTP_VALIDATION_FAILED: Challenge expired', 'Verify expiry time and request a new OTP; do not disclose OTP values.'),
    ('session_expired', 'Session expired immediately', 401, 'IBS_USER_APP.IBS_AUTH_SESSION', 'SESSION_EXPIRED: Access token expired', 'Check EXPIRES_AT, clock synchronization and session revocation.'),
    ('role_denied', 'Access denied for inactive role', 403, 'IBS_USER_APP.IBS_ROLE', 'AccessDeniedException: Required role inactive', 'Check IBS_USER_ROLE and IBS_ROLE; obtain authorization before changing access.'),
    ('account_frozen', 'Frozen account cannot transfer', 409, 'IBS_APP.IBS_ACCOUNT', 'ORA-20122: Source account is FROZEN', 'Review account status and audit; never unfreeze without authorization.'),
    ('transfer_processing', 'Transfer debited but still processing', 202, 'IBS_APP.IBS_FUND_TRANSFER', 'Transfer posting incomplete: credit confirmation pending', 'Trace bank transactions and transfer events; do not blindly retry.'),
    ('duplicate_reference', 'Duplicate payment request', 409, 'IBS_APP.IBS_IDEMPOTENCY_REQUEST', 'ORA-00001: unique constraint (IBS_APP.UQ_IDEMPOTENCY_REQUEST_1) violated', 'Check request key and transaction postings before retry or reversal.'),
    ('recon_mismatch', 'Payment reconciliation amount mismatch', 500, 'IBS_APP.IBS_RECON_RECORD', 'RECON_AMOUNT_MISMATCH: external 15000.00 internal 14900.00', 'Compare reconciliation records, exceptions and settlement state.'),
    ('bill_unknown', 'Bill payment gateway result unknown', 504, 'IBS_APP.IBS_BILL_PAYMENT_ATTEMPT', 'SocketTimeoutException: Payment gateway returned UNKNOWN', 'Confirm external result before initiating another payment.'),
    ('notification_failed', 'Transaction notification delivery failed', 502, 'IBS_APP.IBS_NOTIFICATION_ATTEMPT', 'SMS_PROVIDER_502: Delivery rejected by provider', 'Verify preferences and provider attempts; retry only if allowed.'),
    ('statement_missing', 'Statement marked complete but PDF failed', 500, 'IBS_APP.IBS_STATEMENT_DOCUMENT', 'java.io.FileNotFoundException: generated bank statement missing', 'Compare statement request, generation status and document path.'),
    ('job_failed', 'End of day job fails with database lock', 500, 'IBS_APP.IBS_JOB_RUN', 'ORA-00054: resource busy and acquire with NOWAIT specified', 'Identify blocker, evaluate rerun safety and validate ledger results.'),
]
SCENARIO_MAP = {x[0]: x for x in SCENARIOS}
JOBS = [
    ('IBS_DAILY_RECON', 'Daily payment reconciliation', '0 2 * * *', 'IBS_RECON_RUN / IBS_RECON_RECORD'),
    ('IBS_PAYMENT_SETTLEMENT', 'Payment settlement', '30 2 * * *', 'IBS_SETTLEMENT_BATCH'),
    ('IBS_EOD_GL_POSTING', 'End-of-day general ledger posting', '0 23 * * *', 'IBS_GL_JOURNAL / IBS_GL_JOURNAL_LINE'),
    ('IBS_STATEMENT_GENERATION', 'Statement generation', '0 */4 * * *', 'IBS_STATEMENT_REQUEST / IBS_STATEMENT_DOCUMENT'),
    ('IBS_NOTIFICATION_RETRY', 'Failed SMS and email notification retry', '*/30 * * * *', 'IBS_NOTIFICATION / IBS_NOTIFICATION_ATTEMPT'),
    ('IBS_TRANSFER_STATUS_SYNC', 'Pending transfer status synchronization', '*/15 * * * *', 'IBS_FUND_TRANSFER / IBS_TRANSFER_EVENT'),
]
JOB_MAP = {x[0]: x for x in JOBS}
FAILURES = {
    'none': None,
    'db_lock': 'ORA-00054: resource busy and acquire with NOWAIT specified',
    'tablespace': 'ORA-01653: unable to extend table IBS_APP.IBS_JOB_RUN',
    'db_timeout': 'java.sql.SQLTimeoutException: ORA-01013: operation timed out',
    'mismatch': 'RECON_MISMATCH: External amount differs from internal posting',
    'connection_pool': 'java.sql.SQLTransientConnectionException: HikariPool - Connection not available',
}

def utc():
    return datetime.now(timezone.utc)

def stamp():
    return utc().strftime('%Y-%m-%d %H:%M:%S')

def register(app, get_state, addlog):
    def lab():
        s = get_state()
        if s is None:
            return None
        return s.setdefault('ibs_lab', {'tables': {}, 'incidents': [], 'runs': [], 'next_id': 9400000})

    def row(s, table, values):
        values = dict(values)
        values.setdefault('_TRAINING_ONLY', 'YES')
        tbl = s['tables'].setdefault(table, [])
        tbl.insert(0, values)
        del tbl[80:]

    def nxt(s):
        s['next_id'] += 1
        return s['next_id']

    def log(s, rid, detail, http=200, topic='incident', level='ERROR'):
        t = stamp()
        lstate = get_state()
        addlog(lstate, 'access.log', f'{t} 127.0.0.1 "POST /api/ibs-lab/{topic} HTTP/1.1" {http} 220ms requestId={rid}')
        addlog(lstate, 'application.log', f'{t} INFO  [{rid}] IBS Controller -> Service -> Repository: {topic} started')
        addlog(lstate, 'application.log', f'{t} {level:<5} [{rid}] {detail} [SIMULATED TRAINING]')
        addlog(lstate, 'database.log', f'{t} {level:<5} [{rid}] IBS_APP/IBS_USER_APP synthetic Oracle event: {detail}')
        if http >= 500:
            addlog(lstate, 'error.log', f'{t} [error] [requestId={rid}] IBS upstream request failed: {detail}')
            addlog(lstate, 'catalina.out', f'{t} SEVERE [{rid}] Simulated Java service: {detail}')

    def seed_incident(s, key, rid):
        t = stamp()
        if key in ('login_locked','otp_expired','session_expired','role_denied'):
            uid = nxt(s)
            row(s, 'IBS_USER_APP.IBS_USER', dict(USER_ID=uid, CUSTOMER_ID=920001, USERNAME='LAB_IBS_CUSTOMER', PASSWORD_HASH='[REDACTED TRAINING]', ACCOUNT_STATUS='LOCKED' if key=='login_locked' else 'ACTIVE', FAILED_LOGIN_COUNT=5 if key=='login_locked' else 0))
            if key == 'login_locked':
                row(s, 'IBS_USER_APP.IBS_LOGIN_AUDIT', dict(LOGIN_AUDIT_ID=nxt(s), USER_ID=uid, LOGIN_TIME=t, LOGIN_RESULT='LOCKED', SOURCE_IP='192.0.2.10', REQUEST_ID=rid))
            if key == 'otp_expired':
                row(s, 'IBS_USER_APP.IBS_OTP_CHALLENGE', dict(OTP_CHALLENGE_ID=nxt(s), USER_ID=uid, OPERATION_REFERENCE='OTP-'+rid[-8:], OTP_HASH='[REDACTED TRAINING]', EXPIRY_TIME=(utc()-timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S'), ATTEMPT_COUNT=3, STATUS='EXPIRED'))
            if key == 'session_expired':
                row(s, 'IBS_USER_APP.IBS_AUTH_SESSION', dict(SESSION_ID=nxt(s), USER_ID=uid, SESSION_TOKEN_HASH='[REDACTED TRAINING]', EXPIRES_AT=(utc()-timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'), REVOKED_AT=None, SESSION_STATUS='EXPIRED'))
            if key == 'role_denied':
                role_id = nxt(s)
                row(s, 'IBS_USER_APP.IBS_ROLE', dict(ROLE_ID=role_id, ROLE_CODE='IBS_APPROVER', ROLE_NAME='Banking approver', IS_ACTIVE='N'))
                row(s, 'IBS_USER_APP.IBS_USER_ROLE', dict(USER_ROLE_ID=nxt(s), USER_ID=uid, ROLE_ID=role_id, ASSIGNED_AT=t))
        elif key in ('account_frozen','transfer_processing','duplicate_reference'):
            aid=nxt(s)
            row(s, 'IBS_APP.IBS_ACCOUNT', dict(ACCOUNT_ID=aid, CUSTOMER_ID=920001, ACCOUNT_NUMBER='LAB'+str(aid), ACCOUNT_TYPE_ID=92001, BRANCH_ID=92001, CURRENCY_CODE='INR', AVAILABLE_BALANCE=50000, ACCOUNT_STATUS='FROZEN' if key=='account_frozen' else 'ACTIVE', OPENED_AT=t))
            if key != 'account_frozen':
                tid=nxt(s)
                tref='LAB-TXN-'+rid[-8:]
                row(s, 'IBS_APP.IBS_FUND_TRANSFER', dict(TRANSFER_ID=tid, TRANSACTION_REFERENCE=tref, SOURCE_ACCOUNT_ID=aid, DESTINATION_ACCOUNT_ID=920002, BENEFICIARY_ID=None, TRANSFER_TYPE='IMPS', AMOUNT=5000, CURRENCY_CODE='INR', TRANSFER_STATUS='PROCESSING', COMPLETED_AT=None))
                row(s, 'IBS_APP.IBS_TRANSFER_EVENT', dict(TRANSFER_EVENT_ID=nxt(s), TRANSFER_ID=tid, EVENT_TYPE='DEBIT_POSTED', EVENT_STATUS='SUCCESS', EVENT_DETAILS='Credit confirmation not received', EVENT_TIME=t))
                row(s, 'IBS_APP.IBS_BANK_TRANSACTION', dict(TRANSACTION_ID=nxt(s), ACCOUNT_ID=aid, TRANSFER_ID=tid, TRANSACTION_REFERENCE='DR-'+tref, TRANSACTION_TYPE='TRANSFER', AMOUNT=5000, DIRECTION='DEBIT', TRANSACTION_STATUS='POSTED', TRANSACTION_DATE=t))
                if key=='duplicate_reference':
                    row(s,'IBS_APP.IBS_IDEMPOTENCY_REQUEST',dict(IDEMPOTENCY_ID=nxt(s), REQUEST_KEY='LAB-KEY-'+rid[-8:], TRANSFER_ID=tid, REQUEST_STATUS='PROCESSING', RESPONSE_CODE='409'))
        elif key=='recon_mismatch':
            run=nxt(s)
            row(s,'IBS_APP.IBS_RECON_RUN',dict(RECON_RUN_ID=run, RUN_REFERENCE='LAB-RECON-'+rid[-8:], PROCESSING_DATE=t[:10], INPUT_FILE_REF='payments_'+t[:10]+'.txt', RUN_STATUS='FAILED'))
            row(s,'IBS_APP.IBS_RECON_RECORD',dict(RECON_RECORD_ID=nxt(s), RECON_RUN_ID=run, TRANSACTION_REFERENCE='LAB-PAY-'+rid[-8:], EXTERNAL_AMOUNT=15000, INTERNAL_AMOUNT=14900, MATCH_STATUS='MISMATCHED'))
            row(s,'IBS_APP.IBS_RECON_EXCEPTION',dict(EXCEPTION_ID=nxt(s), RECON_RUN_ID=run, TRANSACTION_REFERENCE='LAB-PAY-'+rid[-8:], EXPECTED_AMOUNT=15000, ACTUAL_AMOUNT=14900, EXCEPTION_TYPE='AMOUNT_MISMATCH', EXCEPTION_STATUS='OPEN'))
        elif key=='bill_unknown':
            payment=nxt(s)
            row(s,'IBS_APP.IBS_BILL_PAYMENT',dict(PAYMENT_ID=payment,CUSTOMER_ID=920001,ACCOUNT_ID=920001,BILLER_ID=920001,CONSUMER_REFERENCE='LAB-CONSUMER',AMOUNT=2500,PAYMENT_STATUS='PENDING',TRANSACTION_REFERENCE='LAB-BILL-'+rid[-8:]))
            row(s,'IBS_APP.IBS_BILL_PAYMENT_ATTEMPT',dict(ATTEMPT_ID=nxt(s), PAYMENT_ID=payment, ATTEMPT_REFERENCE='LAB-GW-'+rid[-8:], GATEWAY_STATUS='UNKNOWN', GATEWAY_RESPONSE='Timeout; cannot confirm settlement', ATTEMPTED_AT=t))
        elif key=='notification_failed':
            nid=nxt(s)
            row(s,'IBS_APP.IBS_NOTIFICATION',dict(NOTIFICATION_ID=nid,CUSTOMER_ID=920001,EVENT_REFERENCE='LAB-TXN-'+rid[-8:],CHANNEL='SMS',MESSAGE_TEMPLATE='PAYMENT_ALERT',NOTIFICATION_STATUS='FAILED'))
            row(s,'IBS_APP.IBS_NOTIFICATION_ATTEMPT',dict(NOTIFICATION_ATTEMPT_ID=nxt(s),NOTIFICATION_ID=nid,PROVIDER_REFERENCE='LAB-SMS-'+rid[-8:],DELIVERY_STATUS='FAILED',ATTEMPTED_AT=t))
        elif key=='statement_missing':
            sr=nxt(s)
            row(s,'IBS_APP.IBS_STATEMENT_REQUEST',dict(STATEMENT_REQUEST_ID=sr,CUSTOMER_ID=920001,ACCOUNT_ID=920001,DATE_FROM='2026-10-01',DATE_TO='2026-10-31',REQUEST_STATUS='COMPLETED'))
            row(s,'IBS_APP.IBS_STATEMENT_DOCUMENT',dict(STATEMENT_DOCUMENT_ID=nxt(s),STATEMENT_REQUEST_ID=sr,DOCUMENT_URI='/opt/ibs/statements/LAB_MISSING.pdf',GENERATION_STATUS='FAILED',GENERATED_AT=None))
        else:
            jid=nxt(s)
            row(s,'IBS_APP.IBS_BATCH_JOB',dict(JOB_ID=jid,JOB_CODE='IBS_EOD_GL_POSTING',JOB_NAME='End of day GL posting',CRON_EXPRESSION='0 23 * * *',JOB_STATUS='ACTIVE'))
            row(s,'IBS_APP.IBS_JOB_RUN',dict(JOB_RUN_ID=nxt(s),JOB_ID=jid,STARTED_AT=t,ENDED_AT=t,RUN_STATUS='FAILED',ERROR_MESSAGE='ORA-00054: resource busy'))

    def job_view(s, j):
        code,name,cron,tab=j
        active=next((r for r in s['runs'] if r['jobCode']==code and r['status']=='RUNNING'),None)
        latest=next((r for r in s['runs'] if r['jobCode']==code),None)
        return dict(code=code,name=name,cron=cron,tables=tab, status='RUNNING' if active else 'IDLE',lastStatus=latest['status'] if latest else 'NOT_RUN',lastRunId=latest['runId'] if latest else None)

    def settle(s):
        for r in s['runs']:
            if r['status']=='RUNNING' and time.monotonic()-r['monotonicStarted']>=12:
                failed = r['failure']!='none'
                r['status']='FAILED' if failed else 'SUCCEEDED'
                r['endedAt']=stamp()
                why=FAILURES.get(r['failure']) or 'Job completed: all test records processed'
                r['message']=why
                for record in s['tables'].get('IBS_APP.IBS_JOB_RUN',[]):
                    if record['JOB_RUN_ID']==r['numericRunId']:
                        record.update(ENDED_AT=r['endedAt'],RUN_STATUS=r['status'],ERROR_MESSAGE=why if failed else None)
                log(s, r['runId'], why, 500 if failed else 200, topic='batch/'+r['jobCode'], level='ERROR' if failed else 'INFO')
                addlog(get_state(),'batch.log', f'{stamp()} {"ERROR" if failed else "INFO"} [{r["runId"]}] job={r["jobCode"]} runStatus={r["status"]} detail={why}')
                if r['jobCode']=='IBS_DAILY_RECON':
                    run_id=nxt(s)
                    row(s,'IBS_APP.IBS_RECON_RUN',dict(RECON_RUN_ID=run_id,RUN_REFERENCE='LAB-'+r['runId'][-10:],PROCESSING_DATE=stamp()[:10],INPUT_FILE_REF='training_daily_payments.txt',RUN_STATUS='FAILED' if failed else 'COMPLETED'))
                    row(s,'IBS_APP.IBS_RECON_RECORD',dict(RECON_RECORD_ID=nxt(s),RECON_RUN_ID=run_id,TRANSACTION_REFERENCE='LAB-RECON-001',EXTERNAL_AMOUNT=15000,INTERNAL_AMOUNT=14900 if failed else 15000,MATCH_STATUS='MISMATCHED' if failed else 'MATCHED'))
                    if failed:
                        row(s,'IBS_APP.IBS_RECON_EXCEPTION',dict(EXCEPTION_ID=nxt(s),RECON_RUN_ID=run_id,TRANSACTION_REFERENCE='LAB-RECON-001',EXPECTED_AMOUNT=15000,ACTUAL_AMOUNT=14900,EXCEPTION_TYPE='AMOUNT_MISMATCH',EXCEPTION_STATUS='OPEN'))

    @app.get('/ibs-training')
    def ibs_training_home():
        return render_template('ibs_training.html')

    @app.get('/api/ibs-lab/scenarios')
    def ibs_scenarios():
        return jsonify([dict(id=k,name=n,http=code,table=table) for k,n,code,table,_,_ in SCENARIOS])

    @app.post('/api/ibs-lab/simulate')
    def ibs_simulate():
        s=lab()
        if s is None:return jsonify(error='Missing X-Lab-Session'),400
        body=request.get_json(silent=True) or {}
        key=body.get('scenario')
        if key not in SCENARIO_MAP:return jsonify(error='Unknown scenario'),400
        key,name,code,table,error,rca=SCENARIO_MAP[key]
        rid='IBS-DB-'+uuid.uuid4().hex[:10].upper()
        seed_incident(s,key,rid)
        log(s,rid,error,code,topic='incident/'+key,level='WARN' if code<500 else 'ERROR')
        i=dict(requestId=rid,scenario=key,title=name,http=code,table=table,error=error,rca=rca,timestamp=stamp())
        s['incidents'].insert(0,i)
        del s['incidents'][50:]
        return jsonify({k:v for k,v in i.items() if k!='rca'})

    @app.get('/api/ibs-lab/incidents')
    def ibs_incidents():
        s=lab()
        return jsonify(s['incidents'] if s else [])

    @app.get('/api/ibs-lab/rca/<rid>')
    def ibs_rca(rid):
        s=lab()
        if s is None:return jsonify(error='Missing session'),400
        i=next((x for x in s['incidents'] if x['requestId']==rid),None)
        return jsonify({'rca':i['rca']} if i else {'error':'Not found'}),200 if i else 404

    @app.get('/api/ibs-lab/tables')
    def ibs_tables():
        s=lab()
        if s is None:return jsonify(error='Missing session'),400
        return jsonify(s['tables'])

    @app.get('/api/ibs-lab/jobs')
    def ibs_jobs():
        s=lab()
        if s is None:return jsonify(error='Missing session'),400
        settle(s)
        return jsonify({'jobs':[job_view(s,j) for j in JOBS], 'runs':[{k:v for k,v in x.items() if k not in ('monotonicStarted',)} for x in s['runs'][:30]],'failureModes':[{'id':k,'label':(v or 'No error / success')} for k,v in FAILURES.items()]})

    @app.post('/api/ibs-lab/jobs/<code>/start')
    def ibs_job_start(code):
        s=lab()
        if s is None:return jsonify(error='Missing session'),400
        if code not in JOB_MAP:return jsonify(error='Unknown batch job'),404
        settle(s)
        if any(r['jobCode']==code and r['status']=='RUNNING' for r in s['runs']):return jsonify(error='This job is already running'),409
        body=request.get_json(silent=True) or {}
        failure=body.get('failure','none')
        if failure not in FAILURES:return jsonify(error='Unknown failure mode'),400
        j=JOB_MAP[code]
        jid=9300001+list(JOB_MAP).index(code)
        if not any(r['JOB_ID']==jid for r in s['tables'].get('IBS_APP.IBS_BATCH_JOB',[])):
            row(s,'IBS_APP.IBS_BATCH_JOB',dict(JOB_ID=jid, JOB_CODE=code, JOB_NAME=j[1], CRON_EXPRESSION=j[2], JOB_STATUS='ACTIVE'))
        n=nxt(s);rid='IBS-RUN-'+uuid.uuid4().hex[:10].upper()
        r=dict(runId=rid, numericRunId=n,jobCode=code,status='RUNNING',failure=failure,startedAt=stamp(),endedAt=None,message='Batch processing started',monotonicStarted=time.monotonic())
        s['runs'].insert(0,r)
        row(s,'IBS_APP.IBS_JOB_RUN',dict(JOB_RUN_ID=n,JOB_ID=jid,STARTED_AT=r['startedAt'],ENDED_AT=None,RUN_STATUS='RUNNING',ERROR_MESSAGE=None))
        addlog(get_state(),'batch.log',f'{stamp()} INFO  [{rid}] job={code} status=RUNNING trigger=MANUAL failureMode={failure}')
        addlog(get_state(),'application.log',f'{stamp()} INFO  [{rid}] BatchScheduler: manually triggered {code} (SIMULATED)')
        return jsonify({k:v for k,v in r.items() if k!='monotonicStarted'})

    @app.post('/api/ibs-lab/jobs/<code>/stop')
    def ibs_job_stop(code):
        s=lab()
        if s is None:return jsonify(error='Missing session'),400
        if code not in JOB_MAP:return jsonify(error='Unknown batch job'),404
        settle(s)
        r=next((x for x in s['runs'] if x['jobCode']==code and x['status']=='RUNNING'),None)
        if not r:return jsonify(error='No running job to stop'),409
        r['status']='STOPPED';r['endedAt']=stamp();r['message']='Stopped manually (simulator only); represented as FAILED in Oracle IBS_JOB_RUN'
        for record in s['tables'].get('IBS_APP.IBS_JOB_RUN',[]):
            if record['JOB_RUN_ID']==r['numericRunId']:
                record.update(RUN_STATUS='FAILED',ENDED_AT=r['endedAt'],ERROR_MESSAGE='MANUALLY_STOPPED (simulation)')
        addlog(get_state(),'batch.log',f'{stamp()} WARN  [{r["runId"]}] job={code} status=STOPPED requested_by=LAB_USER')
        addlog(get_state(),'application.log',f'{stamp()} WARN  [{r["runId"]}] Simulated batch stopped by operator; no real OS job was terminated')
        return jsonify({k:v for k,v in r.items() if k!='monotonicStarted'})
