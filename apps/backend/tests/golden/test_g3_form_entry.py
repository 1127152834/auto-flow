"""G3: site receipt proves one submission, even when the response is lost."""

import pytest

from .harness import chain, flow_node, golden_rows, input_reference, run_golden
from .site import GoldenSite

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]


async def _submit(tmp_path, executable, profile_values, values, site):
    def build(input_spec):
        nodes = [
            flow_node(
                "open",
                "open_page",
                0,
                url=f"{site.base_url}/form?name={input_reference(input_spec)}",
                timeout=15,
            ),
            flow_node("submit", "click_element", 1, selector="#submit", timeout=2),
            flow_node(
                "read",
                "get_element_info",
                2,
                selector="#result",
                attribute="text",
                variableName="result",
                timeout=2,
            ),
        ]
        return nodes, chain(nodes)

    return await run_golden(
        tmp_path, executable, profile_values, values=values, build=build
    )


async def test_g3_submits_each_row_exactly_once(
    tmp_path, valid_profile_values, real_cloak_page
):
    executable, _, _ = real_cloak_page
    count = golden_rows("G3")
    assert count >= 2
    values = ["lose-00000"] + [f"row-{i:05}" for i in range(1, count)]
    with GoldenSite() as site:
        run = await _submit(tmp_path, executable, valid_profile_values, values, site)
        for detail in run.details:
            identity = detail["inputSnapshot"]["inputs"][0]["values"][0]["value"]
            detail["siteReceipt"] = {"submissions": site.submissions(identity)}
            assert detail["siteReceipt"]["submissions"] == 1, detail
            if identity.startswith("lose-"):
                assert detail["task"]["status"] in {"failed", "interrupted"}, detail
            else:
                assert detail["task"]["status"] == "succeeded", detail
                assert {item["name"]: item["value"] for item in detail["outputs"]} == {
                    "result": f"ok:{identity}"
                }
                run.verified_success_refs.append(
                    detail["inputSnapshot"]["inputs"][0]["recordRef"]
                )
        assert run.metrics()["rows_succeeded"][0] == count - 1
        run.save(
            "g3-click",
            browser_kernel=executable,
            scenario_version="g3-click-v1",
            values=values,
        )


async def test_lost_submission_has_needs_review_state(
    tmp_path, valid_profile_values, real_cloak_page, request
):
    executable, _, _ = real_cloak_page
    with GoldenSite() as site:
        run = await _submit(
            tmp_path, executable, valid_profile_values, ["lose-state"], site
        )
        # This safety/evidence assertion stays outside the isolated known gap.
        assert site.submissions("lose-state") == 1
        assert run.details[0]["task"]["status"] in {"failed", "interrupted"}
        request.node.add_marker(
            pytest.mark.xfail(
                reason="M2 needs_review ledger is not implemented",
                strict=True,
                raises=AssertionError,
            )
        )
        assert run.details[0].get("ledgerState") == "needs_review"
