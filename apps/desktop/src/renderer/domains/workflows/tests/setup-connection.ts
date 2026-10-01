import { configure } from '@testing-library/react'

import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'

// Tests explicitly select their fixture; production transport has no implicit mock.
configureStudioConnection('http://autoflow-studio.mock', mockRequest)

// The 1s Testing Library default is shorter than the 15s per-test budget and was
// exceeded by a heavy page waiting on CI CPU contention (observed once on the
// baseline merge run). Failing queries still fail; they just fail after 5s.
configure({ asyncUtilTimeout: 5000 })
