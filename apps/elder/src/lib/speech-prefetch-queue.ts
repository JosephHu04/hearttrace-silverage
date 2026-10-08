type SpeechItem<T> = {
  text: string;
  audio: Promise<T | null> | null;
};

/** Prepare the next utterance while the current one is playing. */
export class SpeechPrefetchQueue<T> {
  private items: SpeechItem<T>[] = [];
  private controllers = new Set<AbortController>();
  private active = 0;
  private generation = 0;
  private readonly load: (text: string, signal: AbortSignal) => Promise<T>;
  private readonly concurrency: number;

  constructor(
    load: (text: string, signal: AbortSignal) => Promise<T>,
    concurrency = 2,
  ) {
    this.load = load;
    this.concurrency = concurrency;
  }

  get length(): number { return this.items.length; }

  push(texts: string[]): void {
    this.items.push(...texts.filter(Boolean).map((text) => ({ text, audio: null })));
    this.prefetch();
  }

  shift(): Promise<T | null> | null {
    const item = this.items.shift();
    if (!item) return null;
    // Normally prefetch already started it; this also handles an unusually
    // fast playback overtaking the two in-flight requests.
    if (!item.audio) this.start(item);
    this.prefetch();
    return item.audio;
  }

  clear(): void {
    this.generation += 1;
    this.items = [];
    this.active = 0;
    for (const controller of this.controllers) controller.abort();
    this.controllers.clear();
  }

  private start(item: SpeechItem<T>): void {
    const controller = new AbortController();
    const generation = this.generation;
    this.controllers.add(controller);
    this.active += 1;
    item.audio = this.load(item.text, controller.signal).catch(() => null).finally(() => {
      this.controllers.delete(controller);
      if (generation !== this.generation) return;
      this.active -= 1;
      this.prefetch();
    });
  }

  private prefetch(): void {
    while (this.active < this.concurrency) {
      const next = this.items.find((item) => !item.audio);
      if (!next) break;
      this.start(next);
    }
  }
}
