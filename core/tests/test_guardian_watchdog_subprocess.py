"""The genuine out-of-process proof: `aura guardian watch` run as a real,
separate OS process that shares nothing with the "main" process below
except the on-disk SQLite file -- exactly how it's meant to run for
real, and the only way this feature's actual claim (a hung or
compromised core process can't silently disable the thing watching it)
means anything more than an in-process unit test could ever prove."""
from __future__ import annotations

import os
import subprocess
import sys
import time

from aura_core.governance.action_broker import ActionBroker
from aura_core.governance.approval_engine import ApprovalEngine
from aura_core.governance.audit_log import AuditLog
from aura_core.governance.credential_broker import CredentialBroker
from aura_core.governance.policy_engine import PolicyEngine
from aura_core.governance.risk_engine import ActionRequest, RiskEngine


def test_a_real_separate_os_process_engages_the_kill_switch(tmp_path):
    db_url = f"sqlite:///{tmp_path}/watchdog_subprocess.db"
    env = {
        **os.environ, "AURA_DATABASE_URL": db_url,
        "AURA_ENV": "test", "AURA_OLLAMA_HOST": "http://127.0.0.1:1",
    }

    watchdog_proc = subprocess.Popen(
        [sys.executable, "-m", "aura_core.cli", "guardian", "watch", "--poll-interval-seconds", "0.2"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        # The "main" process's own objects, pointed at the same on-disk
        # database -- nothing here talks to the watchdog subprocess
        # directly, only through the shared audit log / policy state.
        policy = PolicyEngine(db_url)
        audit = AuditLog(db_url)
        broker = ActionBroker(policy, RiskEngine(), ApprovalEngine(db_url), CredentialBroker(), audit)
        policy.set_autonomy_level("finance.change_bank_details", 5)

        outcomes = [
            broker.submit(ActionRequest(action_type="finance.change_bank_details"))
            for _ in range(3)
        ]
        assert all(o.status.value == "PENDING_APPROVAL" for o in outcomes)  # RED always needs approval
        assert policy.is_kill_switch_engaged() is False  # not yet -- the subprocess hasn't polled

        deadline = time.time() + 15
        while not policy.is_kill_switch_engaged() and time.time() < deadline:
            time.sleep(0.2)

        assert watchdog_proc.poll() is None, f"watchdog process exited early:\n{watchdog_proc.stdout.read()}"
        assert policy.is_kill_switch_engaged() is True, "a separate OS process never engaged the kill switch in time"

        # And it's real for the "main" process too, not just readable --
        # the next action is genuinely blocked by state a process it
        # never talked to directly just wrote.
        blocked = broker.submit(ActionRequest(action_type="status.read"))
        assert blocked.status.value == "KILL_SWITCH_ENGAGED"
    finally:
        watchdog_proc.terminate()
        try:
            watchdog_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            watchdog_proc.kill()
