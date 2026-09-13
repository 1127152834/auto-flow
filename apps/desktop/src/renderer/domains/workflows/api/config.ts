/** AutoFlow owns transport selection; no source-project port discovery or credentials. */
export const getBackendBaseUrl = () => 'http://autoflow-studio.mock'
export const getBackendPort = () => ''
export const getFrontendPort = () => location.port
export const setBackendPort = (_port: number | string) => { throw new Error('Studio connection is managed by AutoFlow') }
export const preloadConfig = async () => {}
