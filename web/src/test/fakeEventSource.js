/** Stands in for the browser's EventSource in tests: `vi.stubGlobal('EventSource', FakeEventSource)`. */
export class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances = [];

  static latest() {
    return FakeEventSource.instances.at(-1);
  }

  constructor(url) {
    this.url = url;
    this.readyState = FakeEventSource.CONNECTING;
    FakeEventSource.instances.push(this);
  }

  open() {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.({});
  }

  emit(data) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }

  /** closedForGood: the server refused (e.g. 404), so the browser won't retry by itself. */
  fail(closedForGood = false) {
    this.readyState = closedForGood ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING;
    this.onerror?.({});
  }

  close() {
    this.readyState = FakeEventSource.CLOSED;
    this.closed = true;
  }
}
