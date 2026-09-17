from autoflow.bootstrap.test_browser_worker import browser_worker_main
from autoflow.providers.browser.workflow_worker import run_workflow_worker


def workflow_worker_main() -> int:
    return browser_worker_main(run_workflow_worker)


def project_workflow_worker_main() -> int:
    from autoflow.providers.browser.project_workflow_worker import run_worker

    return browser_worker_main(run_worker)
