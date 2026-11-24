import { useEffect, useState } from 'react';

/** The current time, refreshed every `everyMs` (a local clock tick, not a server call). */
export function useNow(everyMs) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(timer);
  }, [everyMs]);
  return now;
}
