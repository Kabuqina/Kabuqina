import pytest

from cron.jobs import create_job, load_jobs, save_jobs, update_job
from cron.scheduler import _deliver_result, _resolve_delivery_target


def test_new_removed_cron_target_rejected_without_write(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    save_jobs([])
    with pytest.raises(ValueError, match="kabuqina.delivery/v1"):
        create_job("hello", "30m", deliver="feishu:oc_old")
    assert load_jobs() == []


def test_existing_removed_target_preserved_but_execution_is_unsupported(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    # Execution preflight happens before config or adapter/network loading.
    error = _deliver_result({"id": "old", "deliver": "discord:123"}, "hello")
    assert error.startswith("unsupported_delivery")
    assert "kabuqina.delivery/v1" in error


def test_desktop_origin_without_origin_never_reroutes(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    monkeypatch.setenv("WEIXIN_HOME_CHANNEL", "some-other-chat")
    assert _resolve_delivery_target({"deliver": "origin"}) is None


def test_non_delivery_edit_of_old_job_remains_supported(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    job = create_job("hello", "30m", deliver="local")
    jobs = load_jobs()
    jobs[0]["deliver"] = "feishu:oc_old"  # simulate persisted pre-C02 data
    save_jobs(jobs)
    updated = update_job(job["id"], {"name": "still manageable"})
    assert updated["deliver"] == "feishu:oc_old"
    assert updated["name"] == "still manageable"


def test_replacing_old_delivery_target_is_validated(monkeypatch):
    monkeypatch.setenv("KABUQINA_PRODUCT_PROFILE", "mainland_cn")
    job = create_job("hello", "30m", deliver="local")
    with pytest.raises(ValueError, match="unsupported_delivery"):
        update_job(job["id"], {"deliver": "wecom:old"})
