import hashlib,json,pathlib,subprocess,datetime
root=pathlib.Path('/opt/noor')
def run(args):
    return subprocess.check_output(args,text=True,cwd=root).strip()
result={'measured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release_sha':(root/'.release-sha').read_text().strip(),'env_sha256':hashlib.sha256((root/'.env').read_bytes()).hexdigest(),'containers':{}}
probe="""import asyncio,hashlib,json,pathlib,time
from src.core.config import settings
from src.worker import WorkerSettings
safe={key:getattr(settings,key,None) for key in ('test_channel_restore_mode','wazzup_channel_id','wazzup_outbound_allowed_channel_id','telegram_allowed_inbound_phone')}
channel=str(safe['wazzup_channel_id'] or '')
async def inspect_stock():
    from redis.asyncio import Redis
    redis=Redis.from_url(str(settings.redis_url),decode_responses=True)
    try:
        keys={'v2':'zoho:inventory:stock_state:v2','legacy':'zoho:inventory:stock_snapshot:v1'}
        result={}
        for label,key in keys.items():
            raw=await redis.get(key)
            data=json.loads(raw) if raw else None
            result[label]={'exists':raw is not None,'ttl':await redis.ttl(key),'items':len(data.get('items',[])) if isinstance(data,dict) else None,'coverage':data.get('coverage') if isinstance(data,dict) else None,'full_at':data.get('full_at') if isinstance(data,dict) else None,'delta_at':data.get('delta_at') if isinstance(data,dict) else None,'coverage_evidence_present':bool(data.get('coverage_evidence')) if isinstance(data,dict) else False}
        raw=await redis.get('zoho:inventory:rate_limited_until')
        result['cooldown_remaining_seconds']=max(0,float(raw)-time.time()) if raw else 0
        return result
    finally:
        await redis.aclose()
stock=asyncio.run(inspect_stock())
paths=['src/core/config.py','src/worker.py','src/integrations/inventory/zoho_inventory.py','src/integrations/inventory/stock_state.py','src/integrations/inventory/sync.py','src/llm/engine.py','src/llm/customer_intent_tools.py','src/services/quotation_retry.py']
print(json.dumps({'release_sha':pathlib.Path('.release-sha').read_text().strip(),'stock':stock,'safety_fingerprint':hashlib.sha256(json.dumps(safe,sort_keys=True).encode()).hexdigest(),'restore_mode':safe['test_channel_restore_mode'],'telegram_test_phone_0665':str(safe['telegram_allowed_inbound_phone'] or '').endswith('0665'),'sender_matches_allowlist':bool(channel) and channel==safe['wazzup_outbound_allowed_channel_id'],'incremental_enabled':getattr(settings,'zoho_stock_incremental_enabled',False),'coverage_evidence_present':bool(getattr(settings,'zoho_stock_coverage_evidence','')),'bulk_size':getattr(settings,'zoho_stock_bulk_size',0),'functions':[getattr(f,'name',str(f)) for f in WorkerSettings.functions],'crons':[{'name':c.coroutine.__name__,'minute':str(c.minute),'hour':str(c.hour),'run_at_startup':c.run_at_startup} for c in WorkerSettings.cron_jobs],'hashes':{p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths if pathlib.Path(p).is_file()}}))"""
for service in ('app','worker','db','redis','nginx'):
    ident=run(['docker','compose','ps','--all','--quiet',service])
    if not ident:
        result['containers'][service]={'missing':True};continue
    data=json.loads(run(['docker','inspect',ident]))[0]
    state=data['State']
    row={'id':ident,'image':data['Image'],'status':state['Status'],'started_at':state['StartedAt'],'restart_count':data['RestartCount'],'oom_killed':state['OOMKilled']}
    if service in ('app','worker') and state['Running']:
        row['runtime']=json.loads(run(['docker','exec',ident,'python','-c',probe]))
    result['containers'][service]=row
print(json.dumps(result,indent=2))
