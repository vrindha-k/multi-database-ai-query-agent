import os
import subprocess
import sys

import pytest


def test_cli_help_and_exit():
    env = os.environ.copy()
    env["DATABASES_JSON"] = "[]"
    env["ANTHROPIC_API_KEY"] = ""
    env.pop("DATABASE_CONFIG_FILE", None)
    process = subprocess.run(
        [sys.executable, "-m", "app.cli"],
        input="/help\n/databases\n/exit\n",
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
    )
    assert process.returncode == 0
    assert "Multi-Database AI Query Agent" in process.stdout
    assert "/use ID" in process.stdout


@pytest.mark.integration
def test_cli_switch_and_query(registry):
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = ""
    process = subprocess.run(
        [sys.executable, "-m", "app.cli"],
        input="/use ecommerce\n/sql SELECT count(*) AS total_orders FROM orders\n"
        "/use hr\n/sql SELECT count(*) AS total_employees FROM employees\n"
        "/sql DELETE FROM employees\n/exit\n",
        text=True,
        capture_output=True,
        timeout=30,
        env=env,
    )
    assert process.returncode == 0
    assert "720" in process.stdout and "80" in process.stdout
    assert "Only one SELECT" in process.stdout
