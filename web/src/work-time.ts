function localParts(value: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(value);
  const get = (name: string) => parts.find((part) => part.type === name)!.value;
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}:${get("second")}`;
}

export function localInput(value: string, timezone: string) {
  return localParts(new Date(value), timezone).slice(0, 16);
}

export function localToUtc(value: string, timezone: string): string | null {
  const expected = value.length === 16 ? value + ":00" : value;
  const target = Date.parse(expected + "Z");
  if (!Number.isFinite(target)) return null;
  const candidates = new Set<number>();
  for (const hours of [-36, -12, 0, 12, 36]) {
    const sample = target + hours * 3600000;
    const offset =
      Date.parse(localParts(new Date(sample), timezone) + "Z") - sample;
    const instant = target - offset;
    if (localParts(new Date(instant), timezone) === expected)
      candidates.add(instant);
  }
  return candidates.size === 1
    ? new Date([...candidates][0]).toISOString()
    : null;
}
