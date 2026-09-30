"""G2: real fixed-row batches, field values and injected navigation failures."""

import pytest

from .harness import chain, flow_node, golden_rows, input_reference, run_golden
from .site import FIELDS, GoldenSite

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]


async def test_g2_scrapes_every_selected_row(
    tmp_path, valid_profile_values, real_cloak_page
):
    executable, _, _ = real_cloak_page
    count = golden_rows("G2")
    assert count >= 3, "G2 needs normal, timeout and gone rows"
    values = ["timeout-00000", "gone-00001"] + [f"row-{i:05}" for i in range(2, count)]
    with GoldenSite() as site:

        def build(input_spec):
            nodes = [
                flow_node(
                    "open",
                    "open_page",
                    0,
                    url=f"{site.base_url}/item/{input_reference(input_spec)}",
                    timeout=15,
                )
            ]
            nodes += [
                flow_node(
                    field,
                    "get_element_info",
                    i + 1,
                    selector=f"#{field}",
                    attribute="text",
                    variableName=field,
                    timeout=2,
                )
                for i, field in enumerate(FIELDS)
            ]
            return nodes, chain(nodes)

        run = await run_golden(
            tmp_path, executable, valid_profile_values, values=values, build=build
        )
        for detail in run.details:
            identity = detail["inputSnapshot"]["inputs"][0]["values"][0]["value"]
            detail["siteReceipt"] = {"itemRequests": site.hits(f"/item/{identity}")}
            assert detail["siteReceipt"]["itemRequests"] >= 1, detail
            if identity.startswith(("timeout-", "gone-")):
                assert detail["task"]["status"] == "failed", detail
            else:
                assert detail["task"]["status"] == "succeeded", detail
                outputs = {item["name"]: item["value"] for item in detail["outputs"]}
                assert outputs == {field: f"{field}-{identity}" for field in FIELDS}
                run.verified_success_refs.append(
                    detail["inputSnapshot"]["inputs"][0]["recordRef"]
                )
        assert run.metrics()["rows_succeeded"][0] == count - 2
        run.save(
            "g2-scrape",
            browser_kernel=executable,
            scenario_version="g2-scrape-v1",
            values=values,
        )
