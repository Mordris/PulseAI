/**
 * Run `task` one call at a time, and skip a call that a newer one replaced while it waited. A
 * chart re-themed twice in quick succession draws once more, in the last theme, and an earlier,
 * slower draw can never land on top of it.
 */
export function latestOnly(task: () => Promise<void>): () => Promise<void> {
  let queue: Promise<void> = Promise.resolve();
  let latest = 0;
  return () => {
    latest += 1;
    const ticket = latest;
    queue = queue.catch(() => undefined).then(() => (ticket === latest ? task() : undefined));
    return queue;
  };
}
