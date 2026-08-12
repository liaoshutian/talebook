#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vercel_container_uses_repository_code_and_demo_seed():
    dockerfile = (ROOT / "Dockerfile.vercel").read_text(encoding="utf-8")

    assert "FROM talebook/talebook@sha256:" in dockerfile
    assert " AS vercel-demo" in dockerfile
    assert "COPY webserver/ ./webserver/" in dockerfile
    assert "COPY --from=frontend-builder /app-static/ ./app/" in dockerfile
    assert "COPY docker/vercel/auto.py /prebuilt/books/settings/auto.py" in dockerfile
    assert "COPY docker/vercel/start.sh ./docker/vercel/start.sh" in dockerfile
    assert "COPY docker/vercel/bootstrap.sh ./docker/vercel/bootstrap.sh" in dockerfile
    assert "COPY docker/vercel/gateway.py ./docker/vercel/gateway.py" in dockerfile
    assert "COPY docker/vercel/supervisor.conf /etc/supervisor/conf.d/talebook.conf" in dockerfile
    assert "ln -s /tmp/talebook/data /data" in dockerfile
    assert "setcap -r /usr/sbin/nginx" in dockerfile
    assert "FROM scratch AS vercel-runtime" in dockerfile
    assert "COPY --from=vercel-demo / /" in dockerfile
    assert "LD_LIBRARY_PATH=/usr/lib/talebook-calibre/lib" in dockerfile
    assert 'CMD ["/var/www/talebook/docker/vercel/start.sh"]' in dockerfile
    assert 'EXPOSE 80' in dockerfile

    dockerignore = (ROOT / "Dockerfile.vercel.dockerignore").read_text(encoding="utf-8")
    assert dockerignore.startswith("**\n")
    assert "!app/**" in dockerignore
    assert "!webserver/**" in dockerignore
    assert "app/node_modules" in dockerignore
    assert "app/.output" in dockerignore

    vercelignore = (ROOT / ".vercelignore").read_text(encoding="utf-8")
    assert ".venv" in vercelignore
    assert ".worktrees" in vercelignore
    assert "app/node_modules" in vercelignore
    assert "tests" in vercelignore


def test_vercel_demo_seed_is_installed_read_only_demo():
    settings = runpy.run_path(str(ROOT / "docker/vercel/auto.py"))["settings"]

    assert settings["installed"] is True
    assert settings["DEMO_MODE"] is True
    assert settings["DEMO_USERNAME"] == "demo"
    assert settings["nuxt_env_path"].startswith("/tmp/")
    assert settings["ALLOW_REGISTER"] is False
    assert settings["ALLOW_GUEST_UPLOAD"] is False
    assert settings["ALLOW_GUEST_PUSH"] is False
    assert settings["ALLOW_GUEST_READ"] is True


def test_vercel_runtime_writes_only_to_tmp():
    start_script = (ROOT / "docker/vercel/start.sh").read_text(encoding="utf-8")
    nginx = (ROOT / "docker/vercel/nginx.conf").read_text(encoding="utf-8")

    assert "runtime_dir=/tmp/talebook" in start_script
    assert '"$data_dir/log/nginx"' in start_script
    assert "cp -a /prebuilt/books" not in start_script
    assert "groupmod" not in start_script
    assert "usermod" not in start_script
    assert "chown" not in start_script
    assert "pid /tmp/talebook/run/nginx.pid;" in nginx
    assert "user root;" in nginx
    assert "_temp_path /tmp/talebook/" in nginx
    assert "error_log /tmp/talebook/log/nginx/error.log" in nginx

    supervisor = (ROOT / "docker/vercel/supervisor.conf").read_text(encoding="utf-8")
    assert "user=talebook" not in supervisor
    assert "gosu" not in supervisor
    assert "/dev/fd/1" not in supervisor
    assert "stdout_logfile=/dev/stdout" in supervisor
    assert "programs=gateway,nginx,bootstrap,tornado" in supervisor

    gateway = (ROOT / "docker/vercel/gateway.py").read_text(encoding="utf-8")
    assert 'LISTEN = ("0.0.0.0", 80)' in gateway
    assert 'UPSTREAM = ("127.0.0.1", 8081)' in gateway
    assert "wait_for_ready()" in gateway

    bootstrap = (ROOT / "docker/vercel/bootstrap.sh").read_text(encoding="utf-8")
    assert "cp -a /prebuilt/books /data/" in bootstrap
