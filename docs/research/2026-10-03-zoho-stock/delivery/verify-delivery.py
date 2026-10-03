import hashlib,json,sys
from pathlib import Path
before=json.loads(Path('/tmp/tj-uvld-runtime-before.json').read_text())
after=json.loads(Path('/tmp/tj-uvld-runtime-after.json').read_text())
health=json.loads(Path('/tmp/tj-uvld-health-after.json').read_text())
root=Path('/home/me/code/treejar/.worktrees/tj-uvld-stock-sync')
sha=sys.argv[1]
checks={}
checks['host_release_exact']=after['release_sha']==sha
checks['env_unchanged']=before['env_sha256']==after['env_sha256']
checks['https_health_exact']=health.get('status')=='ok' and health.get('release_sha')==sha
checks['database_and_redis_health']=all(health['dependencies'][s]['status']=='ok' for s in ('database','redis'))
for service in ('db','redis','nginx'):
    checks[f'{service}_container_preserved']=before['containers'][service]['id']==after['containers'][service]['id']
for service in ('app','worker'):
    row=after['containers'][service]
    runtime=row['runtime']
    checks[f'{service}_new_running_container']=row['id']!=before['containers'][service]['id'] and row['status']=='running' and not row['oom_killed'] and row['restart_count']==0
    checks[f'{service}_release_exact']=runtime['release_sha']==sha
    checks[f'{service}_safety_unchanged']=runtime['safety_fingerprint']==before['containers'][service]['runtime']['safety_fingerprint'] and runtime['restore_mode'] and runtime['sender_matches_allowlist'] and runtime['telegram_test_phone_0665']
    checks[f'{service}_delta_gate_closed']=not runtime['incremental_enabled'] and not runtime['coverage_evidence_present']
    checks[f'{service}_unmodified_bulk_configuration']=runtime['bulk_size']==before['containers'][service]['runtime']['bulk_size']==0
    checks[f'{service}_eight_source_hashes_exact']=len(runtime['hashes'])==8 and all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in runtime['hashes'].items())
    allowed={'process_incoming_batch','retry_pending_quotation','refresh_conversation_summary','refresh_zoho_stock_snapshot','refresh_zoho_stock_delta','reconcile_telegram_webhook'}
    checks[f'{service}_restore_functions_exact']=set(runtime['functions'])==allowed
    checks[f'{service}_fallback_crons_exact']=set(c['name'] for c in runtime['crons'])=={'refresh_zoho_stock_snapshot','reconcile_telegram_webhook'}
stock=after['containers']['worker']['runtime']['stock']
checks['v2_generation_live']=stock['v2']['exists'] and stock['v2']['items']>0 and 86400<stock['v2']['ttl']<=172800 and stock['v2']['full_at'] is not None and stock['v2']['delta_at'] is None and not stock['v2']['coverage_evidence_present']
checks['legacy_last_full_mirror']=stock['legacy']['exists'] and stock['legacy']['items']==stock['v2']['items'] and 86400<stock['legacy']['ttl']<=172800
out={'expected_release_sha':sha,'before_measured_at_utc':before['measured_at_utc'],'after_measured_at_utc':after['measured_at_utc'],'checks':checks,'passed':all(checks.values()),'limitations':['No live customer quotation or business mutation.','Delta eligibility is unproved and disabled.','This is a bounded rollout check, not optimized24h savings evidence.']}
print(json.dumps(out,indent=2))
raise SystemExit(0 if out['passed'] else 1)
