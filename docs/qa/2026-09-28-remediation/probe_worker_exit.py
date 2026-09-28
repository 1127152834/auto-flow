import asyncio, importlib.util, json, tempfile, time
from pathlib import Path
from uuid import uuid4
from autoflow.infrastructure.process.project_workflow_worker import ProjectWorkflowWorkerManager
root=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('proxy_fixture', root/'apps/backend/tests/integration/test_workflow_proxy_workers.py')
fixture=importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
async def main():
    rows=[]
    for i in range(3):
        with tempfile.TemporaryDirectory(prefix='autoflow-exit-probe-') as temp:
            manager=ProjectWorkflowWorkerManager(Path(temp),proxy_service=fixture.ProxyService())
            observed={}; original=manager._read
            async def read(worker):
                msg=await original(worker)
                if msg.get('type')=='finished':
                    observed['finished']=time.perf_counter()
                return msg
            manager._read=read
            async def event(_): pass
            try:
                result=await manager.run(run_id=str(uuid4()),execution_generation=3,execution_plan={'document':fixture.document('proxy_change_location')},parameters={},variables={},browser={},executable=None,on_event=event)
                rows.append({'iteration':i,'outcome':result.status,'after_finished_seconds':time.perf_counter()-observed['finished'],'busy':manager.busy()})
            finally: await manager.shutdown()
    print(json.dumps(rows,indent=2))
asyncio.run(main())
