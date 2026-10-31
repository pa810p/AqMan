# Aquarium Manager

Local application for keeping aquarium measurements, notes, and water-change history.
The interface defaults to English and can be switched to Polish with the flag buttons in
the application header.

Aquarium cards can include an optional JPEG, PNG, or WebP photo (up to 8 MB). Photos are
cropped to compact thumbnails and stored in the local SQLite database with the aquarium.

## Requirements

- Python 3.12 or newer
- For the native desktop window, pywebview and the operating system's WebView runtime

On Linux, pywebview uses GTK and WebKitGTK. On this workstation the system Python provides
the `gi` bindings, so a virtual environment used for native mode must include system site
packages. Browser mode does not need pywebview or `gi`.

## Setup

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e '.[test,desktop]'
```

If `.venv` already exists, create a separate environment with the command above's option
instead of deleting the existing environment.

## Run

Run in the default browser:

```bash
python -m aqman --mode browser
```

Run in a standalone desktop window:

```bash
python -m aqman --mode native
```

The application binds to `127.0.0.1` by default. `--host` and `--port` can be supplied
when starting the application. Data is stored outside the installation directory under
`~/.local/share/aquarium-manager` (or `$XDG_DATA_HOME/aquarium-manager`). Set
`AQMAN_DATA_DIR` to use another data directory. Rotating application logs are stored in
the `logs` subdirectory there; each log file is limited to 10 MiB with five backups.

On first start, the application creates `$XDG_CONFIG_HOME/aquarium-manager/config.toml`
(defaulting to `~/.config/aquarium-manager/config.toml`). Set `AQMAN_CONFIG_FILE` to use a
different configuration file. Restart the application after changing it. The
`show_time_in_datetime_picker` setting in the `[ui]` section controls whether date/time
pickers display a time; it defaults to `false`. With time hidden, saved records use local
midnight, while the end date in chart ranges includes the full local day. The `[server]`
section configures the listening port; `--port` takes precedence over `AQMAN_PORT`, which
takes precedence over the configured value.

```toml
[server]
port = 8080

[ui]
show_time_in_datetime_picker = false
```

## Tests

Install the test dependencies with `python -m pip install -e '.[test]'`, then run:

```bash
pytest
```

Pytest reports coverage for the `aqman` package in the terminal and generates an HTML
report at `htmlcov/index.html`.
