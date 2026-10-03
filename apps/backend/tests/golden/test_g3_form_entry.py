"""G3: site receipt proves one submission, even when the response is lost."""

import pytest

from .harness import chain, flow_node, golden_rows, input_reference, run_golden
from .site import GoldenSite

pytestmark = [pytest.mark.golden, pytest.mark.asyncio]


async def _submit(tmp_path, executable, profile_values, values, site, mode="click"):
    """``click`` presses the submit button (M0 scenario); ``enter`` presses Enter in the field."""

    def build(input_spec):
        if mode == "enter":
            submit = flow_node(
                "submit",
                "press_key",
                1,
                key="Enter",
                targetType="element",
                selector="#name",
                timeout=2,
            )
        else:
            submit = flow_node(
                "submit", "click_element", 1, selector="#submit", timeout=2
            )
        nodes = [
            flow_node(
                "open",
                "open_page",
                0,
                url=f"{site.base_url}/form?name={input_reference(input_spec)}",
                timeout=15,
            ),
            submit,
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


@pytest.mark.parametrize(
    ("mode", "report", "version"),
    [
        ("click", "g3-click", "g3-click-v1"),
        ("enter", "g3-enter", "g3-enter-v1"),
    ],
)
async def test_g3_submits_each_row_exactly_once(
    tmp_path, valid_profile_values, real_cloak_page, mode, report, version
):
    executable, _, _ = real_cloak_page
    count = golden_rows("G3")
    assert count >= 2
    values = ["lose-00000"] + [f"row-{i:05}" for i in range(1, count)]
    with GoldenSite() as site:
        run = await _submit(
            tmp_path, executable, valid_profile_values, values, site, mode
        )
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
            report,
            browser_kernel=executable,
            scenario_version=version,
            values=values,
        )


async def test_lost_submission_has_needs_review_state(
    tmp_path, valid_profile_values, real_cloak_page
):
    """AC2-02: a submission whose response is lost is never retried automatically."""
    executable, _, _ = real_cloak_page
    with GoldenSite() as site:
        run = await _submit(
            tmp_path, executable, valid_profile_values, ["lose-state"], site
        )
        assert site.submissions("lose-state") == 1
        assert run.details[0]["task"]["status"] in {"failed", "interrupted"}
        assert run.details[0]["ledgerState"] == "needs_review"
