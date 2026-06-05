# Live Overlay Strategy

The live suggestion overlay remains in the Python/Win32 runtime for now. It is latency-sensitive, must stay topmost without stealing focus, and is tightly coupled to the current keyboard hook, caret locator, and text injection flow.

The Tauri/React migration is settings-first. Tauri owns the modern settings/dashboard surface, while the live typing overlay continues to use the current native Windows implementation until a dedicated replacement is proven.

Current overlay priorities:

- keep the overlay window alive and update its contents in place
- avoid focus stealing with `WS_EX_NOACTIVATE`
- use compact QuickType-style suggestion chips
- avoid flicker through buffered painting
- clamp near the caret while staying inside the active monitor work area
- keep keyboard and mouse selection behavior unchanged

Future native overlay spike:

- evaluate a small C# or Rust native overlay for the live suggestion bar
- keep it separate from correction, SafetyGate, datasets, and local AI logic
- measure input latency, flicker, DPI handling, focus behavior, and multi-monitor positioning before migration
- keep the Python/Win32 overlay as the fallback until the replacement is demonstrably smoother and at least as reliable
