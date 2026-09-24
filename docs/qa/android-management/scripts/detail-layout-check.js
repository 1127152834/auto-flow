// Read-only real-renderer check: open a device with a wrapping long name.
(() => {
  const header = document.querySelector('.ad-device-heading')
  const tabs = document.querySelector('.ad-detail-tabs')
  if (!header || !tabs) throw new Error('Open a device detail page first')
  const contentBottom = Math.max(...[...header.children].map((element) => element.getBoundingClientRect().bottom))
  const tabsTop = tabs.getBoundingClientRect().top
  const result = { contentBottom, tabsTop }
  if (contentBottom > tabsTop + 1) throw new Error(`Device heading overlaps tabs: ${JSON.stringify(result)}`)
  return { passed: true, ...result }
})()
