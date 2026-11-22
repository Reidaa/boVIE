import { config as dotenvConfig } from "dotenv";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";

const LEVEL_PRIORITY: Record<LogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
};

export type LogSink = (message: string, level: LogLevel) => void;

interface RegisteredSink {
  id: number;
  minPriority: number;
  sink: LogSink;
}

let debugEnabled = false;
let nextSinkId = 1;
const sinks = new Map<number, RegisteredSink>();

export function loadEnvironment(): void {
  dotenvConfig({ path: ".env", override: false, quiet: true });
}

export function configureLogging(options: { debug?: boolean } = {}): void {
  loadEnvironment();
  debugEnabled = options.debug ?? false;
}

function formatLine(level: LogLevel, message: string): string {
  const padded = level.padEnd(8, " ");
  return `${new Date().toISOString()} | ${padded} | ${message}`;
}

function emit(level: LogLevel, message: string): void {
  const priority = LEVEL_PRIORITY[level];
  const minStdout = debugEnabled ? LEVEL_PRIORITY.DEBUG : LEVEL_PRIORITY.INFO;
  const line = formatLine(level, message);

  if (priority >= LEVEL_PRIORITY.ERROR) {
    process.stderr.write(`${line}\n`);
  } else if (priority >= minStdout) {
    process.stdout.write(`${line}\n`);
  }

  for (const registered of sinks.values()) {
    if (priority >= registered.minPriority) {
      registered.sink(line, level);
    }
  }
}

export const logger = {
  debug(message: string): void {
    emit("DEBUG", message);
  },
  info(message: string): void {
    emit("INFO", message);
  },
  warning(message: string): void {
    emit("WARNING", message);
  },
  error(message: string): void {
    emit("ERROR", message);
  },
  exception(message: string, error: unknown): void {
    const detail =
      error instanceof Error ? (error.stack ?? `${error.name}: ${error.message}`) : String(error);
    emit("ERROR", `${message}\n${detail}`);
  },
  addSink(sink: LogSink, level: LogLevel = "DEBUG"): number {
    const id = nextSinkId++;
    sinks.set(id, { id, minPriority: LEVEL_PRIORITY[level], sink });
    return id;
  },
  removeSink(id: number): void {
    sinks.delete(id);
  },
};

function stackFramesOnly(error: unknown): string {
  if (!(error instanceof Error) || !error.stack) {
    return "";
  }
  const lines = error.stack.split("\n");
  return lines.filter((line) => /^\s+at\s/.test(line)).join("\n");
}

/**
 * Log a failure with stack frames only, omitting exception messages or local
 * values that could contain secrets such as webhook URLs or database passwords.
 */
export function logFailure(error: unknown, operation: string): void {
  const errorName = error instanceof Error ? error.constructor.name : typeof error;
  const frames = stackFramesOnly(error);
  logger.error(`${operation} failed (${errorName}).\n${frames}`);
}
