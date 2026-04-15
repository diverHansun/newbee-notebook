"use client";

import { create } from "zustand";

import type { VideoStreamEvent } from "@/lib/api/types";

export type VideoTaskPlatform = "bilibili" | "youtube";
export type VideoTaskStatus = "processing" | "completed" | "failed";
export type VideoTaskStepType = "start" | "subtitle" | "asr" | "summarize" | "done" | "reused";

export type VideoTaskStep = {
  type: VideoTaskStepType;
  source?: string;
  status: "done" | "active";
};

export type VideoTaskInfo = {
  title: string;
  uploaderName?: string;
  durationSeconds?: number;
};

export type VideoTaskError = {
  message: string;
  errorCode?: string;
};

export type VideoProcessingTask = {
  taskId: string;
  notebookId: string;
  requestInput: string;
  platform: VideoTaskPlatform;
  videoId?: string;
  summaryId?: string;
  status: VideoTaskStatus;
  info: VideoTaskInfo | null;
  steps: VideoTaskStep[];
  error: VideoTaskError | null;
  dismissed: boolean;
  reused: boolean;
  createdAt: number;
};

type VideoProcessingStoreState = {
  draftInputByNotebook: Record<string, string>;
  foregroundTaskIdByNotebook: Record<string, string | null>;
  tasks: Record<string, VideoProcessingTask>;
  setDraftInput: (notebookId: string, value: string) => void;
  startTask: (args: {
    notebookId: string;
    requestInput: string;
    platform: VideoTaskPlatform;
  }) => string;
  applyInfoEvent: (taskId: string, event: Extract<VideoStreamEvent, { type: "info" }>) => void;
  applyProgressEvent: (
    taskId: string,
    event: Extract<VideoStreamEvent, { type: "start" | "subtitle" | "asr" | "summarize" }>
  ) => void;
  completeTask: (taskId: string, event: Extract<VideoStreamEvent, { type: "done" }>) => void;
  failTask: (taskId: string, event: Extract<VideoStreamEvent, { type: "error" }>) => void;
  dismissForegroundTask: (notebookId: string) => void;
};

function buildTaskId() {
  return `video-task-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function withoutTask(
  tasks: Record<string, VideoProcessingTask>,
  taskId: string
): Record<string, VideoProcessingTask> {
  const nextTasks = { ...tasks };
  delete nextTasks[taskId];
  return nextTasks;
}

function toDoneSteps(steps: VideoTaskStep[]): VideoTaskStep[] {
  return steps.map((step) => ({ ...step, status: "done" }));
}

export const useVideoProcessingStore = create<VideoProcessingStoreState>((set, get) => ({
  draftInputByNotebook: {},
  foregroundTaskIdByNotebook: {},
  tasks: {},
  setDraftInput: (notebookId, value) =>
    set((state) => ({
      draftInputByNotebook: {
        ...state.draftInputByNotebook,
        [notebookId]: value,
      },
    })),
  startTask: ({ notebookId, requestInput, platform }) => {
    const taskId = buildTaskId();
    const state = get();
    const previousForegroundTaskId = state.foregroundTaskIdByNotebook[notebookId];
    const nextTasks = { ...state.tasks };

    if (previousForegroundTaskId) {
      const previousTask = nextTasks[previousForegroundTaskId];
      if (previousTask && previousTask.status !== "processing") {
        delete nextTasks[previousForegroundTaskId];
      }
    }

    nextTasks[taskId] = {
      taskId,
      notebookId,
      requestInput,
      platform,
      status: "processing",
      info: null,
      steps: [],
      error: null,
      dismissed: false,
      reused: false,
      createdAt: Date.now(),
    };

    set({
      draftInputByNotebook: {
        ...state.draftInputByNotebook,
        [notebookId]: requestInput,
      },
      foregroundTaskIdByNotebook: {
        ...state.foregroundTaskIdByNotebook,
        [notebookId]: taskId,
      },
      tasks: nextTasks,
    });

    return taskId;
  },
  applyInfoEvent: (taskId, event) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;
      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            videoId: event.video_id || task.videoId,
            info: {
              title: event.title,
              uploaderName: event.uploader_name,
              durationSeconds: event.duration_seconds,
            },
          },
        },
      };
    }),
  applyProgressEvent: (taskId, event) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;
      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            videoId: event.video_id || task.videoId,
            status: "processing",
            error: null,
            steps: [
              ...toDoneSteps(task.steps),
              {
                type: event.type,
                source: event.source,
                status: "active",
              },
            ],
          },
        },
      };
    }),
  completeTask: (taskId, event) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;

      const nextTask: VideoProcessingTask = {
        ...task,
        summaryId: event.summary_id || task.summaryId,
        status: event.status === "failed" ? "failed" : "completed",
        reused: event.reused,
        error: null,
        steps: event.reused
          ? [{ type: "reused", status: "done" }]
          : [...toDoneSteps(task.steps), { type: "done", status: "done" }],
      };

      if (nextTask.dismissed) {
        return {
          tasks: withoutTask(state.tasks, taskId),
        };
      }

      return {
        tasks: {
          ...state.tasks,
          [taskId]: nextTask,
        },
      };
    }),
  failTask: (taskId, event) =>
    set((state) => {
      const task = state.tasks[taskId];
      if (!task) return state;

      if (task.dismissed) {
        return {
          tasks: withoutTask(state.tasks, taskId),
        };
      }

      return {
        tasks: {
          ...state.tasks,
          [taskId]: {
            ...task,
            status: "failed",
            error: {
              message: event.message,
              errorCode: event.error_code,
            },
            steps: [],
          },
        },
      };
    }),
  dismissForegroundTask: (notebookId) =>
    set((state) => {
      const foregroundTaskId = state.foregroundTaskIdByNotebook[notebookId];
      if (!foregroundTaskId) return state;

      const task = state.tasks[foregroundTaskId];
      const nextForegroundTaskIdByNotebook = {
        ...state.foregroundTaskIdByNotebook,
        [notebookId]: null,
      };

      if (!task) {
        return {
          foregroundTaskIdByNotebook: nextForegroundTaskIdByNotebook,
        };
      }

      if (task.status === "processing") {
        return {
          foregroundTaskIdByNotebook: nextForegroundTaskIdByNotebook,
          tasks: {
            ...state.tasks,
            [foregroundTaskId]: {
              ...task,
              dismissed: true,
            },
          },
        };
      }

      return {
        foregroundTaskIdByNotebook: nextForegroundTaskIdByNotebook,
        tasks: withoutTask(state.tasks, foregroundTaskId),
      };
    }),
}));