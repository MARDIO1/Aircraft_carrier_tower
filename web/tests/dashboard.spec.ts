import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

async function snapshot(request: any) {
  const response = await request.get("http://127.0.0.1:8000/api/snapshot");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function setStateFromPage(page: any, state: string) {
  await page.getByRole("button", { name: state, exact: true }).click();
}

test("dashboard controls state and parameter JSON", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByText("Ground Station Web")).toBeVisible();

  await page.getByRole("button", { name: "load json", exact: true }).click();
  await expect.poll(async () => {
    const snap = await snapshot(request);
    return Array.isArray(snap.control.jacobian_matrix) && Array.isArray(snap.control.surface_angle_min_d);
  }).toBeTruthy();

  for (const state of ["STOP", "TOWER", "AUTO", "TUNING", "DATA"]) {
    await setStateFromPage(page, state);
    await expect.poll(async () => (await snapshot(request)).state.main).toBe(state);
  }

  await page.getByRole("button", { name: "apply jacobian", exact: true }).click();
  await page.getByRole("button", { name: "apply surface limit", exact: true }).click();
  await page.getByRole("button", { name: "save json", exact: true }).click();

  const pidSaved = JSON.parse(readFileSync("../pid_params.json", "utf-8"));
  const surfaceSaved = JSON.parse(readFileSync("../surface_limit_params.json", "utf-8"));
  expect(typeof pidSaved.saved_at).toBe("number");
  expect(typeof surfaceSaved.saved_at).toBe("number");
  expect(Array.isArray(surfaceSaved.surface_angle_min_d)).toBeTruthy();
});
