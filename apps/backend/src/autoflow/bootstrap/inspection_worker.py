from autoflow.bootstrap.test_browser_worker import browser_worker_main
from autoflow.providers.browser.inspection_worker import run_inspection_worker


def inspection_worker_main() -> int:
    return browser_worker_main(run_inspection_worker)
