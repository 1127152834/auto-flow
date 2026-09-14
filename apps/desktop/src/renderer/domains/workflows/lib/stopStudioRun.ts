import type {components} from '../../../shared/api/generated'
import {workflowApi} from '../api'
import {getStudioTransportRevision} from '../api/transport'
/** Cleanup acknowledgement is verified against the requested run, never just the workflow. */
export async function stopStudioRun(workflowId:string,runId:string):Promise<components['schemas']['StudioWorkflowRunSummary']|null> {
 const revision=getStudioTransportRevision()
 await workflowApi.stop(workflowId,runId)
 if(revision!==getStudioTransportRevision())return null
 // A lost stop response may still have committed cleanup; query the original identity.
 const result=await workflowApi.getRun(runId)
 if(revision!==getStudioTransportRevision())return null
 const run=result.data
 if(!result.success||!run||run.workflowId!==workflowId||run.runId!==runId)return null
 if(['completed','failed','stopped','interrupted'].includes(run.status))return run
 return null
}
