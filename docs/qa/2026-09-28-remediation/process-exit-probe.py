import json, os, subprocess, sys, tempfile, time
from pathlib import Path
from autoflow.infrastructure.process import project_browser_processes as p
observations=[]
original=p._native_arguments

def observe(pid):
    result=original(pid)
    if result is None:
        try:
            state=subprocess.check_output(['ps','-p',str(pid),'-o','stat='],text=True).strip()
        except subprocess.CalledProcessError:
            state='gone'
        observations.append({'pid':pid,'state':state,'exists':p._process_exists(pid),'birth':p.process_birth(pid)})
    return result
p._native_arguments=observe
failures=[]
with tempfile.TemporaryDirectory(prefix='autoflow-owned-process-probe-') as raw:
    directory=Path(raw).resolve()
    for attempt in range(100):
        child=subprocess.Popen([sys.executable,'-c','import time; print("READY", flush=True); time.sleep(0.01)','--project-workflow-worker'],env={**os.environ,'CLOAKBROWSER_CACHE_DIR':str(directory)},start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        try:
            assert child.stdout.readline() == b'READY\n'
            birth=p.process_birth(child.pid)
            try:
                p.capture_processes(child.pid,birth,directory,None,strict_ownership=True)
            except RuntimeError as error:
                failures.append({'attempt':attempt,'child':child.pid,'error':str(error),'observations':observations[-5:]})
        finally:
            child.wait(timeout=5)
        if failures: break
print(json.dumps({'kind':'real POSIX process ownership boundary, not workflow execution','attempts':attempt+1,'failures':failures,'unavailableObservations':observations,'ownedChildrenReaped':True},indent=2))
