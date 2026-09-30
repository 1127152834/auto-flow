// Run in the real desktop renderer after opening Create Instances and expanding
// language/timezone settings. Repeat at 1280x800 and 1440x900, zoom 1 and 2.
// Read-only: fails on horizontal overflow; does not submit or change any state.
(() => {
  const page = document.querySelector('.ad-create-page')
  if (!page || !page.querySelector('.ad-advanced-fields')) {
    throw new Error('Open Create Instances and expand language/timezone settings first')
  }
  const width = document.documentElement.clientWidth
  const elements = [...page.querySelectorAll('button, input, select, aside, fieldset')]
  const overflow = elements.flatMap((element) => {
    const rect = element.getBoundingClientRect()
    return rect.left < -1 || rect.right > width + 1
      ? [{ label: element.getAttribute('aria-label') || element.id || element.textContent?.trim().slice(0, 80), left: rect.left, right: rect.right }]
      : []
  })
  const result = { width, pageWidth: page.scrollWidth, controls: elements.length, overflow }
  if (page.scrollWidth > page.clientWidth + 1 || overflow.length) {
    throw new Error(`Create layout overflows: ${JSON.stringify(result)}`)
  }
  return { passed: true, ...result }
})()
