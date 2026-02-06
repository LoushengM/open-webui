# RichTextInput performance SLOs

The editor now tracks and warns on the following SLOs:

- **Typing latency (transaction handler p95):** <= 24ms
- **Initial editor load (p95):** <= 1200ms
- **Markdown -> HTML transform benchmark (p95):** <= 160ms
- **HTML -> Markdown approximation benchmark (p95):** <= 120ms

Run local benchmark:

```bash
npm run benchmark:editor
```

Fixtures are stored in `benchmarks/fixtures`.
