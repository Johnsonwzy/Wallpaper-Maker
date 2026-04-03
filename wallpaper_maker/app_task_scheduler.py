"""Tk 定时任务调度辅助（从 app.py 拆分）。"""
from __future__ import annotations

from typing import Callable, Optional


def schedule_named_job(
    owner: object,
    *,
    attr_name: str,
    delay_ms: int,
    callback: Callable[[], None],
) -> Optional[str]:
    cancel_named_job(owner, attr_name=attr_name)
    try:
        job_id = owner.after(int(delay_ms), callback)  # type: ignore[attr-defined]
    except Exception:
        setattr(owner, attr_name, None)
        return None
    setattr(owner, attr_name, job_id)
    return job_id


def cancel_named_job(owner: object, *, attr_name: str) -> None:
    job_id = getattr(owner, attr_name, None)
    if job_id is None:
        return
    try:
        owner.after_cancel(job_id)  # type: ignore[attr-defined]
    except Exception:
        pass
    finally:
        setattr(owner, attr_name, None)

