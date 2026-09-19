from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Callable, Any

import httpx

from ..config import DEFAULT_COMFYUI_URL, WORKFLOWS_DIR

CONSISTENCY_PROMPT = "Preserve original character design. Preserve clay texture. Preserve clothing. Preserve face shape. Do not change species. Do not add characters. Do not remove characters. No extra limbs. No warped paws. No deformed eyes. No melting face. No random mouth movement from characters who are not speaking. No sudden camera cuts unless requested."

class ComfyUIAdapter:
    def __init__(self, base_url: str = DEFAULT_COMFYUI_URL):
        self.base_url = base_url.rstrip("/")

    def availability(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/system_stats", timeout=2.0)
            return {"available": r.status_code == 200, "details": r.json() if r.status_code == 200 else {}}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    def list_workflows(self) -> list[dict]:
        rows = []
        for config in WORKFLOWS_DIR.glob("*.adapter.json"):
            try:
                data = json.loads(config.read_text(encoding="utf-8"))
                data["config_file"] = str(config)
                rows.append(data)
            except Exception:
                continue
        return rows


    def hardware_requirements(self, workflow_name: str) -> dict:
        config_path = WORKFLOWS_DIR / f"{workflow_name}.adapter.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing workflow adapter: {config_path.name}")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return {"minimum_vram_gb": float(config.get("minimum_vram_gb", 0) or 0), "notes": config.get("hardware_notes", "")}

    def _set_node_input(self, prompt: dict, mapping: dict, value: Any) -> None:
        node_id = str(mapping["node"])
        field = mapping["field"]
        if node_id not in prompt:
            raise KeyError(f"Workflow node {node_id} is missing")
        prompt[node_id].setdefault("inputs", {})[field] = value

    def prepare_prompt(self, workflow_name: str, values: dict) -> tuple[dict, dict]:
        config_path = WORKFLOWS_DIR / f"{workflow_name}.adapter.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing workflow adapter: {config_path.name}")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        workflow_file = WORKFLOWS_DIR / config["workflow"]
        prompt = json.loads(workflow_file.read_text(encoding="utf-8"))
        mapping = config.get("mapping", {})
        for key, value in values.items():
            if key in mapping and value is not None:
                self._set_node_input(prompt, mapping[key], value)
        if "prompt" in values and "prompt" in mapping:
            self._set_node_input(prompt, mapping["prompt"], f"{values['prompt']} {CONSISTENCY_PROMPT}")
        return prompt, config

    def generate(self, workflow_name: str, values: dict, progress_cb: Callable[[float, str], None] | None = None, timeout: int = 3600) -> Path:
        prompt, config = self.prepare_prompt(workflow_name, values)
        client_id = uuid.uuid4().hex
        with httpx.Client(timeout=20.0) as client:
            upload_image = values.get("input_image")
            if upload_image:
                p = Path(upload_image)
                with p.open("rb") as fh:
                    r = client.post(f"{self.base_url}/upload/image", files={"image": (p.name, fh, "application/octet-stream")}, data={"overwrite": "true"})
                    r.raise_for_status()
                uploaded_name = r.json().get("name", p.name)
                if "input_image" in config.get("mapping", {}):
                    self._set_node_input(prompt, config["mapping"]["input_image"], uploaded_name)
            audio = values.get("audio")
            if audio and "audio" in config.get("mapping", {}):
                p = Path(audio)
                with p.open("rb") as fh:
                    r = client.post(f"{self.base_url}/upload/image", files={"image": (p.name, fh, "application/octet-stream")}, data={"overwrite": "true", "type": "input"})
                    r.raise_for_status()
                uploaded_name = r.json().get("name", p.name)
                self._set_node_input(prompt, config["mapping"]["audio"], uploaded_name)
            r = client.post(f"{self.base_url}/prompt", json={"prompt": prompt, "client_id": client_id})
            r.raise_for_status()
            prompt_id = r.json()["prompt_id"]

            start = time.time()
            while time.time() - start < timeout:
                if progress_cb:
                    progress_cb(min(0.95, (time.time() - start) / max(60, timeout * 0.25)), "Generating Motion")
                history = client.get(f"{self.base_url}/history/{prompt_id}").json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    output_node = str(config.get("output_node", ""))
                    candidate = outputs.get(output_node, {}) if output_node else {}
                    files = candidate.get("gifs") or candidate.get("images") or candidate.get("videos") or []
                    if not files:
                        for node in outputs.values():
                            files.extend(node.get("gifs") or node.get("videos") or node.get("images") or [])
                    if not files:
                        raise RuntimeError("ComfyUI completed but the configured output node returned no file.")
                    item = files[0]
                    params = {"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}
                    data = client.get(f"{self.base_url}/view", params=params).content
                    target = Path(values["output_path"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    if progress_cb: progress_cb(1.0, "Complete")
                    return target
                time.sleep(1.0)
        raise TimeoutError("ComfyUI generation timed out")
