#!/usr/bin/env python3
"""Create three disposable Android devices through HTTP; never clean up other devices."""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class ApiError(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Client:
    def __init__(self, url):
        self.url = url.rstrip("/")
        # Desktop proxy settings must not route local WSL API calls through a proxy.
        self.opener = build_opener(ProxyHandler({})) if urlsplit(self.url).hostname in ("localhost", "127.0.0.1", "::1") else build_opener()

    def request(self, path, body=None, png=False):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.url + path, data=data,
                          headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            with self.opener.open(request, timeout=40) as response:
                if png:
                    result = response.read()
                    if not result.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise RuntimeError("Server returned a non-PNG screenshot")
                    return result
                return json.load(response)
        except HTTPError as error:
            raise ApiError(error.code, error.read().decode(errors="replace")) from error

    def wait(self, job_id, timeout=600):
        deadline = time.monotonic() + timeout
        while True:
            job = self.request("/api/jobs/" + quote(job_id, safe=""))
            if job["status"] in ("done", "failed"):
                return job
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Job {job_id} did not finish in {timeout} seconds")
            time.sleep(1)

    def submit(self, path, body):
        return self.wait(self.request(path, body)["job_id"])


def cleanup_run(client, prefix, owned, baseline, baseline_jobs, report, timeout=600):
    """Reconcile late creates after a lost response; delete only this run's resources."""
    deadline = time.monotonic() + timeout
    failed_deletes = set()
    while time.monotonic() < deadline:
        try:
            jobs = client.request("/api/jobs")["jobs"]
            pending_create = any(
                job["id"] not in baseline_jobs and job["action"] == "create"
                and job["status"] in ("queued", "running")
                # Before the first result, conservatively wait for any new create job.
                and (not job["results"] or any(item.get("name", "").startswith(prefix) for item in job["results"]))
                for job in jobs)
            instances = client.request("/api/instances")["instances"]
            ours = [item for item in instances if item["id"] not in baseline and
                    (item["id"] in owned or item["name"] == prefix or item["name"].startswith(prefix + " "))]
            owned.update(item["id"] for item in ours)
            report["remaining_instance_ids"] = [item["id"] for item in ours]
            if not pending_create and not ours:
                return
            for item in ours:
                instance_id = item["id"]
                if instance_id in failed_deletes:
                    continue
                try:
                    # Busy creation may still be running; re-discover all targets on retry.
                    accepted = client.request("/api/instances/" + quote(instance_id, safe="") + "/actions", {"action": "delete"})
                    job = client.wait(accepted["job_id"], timeout=max(1, deadline - time.monotonic()))
                    report["cleanup"].append(job)
                    if job["status"] != "done":
                        failed_deletes.add(instance_id)
                        report["errors"].append(f"{instance_id}: cleanup failed; inspect cleanup results")
                except ApiError as error:
                    if error.status not in (404, 409):
                        failed_deletes.add(instance_id)
                        report["errors"].append(f"{instance_id}: cleanup request failed: {error}")
            if not pending_create and ours and all(item["id"] in failed_deletes for item in ours):
                break
            time.sleep(1)
        except Exception as error:
            report["errors"].append(f"Cleanup could not be verified: {error}")
            return
    try:
        current = client.request("/api/instances")["instances"]
        report["remaining_instance_ids"] = [item["id"] for item in current if item["id"] not in baseline and
            (item["id"] in owned or item["name"] == prefix or item["name"].startswith(prefix + " "))]
    except Exception as error:
        report["errors"].append(f"Final cleanup discovery failed: {error}")
    report["errors"].append("Cleanup did not settle before its deadline; inspect this run's name and remaining IDs in the UI")


def run_demo(client, output):
    output.mkdir(parents=True, exist_ok=False)
    prefix = "batch-" + uuid.uuid4().hex
    report = {"run_name": prefix, "status": "failed", "jobs": [], "screenshots": [], "errors": [], "cleanup": []}
    owned = set()
    baseline = set()
    create_submitted = False
    baseline_jobs = set()
    try:
        environment = client.request("/api/environment")
        report["environment"] = environment
        if not environment["ready"]:
            raise RuntimeError("Environment is not ready; inspect the environment field in summary.json")
        before = client.request("/api/instances")["instances"]
        baseline = {item["id"] for item in before}
        if before:
            raise RuntimeError("The three-instance Demo requires all three slots free; existing instances were preserved")
        baseline_jobs = {job["id"] for job in client.request("/api/jobs")["jobs"]}
        # Mark before the request: a lost HTTP response can still create server-side resources.
        create_submitted = True
        job = client.submit("/api/instances", {"name": prefix, "count": 3})
        report["jobs"].append(job)
        owned.update(item["instance_id"] for item in job["results"] if item.get("instance_id"))
        if job["status"] != "done":
            report["errors"].append("One or more devices failed to start; successful targets will still be exercised")
        ready = []
        successful = {item["instance_id"] for item in job["results"]
                      if item.get("status") == "success" and item.get("instance_id")}
        for instance_id in sorted(successful):
            try:
                item = client.request("/api/instances/" + quote(instance_id, safe=""))
                if item["android_status"] == "ready":
                    ready.append(instance_id)
                else:
                    report["errors"].append(f"{instance_id}: Android is {item['android_status']}")
            except Exception as error:
                report["errors"].append(f"{instance_id}: readiness check failed: {error}")
        if ready:
            job = client.submit("/api/batches", {"action": "open_settings", "instance_ids": ready})
            report["jobs"].append(job)
            if job["status"] != "done":
                report["errors"].append("One or more open_settings actions failed")
            for instance_id in ready:
                try:
                    data = client.request("/api/instances/" + quote(instance_id, safe="") + "/screen", png=True)
                    filename = f"screen-{len(report['screenshots']) + 1}.png"
                    (output / filename).write_bytes(data)
                    report["screenshots"].append({"instance_id": instance_id, "file": filename})
                except Exception as error:
                    report["errors"].append(f"{instance_id}: screenshot failed: {error}")
        if len(report["screenshots"]) != 3:
            report["errors"].append("Expected three successful screenshots")
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        if create_submitted:
            cleanup_run(client, prefix, owned, baseline, baseline_jobs, report)
        report["status"] = "passed" if not report["errors"] else "failed"
        (output / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, default=Path(".data/batch-runs"))
    args = parser.parse_args()
    output = args.output / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    report = run_demo(Client(args.api), output)
    print(json.dumps({"status": report["status"], "report": str(output / "summary.json"), "errors": report["errors"]}, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
