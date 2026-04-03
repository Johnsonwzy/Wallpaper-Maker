"""程序入口。"""
from __future__ import annotations

import sys
import time
import traceback

from wallpaper_maker.app import WallPaperApp
from wallpaper_maker.core import run_cli


def _run_gui_self_test(*, verbose: bool = False, no_preview: bool = False) -> int:
    """GUI 冒烟自检：创建窗口 -> 关键路径 -> 自动退出。"""
    app: WallPaperApp | None = None
    checks: list[tuple[str, bool, str]] = []

    def _record(name: str, ok: bool, detail: str = "", *, elapsed_ms: float | None = None) -> None:
        checks.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        msg = f"[self-test] {status} {name}"
        if detail:
            msg += f" :: {detail}"
        if verbose and elapsed_ms is not None:
            msg += f" ({elapsed_ms:.1f} ms)"
        print(msg)

    def _run_step(name: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        dt = (time.perf_counter() - t0) * 1000.0
        _record(name, True, elapsed_ms=dt)

    try:
        def _step_create_app() -> None:
            nonlocal app
            app = WallPaperApp()
            app.update_idletasks()
            app.update()

        _run_step("create_app", _step_create_app)

        def _step_theme_light() -> None:
            assert app is not None
            app.var_ui_theme_mode.set("light")
            app._apply_theme()
            app.update_idletasks()
            app.update()

        _run_step("apply_theme_light", _step_theme_light)

        def _step_theme_system_poll() -> None:
            assert app is not None
            app.var_ui_theme_mode.set("system")
            app._poll_system_theme_follow()
            app.update_idletasks()
            app.update()

        _run_step("apply_theme_system_poll", _step_theme_system_poll)

        if no_preview:
            _record("preview_steps_skipped", True, "no-preview mode")
        else:
            def _step_init_preview_gallery() -> None:
                assert app is not None
                app._init_preview_gallery_window()
                app.update_idletasks()
                app.update()
                if app.preview_gallery is None:
                    raise RuntimeError("preview_gallery is None")

            _run_step("init_preview_gallery", _step_init_preview_gallery)

            def _step_sync_preview_geometry() -> None:
                assert app is not None and app.preview_gallery is not None
                app._preview_gallery_user_hidden = False
                app.preview_gallery.show_again()
                app._sync_preview_geometry()
                app.update_idletasks()
                app.update()

            _run_step("sync_preview_geometry", _step_sync_preview_geometry)

            def _step_refresh_preview_live() -> None:
                assert app is not None
                app._refresh_preview_filter_live()
                app.update_idletasks()
                app.update()

            _run_step("refresh_preview_live", _step_refresh_preview_live)
    except Exception as exc:
        _record("exception", False, f"{type(exc).__name__}: {exc}")
        print("[self-test] traceback begin")
        print(traceback.format_exc().rstrip())
        print("[self-test] traceback end")
    finally:
        if app is not None:
            try:
                app._on_close_main_window()
            except Exception:
                try:
                    app.destroy()
                except Exception:
                    pass

    failed = [c for c in checks if not c[1]]
    if failed:
        print(f"[self-test] RESULT: FAIL ({len(failed)} failed / {len(checks)} total)")
        return 1
    print(f"[self-test] RESULT: PASS ({len(checks)} checks)")
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and "--self-test" in argv:
        verbose = "--self-test-verbose" in argv
        no_preview = "--self-test-no-preview" in argv
        raise SystemExit(_run_gui_self_test(verbose=verbose, no_preview=no_preview))
    if argv and "--cli" in argv:
        run_cli()
    else:
        WallPaperApp().mainloop()


if __name__ == "__main__":
    main()
