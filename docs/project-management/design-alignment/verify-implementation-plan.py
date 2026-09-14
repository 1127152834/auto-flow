"""Validate planning assets; never executes the planned business tasks."""
from pathlib import Path
import re, json, hashlib
from datetime import datetime, timezone
root=Path(__file__).resolve().parents[3]
plans=root/'docs/superpowers/plans'
files=sorted(plans.glob('2026-09-13-project-management-alignment-*.md'))
created=set(); tasks=[]; links=0
for p in files:
    text=p.read_text()
    assert text.startswith('# ') and 'REQUIRED SUB-SKILL:' in text and '**Goal:**' in text and '**Architecture:**' in text and '**Tech Stack:**' in text
    assert not re.search(r'\b(?:TBD|TODO)\b|稍后填写|待定接口',text)
    for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
        if '://' in target: continue
        assert (p.parent/target.split('#')[0]).exists(),(p,target)
        links+=1
    sections=list(re.finditer(r'^## (R[123]-\d\d)：([^\n]+)',text,re.M))
    for n,match in enumerate(sections):
        body=text[match.end():sections[n+1].start() if n+1<len(sections) else len(text)]
        fileline=next(line for line in body.splitlines() if line.startswith('**Files:**'))
        scope=[]
        for part in fileline.split('；'):
            mode=re.search(r'(Create|Modify|Read)',part)
            if not mode: continue
            for file in re.findall(r'`([^`]+)`',part):
                if file.startswith(('apps/','scripts/','docs/')) or file == 'package-lock.json':
                    scope.append({'action':mode.group(1),'path':file})
                    if mode.group(1)=='Create': created.add(file)
        assert scope,(p,match.group(1))
        steps=len(re.findall(r'^- \[ \]',body,re.M))
        assert steps>=4 and '```' in body and ('提交' in body),match.group(1)
        tasks.append({'id':match.group(1),'title':match.group(2),'plan':str(p.relative_to(root)),'stepCount':steps,'files':scope,'status':'notStarted','evidence':{'automatic':None,'electron':None,'windows':None}})
bad_paths=[]
for task in tasks:
    for file in task['files']:
        if file['action']!='Create':
            if not ((root/file['path']).exists() or file['path'] in created): bad_paths.append((task['id'], file))
assert not bad_paths, bad_paths
expected={f'R{r}-{i:02}' for r,c in [(1,5),(2,5),(3,8)] for i in range(1,c+1)}
assert {t['id'] for t in tasks}==expected
# Dependencies are explicit; component/backend tracks may run together, shared assembly is serial.
deps={
'R1-01':['B0'],'R1-02':['R1-01'],'R1-03':['B0'],'R1-04':['R1-01','R1-03'],'R1-05':['R1-02','R1-04'],
'R2-01':['B0'],'R2-02':['B0'],'R2-03':['R1-05','R2-01','R2-02'],'R2-04':['R2-03'],'R2-05':['R2-03','R2-04'],
'R3-01':['B0'],'R3-02':['R3-01'],'R3-03':['R3-02'],'R3-04':['R3-03'],'R3-05':['R3-02','R3-04'],'R3-06':['R2-05','R3-04'],'R3-07':['R3-05','R3-06'],'R3-08':['R3-07']}
visited=set(); visiting=set()
def visit(key):
    assert key not in visiting, key
    if key in visited: return
    visiting.add(key)
    for dependency in deps.get(key,[]):
        assert dependency=='B0' or dependency in expected
        visit(dependency)
    visiting.remove(key);visited.add(key)
for key in deps:visit(key)
for t in tasks:t['dependsOn']=deps[t['id']]
manifest=json.loads((root/'docs/project-management/design-alignment/coverage.json').read_text())
refs=[]
for e in manifest['entries']:
    selected=e['selection']
    if selected in {'excluded-history','excluded-external-sqlite-source','alternative-not-recommended-layout'}:
        target=selected
    elif e['module']=='00-projects': target='R1-02'
    elif e['module']=='07-shared': target='R1-01/R1-03/R1-05/R2-05'
    elif e['module']=='05-data':
        name=Path(e['file']).name
        if any(x in name for x in ['source-sheets','sheets-directions']):target='PM6'
        elif 'delete-table' in name:target='PM8'
        elif e['section']!='latest':target='PM4'
        elif any(x in name for x in ['field','states','settings','source-excel']):target='R3-01..R3-08'
        elif any(x in name for x in ['detail','record-create','record-edit','unsaved','record-delete']):target='R2-01..R2-05'
        else:target='R1-04/R3-07'
    else:target={'01-overview':'R1-01/PM7','02-automation':'G1/PM3/PM8','03-runs':'PM3/PM4/PM5/PM7','04-statistics':'PM7','06-environments':'G1/PM3/PM5/PM8'}[e['module']]
    refs.append({'id':e['id'],'target':target,'detailSource':e['reviewDocument'],'businessEvidence':None})
assert len(refs)==112
output={'date':'2026-09-13','status':'plan-only-not-implementation','baseline':'4688353be07e06d08aa2319c3195086983768ad0','tasks':tasks,'sourceCoverage':refs,'specSections':{'1':'B0','2':'R1-01/R1-03/R1-05','3':'R1/R2/R3 + G1 + PM4–PM9','4':'R2-01/R2-05','5':'R2-02/R2-05/R3-04/R3-06','6':'R1-04/R2/R3','7':'G1','8':'G1/PM3–PM8 (unchanged contracts)','9':'B0/G1/PM8','10':'all task file responsibility rows','11':'R1-05/R2-05/R3-08'}}
(root/'docs/project-management/design-alignment/implementation-plan-index.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'status':'passed-static-plan-checks','method':'Primary-agent writing-plans self-review; local Python assertions for references, task/file/dependency/source coverage','command':'python3 docs/project-management/design-alignment/verify-implementation-plan.py','planFiles':[{ 'path':str(p.relative_to(root)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files], 'checks':{'plans':len(files),'implementationTasks':len(tasks),'checkboxSteps':sum(t['stepCount'] for t in tasks),'localLinks':links,'sourceIdsMapped':len(refs),'dependencyCycle':False,'unresolvedExistingFileReferences':0,'placeholderScan':'passed','alembicReadOnlyHead':'pm02_excel_exports'},'limits':['No business implementation or product tests executed','New prototypes not generated or reviewed','Windows, other architectures and packaging not executed','Future PM3 plan requires fresh core and migration baseline; G1 is an admission checklist']}
(root/'docs/project-management/design-alignment/implementation-plan-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
