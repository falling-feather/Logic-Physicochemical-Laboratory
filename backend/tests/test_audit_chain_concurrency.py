from pathlib import Path
from threading import Barrier, Thread
import time
from uuid import uuid4

from sqlalchemy import select

from app.db.session import get_session_factory, init_db, make_engine, reset_database_state
from app.models import AuditChainHead, AuditLog
from app.services.audit import record_audit_log
from app.services.audit_chain import verify_audit_log_chain


def test_concurrent_audit_writers_share_one_serial_tail_on_sqlite_fallback():
    runtime_dir = Path.cwd() / "pytest-cache-files-audit-chain"
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / f"audit-chain-{uuid4().hex}.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    errors: list[Exception] = []
    barrier = Barrier(2)
    try:
        init_db(database_url)
        session_factory = get_session_factory(database_url)

        def write_audit(index: int) -> None:
            try:
                with session_factory() as db:
                    barrier.wait(timeout=5)
                    record_audit_log(
                        db,
                        action=f"test.audit.concurrent.{index}",
                        resource_type="concurrency_test",
                        event_result="success",
                    )
                    time.sleep(0.05)
                    db.commit()
            except Exception as exc:
                errors.append(exc)

        threads = [Thread(target=write_audit, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
        assert errors == []

        with session_factory() as db:
            logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all())
            head = db.get(AuditChainHead, 1)
            report = verify_audit_log_chain(logs)
        assert len(logs) == 2
        assert logs[0].prev_hash is None
        assert logs[1].prev_hash == logs[0].current_hash
        assert head.current_audit_log_id == logs[1].id
        assert head.current_hash == logs[1].current_hash
        assert report["status"] == "valid"
    finally:
        make_engine(database_url).dispose()
        reset_database_state()
        if database_path.exists():
            database_path.unlink()
