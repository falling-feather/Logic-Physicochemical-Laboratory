from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math
from typing import Any, Callable


SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION = "astra-sandbox-dom-v1"
ENERGY_CONSERVATION_TEMPLATE_ID = "physics-energy-conservation-v1"


class ScriptSandboxDocumentError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ResolvedScriptSandboxDocument:
    contract_version: str
    template_id: str
    config: dict[str, Any]
    initializer: str
    body_html: str
    stylesheet: str

    def public_contract(self) -> dict[str, Any]:
        return {
            "contractVersion": self.contract_version,
            "templateId": self.template_id,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class _ScriptSandboxTemplate:
    template_id: str
    initializer: str
    normalize_config: Callable[[Any], dict[str, Any]]
    render_body: Callable[[dict[str, Any]], str]
    stylesheet: str


def resolve_script_sandbox_document(value: Any) -> ResolvedScriptSandboxDocument:
    if value is None:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_missing",
            "Script sandbox document contract is required for iframe embedding.",
        )
    if not isinstance(value, dict):
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_invalid",
            "Script sandbox document contract must be an object.",
        )

    allowed_keys = {"contractVersion", "templateId", "config"}
    extra_keys = sorted(str(key) for key in value if key not in allowed_keys)
    if extra_keys:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_invalid",
            "Script sandbox document contract contains unsupported fields.",
        )

    contract_version = value.get("contractVersion")
    if contract_version != SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_contract_unsupported",
            "Script sandbox document contract version is unsupported.",
        )

    template_id = value.get("templateId")
    if not isinstance(template_id, str) or not template_id.strip():
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_invalid",
            "Script sandbox document templateId is required.",
        )
    template = _SCRIPT_SANDBOX_TEMPLATES.get(template_id.strip())
    if template is None:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_template_unsupported",
            "Script sandbox document template is not registered.",
        )

    config = template.normalize_config(value.get("config", {}))
    return ResolvedScriptSandboxDocument(
        contract_version=SCRIPT_SANDBOX_DOCUMENT_CONTRACT_VERSION,
        template_id=template.template_id,
        config=config,
        initializer=template.initializer,
        body_html=template.render_body(config),
        stylesheet=template.stylesheet,
    )


def _normalize_energy_conservation_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_config_invalid",
            "Energy conservation sandbox config must be an object.",
        )
    extra_keys = sorted(str(key) for key in value if key != "defaultFriction")
    if extra_keys:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_config_invalid",
            "Energy conservation sandbox config contains unsupported fields.",
        )
    friction = value.get("defaultFriction", 0.1)
    if isinstance(friction, bool) or not isinstance(friction, (int, float)):
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_config_invalid",
            "Energy conservation defaultFriction must be a number.",
        )
    normalized_friction = float(friction)
    if not math.isfinite(normalized_friction) or normalized_friction < 0 or normalized_friction > 0.3:
        raise ScriptSandboxDocumentError(
            "content_script_sandbox_document_config_invalid",
            "Energy conservation defaultFriction must be between 0 and 0.3.",
        )
    return {"defaultFriction": normalized_friction}


def _render_energy_conservation_body(config: dict[str, Any]) -> str:
    friction = float(config["defaultFriction"])
    friction_value = f"{friction:.2f}"
    input_value = f"{friction:g}"
    return (
        '<main class="sandbox-experiment" data-astra-sandbox-template="physics-energy-conservation-v1">\n'
        '  <header class="sandbox-experiment__header">\n'
        '    <p class="sandbox-experiment__eyebrow">交互实验 · 隔离运行</p>\n'
        '    <h1>机械能守恒</h1>\n'
        '    <p>调节摩擦，观察动能、势能与耗散内能之间的转换。</p>\n'
        '  </header>\n'
        '  <div class="energy-controls" aria-label="机械能守恒实验控制">\n'
        '    <label for="energy-friction">摩擦系数</label>\n'
        f'    <input type="range" id="energy-friction" min="0" max="0.3" step="0.01" value="{escape(input_value, quote=True)}">\n'
        f'    <output id="energy-friction-value" for="energy-friction">{escape(friction_value)}</output>\n'
        '    <button id="energy-play" type="button">⏸ 暂停</button>\n'
        '    <button id="energy-reset" type="button">↺ 重置</button>\n'
        '  </div>\n'
        '  <div class="physics-canvas-wrap">\n'
        '    <canvas id="energy-canvas" role="img" aria-label="机械能守恒过山车与能量柱图">当前浏览器不支持 Canvas。</canvas>\n'
        '  </div>\n'
        '  <div id="energy-info" class="energy-info" aria-live="polite"></div>\n'
        '</main>\n'
    )


_ENERGY_CONSERVATION_STYLESHEET = """
:root {
  color-scheme: dark;
  --font-sans: Inter, "Noto Sans SC", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", Consolas, monospace;
  --text-primary: #eef3ff;
  --text-secondary: #b6c0d8;
  --text-tertiary: #8a91a6;
}
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; background: #060912; color: var(--text-primary); }
body { font-family: var(--font-sans); }
#astra-sandbox-root { min-height: 100%; padding: 14px; }
.sandbox-experiment {
  width: min(100%, 960px);
  margin: 0 auto;
  padding: 16px;
  border: 1px solid rgba(139, 111, 192, .24);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(18, 24, 41, .98), rgba(8, 13, 25, .98));
}
.sandbox-experiment__header { margin-bottom: 14px; }
.sandbox-experiment__header h1 { margin: 2px 0 6px; font-size: clamp(1.1rem, 3vw, 1.45rem); }
.sandbox-experiment__header p { margin: 0; color: var(--text-secondary); line-height: 1.6; }
.sandbox-experiment__eyebrow { color: #a78bfa !important; font-size: .78rem; letter-spacing: .05em; }
.energy-controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 14px; }
.energy-controls label { color: var(--text-secondary); font-size: .86rem; }
.energy-controls input[type="range"] { width: min(180px, 44vw); accent-color: #8b6fc0; }
.energy-controls output { min-width: 3.2rem; color: #c9b8ff; font-family: var(--font-mono); font-size: .82rem; }
.energy-controls button {
  min-height: 40px;
  padding: 8px 13px;
  border: 1px solid rgba(139, 111, 192, .38);
  border-radius: 8px;
  background: rgba(139, 111, 192, .15);
  color: var(--text-primary);
  font: inherit;
  cursor: pointer;
}
.energy-controls button:hover, .energy-controls button:focus-visible { background: rgba(139, 111, 192, .28); outline: none; }
.physics-canvas-wrap { position: relative; overflow: hidden; border-radius: 10px; background: rgba(0, 0, 0, .2); }
.physics-canvas-wrap canvas { display: block; width: 100%; }
.energy-info {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(139, 111, 192, .14);
  border-radius: 8px;
  background: rgba(139, 111, 192, .06);
  color: var(--text-secondary);
  font-size: .84rem;
  line-height: 1.65;
}
.energy-info .ac-hd { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; color: var(--text-primary); font-size: 1rem; font-weight: 600; }
.energy-info .ac-tag { padding: 1px 8px; border-radius: 4px; background: rgba(139, 111, 192, .18); color: #c9b8ff; font-size: .75rem; }
.energy-info .ac-row { display: flex; gap: 8px; margin: 3px 0; }
.energy-info .ac-key { flex: 0 0 auto; color: #79a9e8; font-weight: 600; }
.energy-info .ac-key--purple { color: #b9a2ef; }
.energy-info .ac-key--amber { color: #e5c07b; }
.energy-info .ac-note { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(139, 111, 192, .12); color: var(--text-tertiary); }
@media (max-width: 560px) {
  #astra-sandbox-root { padding: 8px; }
  .sandbox-experiment { padding: 12px; }
  .energy-controls button { flex: 1 1 110px; }
  .energy-info .ac-row { display: block; }
}
""".strip()


_SCRIPT_SANDBOX_TEMPLATES = {
    ENERGY_CONSERVATION_TEMPLATE_ID: _ScriptSandboxTemplate(
        template_id=ENERGY_CONSERVATION_TEMPLATE_ID,
        initializer="initEnergyConservation",
        normalize_config=_normalize_energy_conservation_config,
        render_body=_render_energy_conservation_body,
        stylesheet=_ENERGY_CONSERVATION_STYLESHEET,
    )
}
