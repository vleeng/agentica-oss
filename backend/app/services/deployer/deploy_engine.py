from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader

from app.core.config import get_settings
from app.schemas.agent import AgentDesign

settings = get_settings()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "builders" / "templates"


class DeployEngineService:
    """
    Orquesta el ciclo completo de deploy de un agente:
    1. Genera los archivos del agente (código + Dockerfile)
    2. Build de la imagen Docker
    3. Configura Traefik (label en docker run)
    4. Lanza el contenedor
    5. Registra el endpoint en la DB
    """

    def __init__(self):
        self._builds_path = Path(settings.builds_path)
        self._builds_path.mkdir(parents=True, exist_ok=True)
        self._jinja = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    async def deploy(self, design: AgentDesign, tenant_id: str) -> dict:
        agent_id = str(design.agent_id)
        build_dir = self._builds_path / tenant_id / agent_id
        build_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[DEPLOY] Generando archivos para agent_id={agent_id}")
        await self._generate_agent_files(design, build_dir)

        logger.info(f"[DEPLOY] Build Docker para agent_id={agent_id}")
        image_tag = f"agentica-agent-{agent_id[:8]}:latest"
        await self._docker_build(build_dir, image_tag)

        logger.info(f"[DEPLOY] Lanzando contenedor para agent_id={agent_id}")
        container_id = await self._docker_run(agent_id, tenant_id, image_tag)

        endpoint_url = f"https://api.{_get_base_domain()}/agents/{tenant_id[:8]}/{agent_id[:8]}/invoke"
        ws_url       = f"wss://api.{_get_base_domain()}/agents/{tenant_id[:8]}/{agent_id[:8]}/ws"

        logger.info(f"[DEPLOY] Agente desplegado en {endpoint_url}")
        return {
            "agent_id": agent_id,
            "container_id": container_id,
            "endpoint_url": endpoint_url,
            "ws_url": ws_url,
            "status": "active",
        }

    # ── Generación de archivos ────────────────────────────────────────────────

    async def _generate_agent_files(self, design: AgentDesign, build_dir: Path) -> None:
        spec = design.spec
        fw   = design.framework

        ctx = {
            "agent_id":      str(design.agent_id),
            "agent_name":    spec.name,
            "system_prompt": design.system_prompt,
            "framework":     fw.framework,
            "agent_type":    fw.agent_type or "openai_functions",
            "process":       fw.process.value if fw.process else "sequential",
            "model":         spec.model_params.model,
            "temperature":   spec.model_params.temperature,
            "max_tokens":    spec.model_params.max_tokens,
            "tools":         [{"name": t.name, "config": t.config} for t in spec.tools],
            "agents":        [a.model_dump() for a in spec.agents],
            "memory_type":   spec.memory.type.value,
            "memory_ttl":    spec.memory.ttl_seconds or 3600,
            "rag_enabled":   spec.rag.enabled,
            "mode":          spec.mode.value,
        }

        # agent.py
        template_name = f"agent_{fw.framework}.py.j2"
        agent_code = self._jinja.get_template(template_name).render(**ctx)
        (build_dir / "agent.py").write_text(agent_code)

        # api.py — FastAPI app del agente desplegado
        api_code = self._jinja.get_template("agent_api.py.j2").render(**ctx)
        (build_dir / "api.py").write_text(api_code)

        # Dockerfile
        dockerfile = self._jinja.get_template("Dockerfile.j2").render(**ctx)
        (build_dir / "Dockerfile").write_text(dockerfile)

        # requirements mínimos del agente
        reqs = self._jinja.get_template("requirements_agent.txt.j2").render(**ctx)
        (build_dir / "requirements.txt").write_text(reqs)

        # metadata JSON para el runtime
        meta = {
            "agent_id": str(design.agent_id),
            "framework": fw.framework,
            "mode": spec.mode.value,
            "version": design.version,
        }
        (build_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    # ── Docker ────────────────────────────────────────────────────────────────

    async def _docker_build(self, build_dir: Path, image_tag: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "docker", "build", "-t", image_tag, str(build_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Docker build falló:\n{stderr.decode()}")

    async def _docker_run(
        self,
        agent_id: str,
        tenant_id: str,
        image_tag: str,
    ) -> str:
        container_name = f"agent_{agent_id[:8]}_{tenant_id[:8]}"
        base_domain = _get_base_domain()

        # Traefik labels para ruteo automático
        labels = [
            f"traefik.enable=true",
            f"traefik.http.routers.{container_name}.rule="
            f"Host(`api.{base_domain}`) && PathPrefix(`/agents/{tenant_id[:8]}/{agent_id[:8]}`)",
            f"traefik.http.routers.{container_name}.entrypoints=websecure",
            f"traefik.http.routers.{container_name}.tls.certresolver=letsencrypt",
            f"traefik.http.services.{container_name}.loadbalancer.server.port=8080",
            f"traefik.http.middlewares.{container_name}-strip.stripprefix.prefixes="
            f"/agents/{tenant_id[:8]}/{agent_id[:8]}",
            f"traefik.http.routers.{container_name}.middlewares={container_name}-strip",
        ]

        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--restart", "unless-stopped",
            f"--network={settings.docker_network}",
            "-e", f"AGENT_ID={agent_id}",
            "-e", f"TENANT_ID={tenant_id}",
            "-e", f"ANTHROPIC_API_KEY={settings.anthropic_api_key}",
            "-e", f"REDIS_URL={settings.redis_url}",
            "-e", f"DATABASE_URL={settings.database_url}",
        ]
        for label in labels:
            cmd += ["--label", label]
        cmd.append(image_tag)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Docker run falló:\n{stderr.decode()}")

        return stdout.decode().strip()[:12]  # container ID abreviado

    async def stop_agent(self, container_id: str) -> None:
        """Para y elimina el contenedor de un agente."""
        for cmd in [["docker", "stop", container_id], ["docker", "rm", container_id]]:
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.communicate()


def _get_base_domain() -> str:
    return os.getenv("BASE_DOMAIN", "axenova.com")
