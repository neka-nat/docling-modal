# docling-modal


## Setup

```bash
uv sync
# If you get an error about the number of inotify watchers, you can increase the limit.
# sudo sysctl fs.inotify.max_user_watches=524288
uv run modal setup
uv run modal deploy app.py
```

```bash
curl -X POST https://<your-app-name>.modal.run/convert -H "Content-Type: multipart/form-data" -F "file=@test.pdf"
```
