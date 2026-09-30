// Development-only visual fixture. The production entry never imports test data.
import { ApplicationHeader } from '../../../app/ApplicationHeader'
import { ResourceBoard } from '../components/ResourceBoard'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
import { devices, images, profile, environment, allocations, runs, fixtureSession } from './prototype-fixtures'
import manualScreen from '../assets/reference/manual-screen.png'
import workflowScreen from '../assets/reference/workflow-screen.png'
import '../android.css'
const noop = () => {}
export function PrototypePreview() {
  const page = new URLSearchParams(location.search).get('androidFixture')
  return (
    <>
      <ApplicationHeader route="android" status="connected" onNavigate={noop} />
      {page === 'create' ? (
        <CreateInstances
          profiles={[profile]}
          environment={environment}
          onBack={noop}
          onProfiles={noop}
          onSubmit={async () => {}}
        />
      ) : page === 'manual' || page === 'takeover' ? (
        <DeviceConsole
          initialText="测试账号
"
          device={devices[page === 'manual' ? 0 : 2]}
          session={fixtureSession(page === 'manual')}
          run={page === 'takeover' ? runs[devices[2].deviceId] : undefined}
          apps={{
            currentPackage: 'com.google.android.keep',
            packages: ['com.google.android.keep'],
            shellRoot: 'available',
            applicationRoot: 'unknown',
          }}
          image={page === 'manual' ? manualScreen : workflowScreen}
          thumbnail={images[devices[page === 'manual' ? 0 : 2].deviceId]}
          onBack={noop}
          onSession={noop}
          onOpen={noop}
          onManage={noop}
          onRefresh={noop}
        />
      ) : (
        <ResourceBoard
          devices={devices}
          profiles={[profile]}
          allocations={allocations}
          batches={[]}
          runs={runs}
          images={images}
          onCreate={noop}
          onProfiles={noop}
          onOpen={noop}
          onAllocate={noop}
          onManage={noop}
          onRuns={noop}
          onBatch={noop}
        />
      )}
    </>
  )
}
