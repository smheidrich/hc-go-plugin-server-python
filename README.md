# hc-go-plugin-server

Python server for HashiCorp's go-plugin (RPCPlugin)

DON'T use this yet if you aren't me, trust me.

## Development

### Sync/Async variants

The sync variant of the API is automatically generated from the async one
using [unasync](https://pypi.org/project/unasync/). With dev dependencies
installed, you can regenerate them by running `run_unasync.py` as a Python
script (e.g. via `poetry run run_unasync.py`).
