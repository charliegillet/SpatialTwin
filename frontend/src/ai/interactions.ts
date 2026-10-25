export interface ActivitySnapshot<T> {
  readonly events: readonly T[];
  readonly lastId: number;
}

/** Hold a display snapshot while the parent's bounded live buffer keeps growing. */
export function pauseActivity<T extends { id: number }>(events: readonly T[]): ActivitySnapshot<T> {
  return { events: [...events], lastId: events[events.length - 1]?.id ?? 0 };
}

export function getActivityView<T extends { id: number }>(incoming: readonly T[], held: ActivitySnapshot<T> | null) {
  return {
    events: held?.events ?? incoming,
    bufferedCount: held ? incoming.filter(event => event.id > held.lastId).length : 0,
  };
}
