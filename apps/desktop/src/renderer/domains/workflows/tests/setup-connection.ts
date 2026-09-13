import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'

// Tests explicitly select their fixture; production transport has no implicit mock.
configureStudioConnection('http://autoflow-studio.mock', mockRequest)
