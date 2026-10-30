import argparse
import ctypes.util
import importlib.util


def check_native_dependencies() -> list[str]:
    missing: list[str] = []

    for module in ("nicegui", "webview", "gi"):
        if importlib.util.find_spec(module) is None:
            missing.append(f"Python module: {module}")

    if ctypes.util.find_library("gtk-3") is None:
        missing.append("System library: GTK 3")

    if not any(
        ctypes.util.find_library(name) is not None
        for name in ("webkit2gtk-4.1", "webkit2gtk-4.0")
    ):
        missing.append("System library: WebKitGTK 4.0 or 4.1")

    return missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("browser", "native"),
        help="Open the PoC in a browser or in a pywebview desktop window",
    )
    mode = parser.parse_args().mode

    if mode == "native":
        missing = check_native_dependencies()
        if missing:
            print("Standalone mode cannot start; missing dependencies:")
            for dependency in missing:
                print(f"- {dependency}")
            print("The browser mode does not require the GTK/WebKit dependencies.")
            raise SystemExit(1)
    elif importlib.util.find_spec("nicegui") is None:
        print("Browser mode requires the Python package: nicegui")
        raise SystemExit(1)

    from nicegui import ui

    ui.label("Aquarium Manager — WebView PoC").classes("text-h4")
    ui.label(f"Try the {mode} launch mode.")
    ui.run(
        native=mode == "native",
        host="127.0.0.1",
        port=8080,
        reload=False,
        show=mode == "browser",
        title="Aquarium Manager PoC",
        window_size=(900, 600),
    )


if __name__ == "__main__":
    main()
