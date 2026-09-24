

it('QA AM2 forward entry rollback retains basic management', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('实例管理')
  await waitFor(() => expect(client.isFetching()).toBe(0))
  const disabled = process.env.AUTOFLOW_QA_ENTRY_DISABLED === '1'
  for (const name of ['镜像管理', '设备模板']) {
    if (disabled) expect(screen.queryByRole('heading', { name })).not.toBeInTheDocument()
    else expect(screen.getByRole('heading', { name })).toBeVisible()
  }
  expect(screen.getByRole('button', { name: /打开测试设备 01/ })).toBeEnabled()
  expect(mocks.client.request.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false)
})
