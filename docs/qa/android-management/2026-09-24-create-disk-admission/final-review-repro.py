import asyncio, tempfile
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from autoflow.infrastructure.database.android_models import AndroidDeviceRow, AndroidOperationRow, AndroidResourceRow
from autoflow.infrastructure.database.android import SqlAlchemyDeviceRepository
from autoflow.infrastructure.database.android_operations import SqlAlchemyAndroidOperationRepository
from autoflow.infrastructure.database.android_resources import AndroidResourceRepository
from autoflow.application.android.verification import verify_lifecycle_operation
from autoflow.application.android.devices import AndroidDeviceService
from autoflow.application.android.images import AndroidImageService

async def main():
 with tempfile.TemporaryDirectory() as temporary:
  engine=create_engine('sqlite:///'+str(Path(temporary)/'review.db'))
  for model in (AndroidDeviceRow,AndroidOperationRow,AndroidResourceRow): model.__table__.create(engine)
  sessions=sessionmaker(engine,expire_on_commit=False)
  repository=SqlAlchemyDeviceRepository(sessions)
  operations=SqlAlchemyAndroidOperationRepository(sessions)
  resources=AndroidResourceRepository(sessions)
  op=operations.accept('workspace','old-start','device','start','digest',{})
  operations.transition(op.operation_id,'queued','running',{})
  op=operations.transition(op.operation_id,'running','needs_verification',{})
  repository.save({'deviceId':'device','workspaceId':'workspace','generation':2,'ownerRunId':None,'control':'recovery_required','androidStatus':'unknown','operation':{'id':op.operation_id,'state':'needs_verification','action':'start'}})
  started, release=asyncio.Event(),asyncio.Event()
  class Runtime:
   workspace_id='workspace'
   def lock(self): pass
   def unlock(self): pass
   async def manage(self,device,request,stage,save):device['androidStatus']='ready'
   async def inspect(self,device):
    started.set(); await release.wait(); return {'androidStatus':'ready'}
  devices=AndroidDeviceService(repository,Runtime())
  devices.management.operations=operations
  devices.management.workspace_identity='workspace'
  verification=asyncio.create_task(verify_lifecycle_operation(operations,devices,op,workspace_identity='workspace'))
  await started.wait()
  devices.operate('device',{'requestId':'newer-recover','action':'recover','deleteData':False})
  await devices.management.task
  newer=repository.claim('device','new-session');newer['control']='manual';repository.save(newer)
  assert newer['generation']==4
  release.set();await verification
  result=repository.get('device')
  print('LIFECYCLE_REPRO',{'beforeGeneration':4,'afterGeneration':result['generation'],'beforeControl':'manual','afterControl':result['control'],'beforeOwner':'new-session','afterOwner':result['ownerRunId']})
  assert result['generation']==2 and result['ownerRunId'] is None and result['control']=='idle'
  image_id='sha256:'+'a'*64
  resources.save('image',{'id':'image','imageId':image_id,'name':'fixture','reference':'local:fixture','state':'unregistered','revision':2,'workspaceId':'workspace','verification':{'state':'unknown'}})
  class ImageRuntime:
   workspace_id='workspace'
   async def inspect_image(self,ref):return {'imageId':image_id,'architecture':'arm64','os':'linux'}
  image_service=AndroidImageService(resources,SimpleNamespace(runtime=ImageRuntime(),list=lambda: []))
  await image_service.verify_server('image',{'check':'image_metadata'})
  print('IMAGE_REPRO',resources.get('image','image')['state'])
  assert resources.get('image','image')['state']=='verified'
  from fastapi import FastAPI
  import httpx
  from autoflow.adapters.http.android_management import android_management_router
  from autoflow.application.android.diagnostics import EnvironmentCheckService
  failed=operations.accept('workspace','failed-start','device','start','failed-digest',{})
  operations.transition(failed.operation_id,'queued','running',{})
  failed=operations.transition(failed.operation_id,'running','failed',{})
  device=repository.get('device');device.update(control='recovery_required',ownerRunId=None,operation={'id':failed.operation_id,'action':'start','state':'failed'});repository.save(device)
  app=FastAPI();app.include_router(android_management_router(EnvironmentCheckService(None),operations,devices=devices))
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
   response=await client.post('/api/v1/android/management/operations/'+failed.operation_id+'/verify',json={'requestId':'failed-start'})
  print('FAILED_VERIFY_REPRO',{'http':response.status_code,'operationState':response.json()['state'],'control':repository.get('device')['control']})
  assert response.status_code==200 and repository.get('device')['control']=='recovery_required'
  engine.dispose()
asyncio.run(main())
