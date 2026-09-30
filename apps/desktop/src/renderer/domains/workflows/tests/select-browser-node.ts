import {useWorkflowStore} from '../editor-store'
/** Transport fixtures explicitly select an initializer; production has no global fallback. */
export function selectBrowserNode(profileId='10000000-0000-4000-8000-000000000001') {
 const store=useWorkflowStore.getState()
 store.clearWorkflow()
 store.addNode('open_page',{x:0,y:0})
 const node=useWorkflowStore.getState().nodes[0]
 store.updateNodeData(node.id,{browserEnvironment:{source:'newFromProfile',profileId}})
 store.selectNode(node.id)
}
