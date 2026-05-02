import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

async function apiSnapshot(request: any) {
  const response = await request.get("http://127.0.0.1:8000/api/snapshot");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function apiPost(request: any, path: string, data: Record<string, unknown> = {}) {
  const response = await request.post(`http://127.0.0.1:8000${path}`, { data });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function waitForSendPrefix(request: any, prefix: string) {
  await expect.poll(async () => String((await apiSnapshot(request)).runtime?.send?.hex ?? "")).toContain(prefix);
}

async function waitForMainState(request: any, state: string) {
  await expect.poll(async () => (await apiSnapshot(request)).state?.main).toBe(state);
}

test("ui buttons drive the live serial sender", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByText("Ground Station Web")).toBeVisible();

  const snap = await apiSnapshot(request);
  expect(snap.runtime?.serial?.connected).toBeTruthy();

  await page.getByRole("button", { name: "load json", exact: true }).click();
  await expect.poll(async () => (await apiSnapshot(request)).control?.pid_param?.length).toBe(7);

  const states = [
    { name: "STOP", prefix: "AA 00" },
    { name: "TOWER", prefix: "AA 02" },
    { name: "AUTO", prefix: "AA 01" },
    { name: "DATA", prefix: "AA B1" },
  ];

  for (const item of states) {
    await page.getByRole("button", { name: item.name, exact: true }).click();
    await waitForMainState(request, item.name);
    await waitForSendPrefix(request, item.prefix);
  }

  await page.getByRole("button", { name: "TUNING", exact: true }).click();
  await expect
    .poll(async () => {
      const current = await apiSnapshot(request);
      return current.runtime?.auto_tune?.running ? current.runtime.auto_tune.stage : current.state?.main;
    })
    .toBe("STOP");
  await waitForSendPrefix(request, "AA 00");
});

test("backend protocol covers tuning sub-states and save requests", async ({ request }) => {
  const snap = await apiSnapshot(request);
  expect(snap.runtime?.serial?.connected).toBeTruthy();

  const tuningCases = [
    { subState: "SERVO", prefix: "AA A1" },
    { subState: "FEEDFORWARD", prefix: "AA A4" },
    { subState: "PID", prefix: "AA A2" },
    { subState: "JACOBIAN", prefix: "AA A3" },
    { subState: "SURFACE_LIMIT", prefix: "AA A7" },
  ];

  for (const item of tuningCases) {
    await apiPost(request, "/api/control", { main_state: "TUNING", sub_state: item.subState });
    await waitForMainState(request, "TUNING");
    await waitForSendPrefix(request, item.prefix);
  }

  await apiPost(request, "/api/control", { request_save_to_flash: true });
  await waitForSendPrefix(request, "AA A5");
});

test("parameter json round-trip stays intact", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "load json", exact: true }).click();
  await page.getByRole("button", { name: "save json", exact: true }).click();

  const pidSaved = JSON.parse(readFileSync("../pid_params.json", "utf-8"));
  const surfaceSaved = JSON.parse(readFileSync("../surface_limit_params.json", "utf-8"));
  expect(typeof pidSaved.saved_at).toBe("number");
  expect(typeof surfaceSaved.saved_at).toBe("number");

  const snap = await apiSnapshot(request);
  expect(Array.isArray(snap.control.servo_angles)).toBeTruthy();
  expect(Array.isArray(snap.control.jacobian_matrix)).toBeTruthy();
});
