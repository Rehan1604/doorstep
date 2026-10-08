import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App, { MissionCard, Badge, Insights } from "./App.jsx";
import * as api from "./api.js";

const mission = { id: 1, source: "model", mission: { title: "Quiet Corner Hunt", duration_minutes: 20, difficulty: "easy",
  objective: "Find one quiet spot and listen.", steps: ["Walk slowly.", "Listen for 60 seconds."],
  why_it_matters: "Listening resets attention.", safety_notes: ["Stay on public paths."] } };

beforeEach(() => {
  vi.spyOn(api, "health").mockResolvedValue({ ollama: true, model_present: true });
  vi.spyOn(api, "getHistory").mockResolvedValue({ completed: 0, minutes_outside: 0, items: [] });
});

test("create mission shows card with safety note", async () => {
  vi.spyOn(api, "createMission").mockResolvedValue(mission);
  render(<App />);
  await userEvent.click(screen.getByText("CREATE MY MISSION"));
  expect(await screen.findByText("Quiet Corner Hunt")).toBeTruthy();
  expect(screen.getByText(/Stay on public paths/)).toBeTruthy();
});

test("server failure shows error and returns home, not a crash", async () => {
  vi.spyOn(api, "createMission").mockRejectedValue(new Error("x"));
  render(<App />);
  await userEvent.click(screen.getByText("CREATE MY MISSION"));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByText("CREATE MY MISSION")).toBeTruthy();
});

test("offline badge shows DISCONNECTED", () => {
  render(<Badge status={{ online: false, ai: "local" }} />);
  expect(screen.getByRole("status").textContent).toMatch(/DISCONNECTED.*AI: LOCAL/);
});

test("screen budget auto-launches outdoor mode at zero", () => {
  vi.useFakeTimers();
  const onStart = vi.fn();
  render(<MissionCard data={mission} onStart={onStart} />);
  act(() => { vi.advanceTimersByTime(46000); });
  expect(onStart).toHaveBeenCalledTimes(1);
  vi.useRealTimers();
});

test("full flow: card -> phone down -> complete -> reflection", async () => {
  vi.spyOn(api, "createMission").mockResolvedValue(mission);
  vi.spyOn(api, "completeMission").mockResolvedValue({ reflection: "You gave it 20 minutes." });
  render(<App />);
  await userEvent.click(screen.getByText("CREATE MY MISSION"));
  await userEvent.click(await screen.findByText("GO OUTSIDE"));
  expect(screen.getByText("PHONE DOWN")).toBeTruthy();
  await userEvent.click(screen.getByText("I’m back"));
  await userEvent.type(screen.getByLabelText("What surprised you?"), "a heron");
  await userEvent.click(screen.getByText("FINISH"));
  expect(await screen.findByText("You gave it 20 minutes.")).toBeTruthy();
});

test("mission card explains why this style and shows novelty", () => {
  const data = { ...mission, style_label: "Close-up", why: "Close-up has left you feeling better in 3 of 4 missions.", novelty: 0.82 };
  render(<MissionCard data={data} onStart={() => {}} />);
  expect(screen.getByText(/3 of 4 missions/)).toBeTruthy();
  expect(screen.getByText("82% new")).toBeTruthy();
});

test("insights panel shows what works and hides when empty", () => {
  const { container, rerender } = render(<Insights data={{ total: 0, styles: [], best: null }} />);
  expect(container.textContent).toBe("");
  rerender(<Insights data={{ total: 4, best: "Close-up", styles: [{ style: "closeup", label: "Close-up", n: 4, good: 3, mean: 0.8 }] }} />);
  expect(screen.getByText("3/4 felt better")).toBeTruthy();
  expect(screen.getByText(/Right now: Close-up/)).toBeTruthy();
});
