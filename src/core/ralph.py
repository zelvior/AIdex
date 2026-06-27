# -*- coding: utf-8 -*-
"""
AIdex Ralph Loop - autonomous task-loop orchestrator.
Apache 2.0 License

Inspired by the "Ralph" pattern (named after Ralph Wiggum's stubborn
persistence): pick the next task, build a focused prompt, run the agent,
detect completion, persist state, repeat — until the task list is empty
or a safety cap is hit. Unlike the standalone TypeScript "Ralph TUI"
project this takes its name from, this is a small, self-contained module
that reuses AIdex's own Agent/Config/tool system directly rather than
shelling out to an external coding-agent CLI.

Pure standard library, Python 2.7+ compatible (no f-strings, no walrus,
no pathlib dependency in the hot path) so this runs identically under
the plain TUI on Windows XP / 32-bit systems as it does under the full
Rich TUI or the web UI.

Task file format (JSON), default path: <workspace>/ralph_tasks.json
{
  "tasks": [
    {"id": "1", "title": "...", "status": "pending", "notes": ""},
    ...
  ]
}
Statuses: "pending", "in_progress", "done", "failed", "skipped".
"""

from __future__ import print_function
import os
import json
import time


DEFAULT_TASKS_FILENAME = "ralph_tasks.json"
DEFAULT_MAX_ITERATIONS = 35  # same default as the Ralph TUI pattern this borrows from
STATE_SCHEMA_VERSION = 1


class RalphTask(object):
    __slots__ = ("id", "title", "status", "notes", "attempts")

    def __init__(self, id, title, status="pending", notes="", attempts=0):
        self.id = id
        self.title = title
        self.status = status
        self.notes = notes
        self.attempts = attempts

    def to_dict(self):
        return {"id": self.id, "title": self.title, "status": self.status,
                "notes": self.notes, "attempts": self.attempts}

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", ""), title=d.get("title", ""),
            status=d.get("status", "pending"), notes=d.get("notes", ""),
            attempts=d.get("attempts", 0),
        )


class RalphState(object):
    """Holds the task list and run metadata; knows how to persist/restore
    itself so a run can be paused, crash, and resume without losing
    progress — same guarantee the standalone Ralph TUI project provides,
    implemented here with a single flat JSON file instead of a database."""

    def __init__(self, tasks_path):
        self.tasks_path = tasks_path
        self.tasks = []
        self.iteration = 0
        self.started_at = None
        self.paused = False

    def load(self):
        if not os.path.exists(self.tasks_path):
            self.tasks = []
            return
        try:
            f = open(self.tasks_path, "r")
            try:
                data = json.load(f)
            finally:
                f.close()
        except (IOError, ValueError):
            self.tasks = []
            return
        self.tasks = [RalphTask.from_dict(t) for t in data.get("tasks", [])]
        self.iteration = data.get("iteration", 0)
        self.started_at = data.get("started_at")
        self.paused = data.get("paused", False)

    def save(self):
        directory = os.path.dirname(self.tasks_path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        payload = {
            "schema_version": STATE_SCHEMA_VERSION,
            "tasks": [t.to_dict() for t in self.tasks],
            "iteration": self.iteration,
            "started_at": self.started_at,
            "paused": self.paused,
            "saved_at": time.time(),
        }
        tmp_path = self.tasks_path + ".tmp"
        f = open(tmp_path, "w")
        try:
            json.dump(payload, f, indent=2)
        finally:
            f.close()
        # Atomic-ish replace: write to a temp file then rename, so a crash
        # mid-write can't corrupt the real state file (important since this
        # is the thing a resumed run depends on).
        if os.path.exists(self.tasks_path):
            os.remove(self.tasks_path)
        os.rename(tmp_path, self.tasks_path)

    def next_pending(self):
        for t in self.tasks:
            if t.status == "pending":
                return t
        return None

    def counts(self):
        out = {"pending": 0, "in_progress": 0, "done": 0, "failed": 0, "skipped": 0}
        for t in self.tasks:
            out[t.status] = out.get(t.status, 0) + 1
        return out

    def add_task(self, title):
        next_id = str(len(self.tasks) + 1)
        # Keep ids unique even after tasks are removed/reordered by hand.
        existing_ids = set(t.id for t in self.tasks)
        while next_id in existing_ids:
            next_id = str(int(next_id) + 1)
        task = RalphTask(id=next_id, title=title)
        self.tasks.append(task)
        return task


def default_tasks_path(workspace):
    return os.path.join(workspace, DEFAULT_TASKS_FILENAME)


def build_task_prompt(task, task_index, total_tasks):
    """A small, focused prompt for a single task — deliberately minimal
    context injection (matching the 'minimal context injection' principle
    the Ralph pattern uses) rather than dumping the whole task list at the
    model every iteration."""
    return (
        "You are working through an autonomous task list (task %s of %s).\n\n"
        "Current task: %s\n\n"
        "Complete this task using the available tools. When you are done, "
        "say so clearly in your final response. If you cannot complete it, "
        "explain why."
    ) % (task_index, total_tasks, task.title)


class RalphRunner(object):
    """Drives the select -> prompt -> execute -> detect -> repeat loop
    using an existing AIdex Agent instance. UI-agnostic: callers (plain
    TUI, Rich TUI, web UI) supply callback functions and get told what
    happened after each step, rather than this class doing any printing
    itself — keeps it usable identically from a Python-2.7-only plain
    terminal and from a Rich/web frontend."""

    def __init__(self, agent, state, max_iterations=DEFAULT_MAX_ITERATIONS,
                 excluded_tools=None, confine_to_workspace=False):
        self.agent = agent
        self.state = state
        self.max_iterations = max_iterations
        self.excluded_tools = excluded_tools
        self.confine_to_workspace = confine_to_workspace
        self.stop_requested = False

    def request_stop(self):
        """Cooperative stop — checked between tasks, not mid-task, so a
        task already in flight is allowed to finish rather than being cut
        off halfway (avoids leaving a task in a half-done, ambiguous state)."""
        self.stop_requested = True

    def run(self, on_task_start=None, on_task_event=None, on_task_done=None, on_finished=None):
        """Blocking loop. Callbacks:
          on_task_start(task, index, total)
          on_task_event(task, event_type, content)  -- mirrors chat_stream's
              ("text"|"tool_call"|"tool_result"|"error"|"done", content)
          on_task_done(task, outcome)  -- outcome is "done"/"failed"
          on_finished(reason)  -- "completed"/"max_iterations"/"stopped"/"no_tasks"
        """
        if self.state.started_at is None:
            self.state.started_at = time.time()

        total = len(self.state.tasks)
        if total == 0:
            if on_finished:
                on_finished("no_tasks")
            return

        while True:
            if self.stop_requested:
                self.state.paused = True
                self.state.save()
                if on_finished:
                    on_finished("stopped")
                return

            if self.state.iteration >= self.max_iterations:
                self.state.save()
                if on_finished:
                    on_finished("max_iterations")
                return

            task = self.state.next_pending()
            if task is None:
                self.state.save()
                if on_finished:
                    on_finished("completed")
                return

            self.state.iteration += 1
            task.status = "in_progress"
            task.attempts += 1
            self.state.save()  # persist immediately so a crash mid-task is visible on resume

            index = self._task_index(task)
            if on_task_start:
                on_task_start(task, index, total)

            prompt = build_task_prompt(task, index, total)

            outcome = "failed"
            final_text_parts = []
            try:
                for event_type, content in self.agent.chat_stream(
                    prompt, excluded_tools=self.excluded_tools,
                    confine_to_workspace=self.confine_to_workspace,
                ):
                    if on_task_event:
                        on_task_event(task, event_type, content)
                    if event_type == "text":
                        final_text_parts.append(content)
                    if event_type == "error":
                        outcome = "failed"
                if final_text_parts:
                    outcome = "done"
            except Exception as e:
                if on_task_event:
                    on_task_event(task, "error", "Ralph loop error: %s" % e)
                outcome = "failed"

            task.status = outcome
            task.notes = ("".join(final_text_parts))[:500]
            self.state.save()

            if on_task_done:
                on_task_done(task, outcome)

    def _task_index(self, task):
        for i, t in enumerate(self.state.tasks):
            if t.id == task.id:
                return i + 1
        return 0
