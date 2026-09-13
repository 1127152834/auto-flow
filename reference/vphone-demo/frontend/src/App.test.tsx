import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { App } from "./App";
import { position } from "./api";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("shows real blocked state without invented devices or enabled controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: true,
        json: async () => ({
          token: "test",
          devices: [],
          environment: {
            root: "/tmp/demo",
            freeGiB: 20,
            canAttemptLaunch: false,
            note: "检查",
            checks: {
              research: {
                ok: false,
                text: "Allow Research Guests status: disabled",
              },
            },
          },
        }),
      }),
  );
  render(<App />);
  expect(
    await screen.findByText("Allow Research Guests status: disabled"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "读取截图" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "运行步骤" })).toBeDisabled();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
it("maps actual displayed image bounds and rejects margins", () => {
  const rect = { left: 100, top: 50, width: 430, height: 932 };
  expect(position(315, 516, rect)).toEqual({ x: 0.5, y: 0.5 });
  expect(position(99, 516, rect)).toBeNull();
});
it("surfaces a failed real screenshot request without keeping a success image", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          token: "test",
          devices: [
            {
              name: "phone",
              width: 1290,
              height: 2796,
              socketPresent: true,
              managed: false,
            },
          ],
          environment: {
            root: "/tmp/demo",
            freeGiB: 20,
            canAttemptLaunch: true,
            note: "",
            checks: {},
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: "no active VM view" }),
      }),
  );
  render(<App />);
  await screen.findByRole("option", { name: "phone" });
  fireEvent.click(screen.getByRole("button", { name: "读取截图" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "no active VM view",
  );
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
