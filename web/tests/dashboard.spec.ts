import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

async function snapshot(request: any) {
  const response = await request.get("http://127.0.0.1:8000/api/snapshot");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function clickButton(page: any, name: string) {
  await page.getByRole("button", { name, exact: true }).evaluate((button: HTMLElement) => {
    (button as HTMLButtonElement).click();
  });
}

async function setStateFromPage(page: any, state: string) {
  const result = await page.evaluate(async (targetState: string) => {
    const response = await fetch("http://127.0.0.1:8000/api/control", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ main_state: targetState }),
    });
    return {
      ok: response.ok,
      status: response.status,
      body: await response.text(),
    };
  }, state);
  expect(result.ok).toBeTruthy();
}

test("dashboard connects, changes states, and round-trips JSON params", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByText("AIRCRAFT CARRIER TOWER")).toBeVisible();

  await clickButton(page, "connect");
  await expect.poll(async () => (await snapshot(request)).runtime.serial.com_port).not.toBeNull();

  await setStateFromPage(page, "STOP");
  for (const state of ["AUTO", "TOWER", "STOP"]) {
    await setStateFromPage(page, state);
    await expect.poll(async () => (await snapshot(request)).state.main).toBe(state);
  }

  await clickButton(page, "load json");
  await expect.poll(async () => {
    const response = await request.get("http://127.0.0.1:8000/api/params");
    const body = await response.json();
    return Array.isArray(body.params.pid_param) && Array.isArray(body.params.jacobian_matrix);
  }).toBeTruthy();

  await clickButton(page, "save json");
  const saved = JSON.parse(readFileSync("../pid_params.json", "utf-8"));
  expect(typeof saved.saved_at).toBe("number");
  expect(Array.isArray(saved.pid_param)).toBeTruthy();
});
