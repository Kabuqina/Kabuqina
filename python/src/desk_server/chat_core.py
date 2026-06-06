# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Desk chat helpers."""
from __future__ import annotations
import base64, io, json, logging, os, re, threading, time, uuid, zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET
from capability_prompt import build_capability_prompt_summary
from desk_server.capabilities import get_desk_catalog_payload_cached
from desk_server.interactions import interaction_manager
log = logging.getLogger(__name__)
_desk_active_agents: Dict[str, Any] = {}
_desk_active_lock = threading.Lock()
_DESK_MAX_ATTACHMENTS = 6
_DESK_MAX_ATTR_BYTES = 12 * 1024 * 1024
_DESK_MAX_INLINE_CHARS = 200_000


def _desk_register_active(session_id: str, agent: Any) -> None:
    with _desk_active_lock:
        _desk_active_agents[session_id] = agent


def _desk_unregister_active(session_id: str) -> None:
    with _desk_active_lock:
        _desk_active_agents.pop(session_id, None)


_DESK_PROGRESS_EVENT_CAP = 200


def _desk_progress_response(
    agent: Any,
    since: int = 0,
    events_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    progress = dict(getattr(agent, "_progress", {}) or {})
    events_out: List[Dict[str, Any]] = []
    next_seq = 0
    lock = getattr(agent, "_progress_event_lock", None)
    if lock is not None:
        with lock:
            all_events = list(getattr(agent, "_progress_events", []) or [])
            next_seq = int(getattr(agent, "_progress_event_seq", 0) or 0)
        if events_override is not None:
            events_out = events_override
        else:
            events_out = [e for e in all_events if int(e.get("seq", 0)) > int(since or 0)]
    progress["events"] = events_out
    progress["next_seq"] = next_seq
    return progress


def _desk_attach_progress_events(agent: Any, stream_emit: Optional[Any] = None) -> None:
    """Wire `tool_progress_callback` to record per-tool events on the agent.

    The frontend polls /api/desk/chat-preview/{sid}?since=N to render a live
    step list (tool name + preview + duration). Events are kept on the agent
    as a ring buffer; the callback only forwards `tool.started` / `tool.completed`.
    """
    agent._progress_events = []
    agent._progress_event_seq = 0
    agent._progress_event_lock = threading.Lock()

    def _cb(event_type, name, preview, args, duration=None, is_error=None):
        if event_type not in ("tool.started", "tool.completed"):
            return
        event_payload: Optional[Dict[str, Any]] = None
        try:
            with agent._progress_event_lock:
                agent._progress_event_seq += 1
                event_payload = {
                    "seq": agent._progress_event_seq,
                    "kind": event_type,
                    "tool": str(name) if name else "",
                    "preview": preview if isinstance(preview, str) else None,
                    "duration": float(duration) if duration is not None else None,
                    "is_error": bool(is_error) if is_error else False,
                    "ts": time.time(),
                }
                agent._progress_events.append(event_payload)
                if len(agent._progress_events) > _DESK_PROGRESS_EVENT_CAP:
                    agent._progress_events = agent._progress_events[-_DESK_PROGRESS_EVENT_CAP:]
        except Exception:
            log.debug("desk progress event callback failed", exc_info=True)
        if stream_emit is not None and event_payload is not None:
            try:
                stream_emit({
                    "type": "progress",
                    "progress": _desk_progress_response(agent, events_override=[event_payload]),
                })
            except Exception:
                log.debug("desk progress stream emit failed", exc_info=True)

    agent.tool_progress_callback = _cb


def _desk_prepare_active_agent(
    session_id: str,
    agent: Any,
    stream_delta_callback: Optional[Any] = None,
    progress_event_callback: Optional[Any] = None,
) -> None:
    """Make a desk agent visible to preview/stop before its worker thread starts."""
    if getattr(agent, "_desk_prepared_session_id", None) == session_id:
        return
    agent._progress = {
        "running": True,
        "status": "starting",
        "iteration": 0,
        "max_iterations": int(getattr(agent, "max_iterations", 0) or 0),
        "current_tool": None,
        "error": None,
    }
    _desk_attach_progress_events(agent, progress_event_callback)
    if stream_delta_callback is not None:
        agent.stream_delta_callback = stream_delta_callback

    def _clarify_callback(
        question: str,
        choices: Optional[List[str]] = None,
        kind: Optional[str] = None,
        artifact: Optional[Dict[str, Any]] = None,
    ) -> Any:
        result = interaction_manager.request(
            session_id=session_id,
            kind=kind or ("choice" if choices else "text"),
            question=str(question or ""),
            choices=list(choices or []),
            artifact=artifact,
            emit=progress_event_callback or (lambda payload: None),
        )
        if kind:
            return result
        action = str(result.get("action") or "")
        text = str(result.get("text") or "").strip()
        if action == "timeout":
            return text
        return text or action

    agent.clarify_callback = _clarify_callback
    agent._desk_prepared_session_id = session_id
    _desk_register_active(session_id, agent)


def _desk_parse_attachments_from_body(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = body.get("attachments")
    if not raw or not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in raw[:_DESK_MAX_ATTACHMENTS]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "file")
        mime = (str(it.get("mime") or "application/octet-stream")).strip() or "application/octet-stream"

        # Path-based attachment (Rust saves to workspace, sends path)
        fpath = it.get("path")
        if isinstance(fpath, str) and fpath:
            if os.path.isfile(fpath):
                try:
                    rawb = Path(fpath).read_bytes()
                except Exception as e:
                    log.warning("desk attachment read failed for %s: %s", fpath, e)
                    continue
                out.append({"name": name, "mime": mime.lower(), "data": rawb, "path": fpath})
                continue
            else:
                log.warning("desk attachment path not found: %s", fpath)
                continue

        # Legacy base64 data field
        raw_d = it.get("data")
        if raw_d in (None, ""):
            continue
        b64 = str(raw_d).strip()
        if not b64:
            continue
        try:
            rawb = base64.b64decode(b64, validate=False)
        except Exception as e:
            log.warning("desk attachment b64decode failed: %s", e)
            continue
        if not rawb or len(rawb) > _DESK_MAX_ATTR_BYTES:
            log.warning("desk attachment skipped: empty=%s too_big=%s (limit=%s)",
                         not rawb, len(rawb) > _DESK_MAX_ATTR_BYTES if rawb else False, _DESK_MAX_ATTR_BYTES)
            continue
        out.append({"name": name, "mime": mime.lower(), "data": rawb})
    return out


def _desk_attachment_ext(name: str) -> str:
    return Path(name).suffix.lower()


def _desk_is_presentation(name: str, mime: str) -> bool:
    ext = _desk_attachment_ext(name)
    return ext in {".ppt", ".pptx"} or mime in {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }


def _desk_pptx_sort_key(path: str) -> Tuple[int, str]:
    m = re.search(r"(\d+)", path)
    return (int(m.group(1)) if m else 0, path)


def _desk_extract_pptx_text(data: bytes) -> str:
    """Extract readable text from a PPTX using only stdlib zip/xml parsing."""
    slides: List[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = sorted(
            (
                n for n in zf.namelist()
                if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            ),
            key=_desk_pptx_sort_key,
        )
        notes = sorted(
            (
                n for n in zf.namelist()
                if n.startswith("ppt/notesSlides/notesSlide") and n.endswith(".xml")
            ),
            key=_desk_pptx_sort_key,
        )
        for label, xml_names in (("Slide", names), ("Notes", notes)):
            for idx, n in enumerate(xml_names, 1):
                try:
                    root = ET.fromstring(zf.read(n))
                except Exception:
                    continue
                parts: List[str] = []
                for el in root.iter():
                    if el.tag.endswith("}t") and el.text:
                        txt = " ".join(el.text.split())
                        if txt:
                            parts.append(txt)
                if parts:
                    slides.append(f"{label} {idx}: " + "\n".join(parts))
    return "\n\n".join(slides)


def _desk_extract_legacy_ppt_text(data: bytes) -> str:
    """Best-effort text scrape for legacy binary .ppt files.

    This is intentionally conservative: it extracts printable UTF-16LE and
    ASCII runs without executing macros or relying on Office automation.
    """
    chunks: List[str] = []
    seen: set[str] = set()

    for raw in re.findall(rb"(?:[\x20-\x7e]\x00){4,}", data):
        txt = raw.decode("utf-16le", errors="ignore").strip()
        txt = " ".join(txt.split())
        if txt and txt not in seen:
            seen.add(txt)
            chunks.append(txt)

    for raw in re.findall(rb"[\x20-\x7e]{8,}", data):
        txt = raw.decode("latin-1", errors="ignore").strip()
        txt = " ".join(txt.split())
        if txt and txt not in seen:
            seen.add(txt)
            chunks.append(txt)

    return "\n".join(chunks)


def _desk_extract_presentation_text(name: str, mime: str, data: bytes) -> str:
    ext = _desk_attachment_ext(name)
    try:
        if ext == ".pptx" or mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            return _desk_extract_pptx_text(data)
        if ext == ".ppt" or mime == "application/vnd.ms-powerpoint":
            return _desk_extract_legacy_ppt_text(data)
    except Exception as e:
        log.warning("desk presentation extraction failed for %s: %s", name, e)
    return ""


_DESK_UI_PERSIST_PREFIX = "__hermesdesk_ui__:"


def _desk_serialize_ui_persist(plain: str, atts: List[Dict[str, Any]]) -> str:
    """JSON envelope for SQLite so HermesDesk can replay image previews in chat history."""
    plain = (plain or "").strip()
    ui_attachments: List[Dict[str, str]] = []
    for p in atts:
        name = str(p.get("name") or "file")
        mime = (str(p.get("mime") or "")).lower()
        data: bytes = p.get("data") or b""
        if not data or not mime.startswith("image/"):
            continue
        ui_attachments.append(
            {
                "name": name,
                "mime": mime,
                "data": base64.b64encode(data).decode("ascii"),
            }
        )
    payload = {"text": plain, "attachments": ui_attachments}
    return _DESK_UI_PERSIST_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _desk_parse_ui_persist(content: str) -> Optional[Dict[str, Any]]:
    if not isinstance(content, str) or not content.startswith(_DESK_UI_PERSIST_PREFIX):
        return None
    try:
        parsed = json.loads(content[len(_DESK_UI_PERSIST_PREFIX) :])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _desk_agent_history_content(content: Any) -> Any:
    """Collapse desk UI persist envelope to agent-safe plain text (no base64 blobs)."""
    if not isinstance(content, str):
        return content
    parsed = _desk_parse_ui_persist(content)
    if parsed is None:
        return content
    text = (parsed.get("text") or "").strip()
    atts = parsed.get("attachments")
    n_img = len(atts) if isinstance(atts, list) else 0
    if text:
        return text
    if n_img:
        return f"[{n_img} image(s)]"
    return content


def _desk_normalize_history_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(msg, dict):
        return msg
    out = dict(msg)
    if msg.get("role") == "user":
        out["content"] = _desk_agent_history_content(msg.get("content"))
    return out


def _desk_build_user_message(
    plain: str, atts: List[Dict[str, Any]]
) -> Optional[Tuple[Union[str, List[Dict[str, Any]]], Optional[str]]]:
    """persist_user_message stores a desk UI envelope when images are attached."""
    plain = (plain or "").strip()
    if not atts:
        if not plain:
            return None
        return plain, None

    text_buf = plain if plain else "Please answer based on the attachments."
    image_parts: List[Dict[str, Any]] = []
    for p in atts:
        name = str(p.get("name") or "file")
        mime = (str(p.get("mime") or "")).lower()
        data: bytes = p.get("data") or b""
        if not data:
            continue
        if mime.startswith("image/"):
            b64d = base64.b64encode(data).decode("ascii")
            data_url = f"data:{mime};base64,{b64d}"
            image_parts.append({"type": "image_url", "image_url": {"url": data_url}})
        elif _desk_is_presentation(name, mime):
            t = _desk_extract_presentation_text(name, mime, data)
            if t:
                if len(t) > _DESK_MAX_INLINE_CHARS:
                    t = t[:_DESK_MAX_INLINE_CHARS] + "\n[truncated]"
                text_buf = f"{text_buf}\n\n--- {name} (presentation text) ---\n{t}".strip()
            else:
                text_buf = (
                    f"{text_buf}\n\n[file {name!r} type {mime!r} size {len(data)} bytes; "
                    f"presentation text could not be extracted.]"
                ).strip()
        elif mime.startswith("text/") or mime in ("application/json", "application/xml"):
            try:
                t = data.decode("utf-8")
            except UnicodeDecodeError:
                t = data.decode("utf-8", errors="replace")
            if len(t) > _DESK_MAX_INLINE_CHARS:
                t = t[:_DESK_MAX_INLINE_CHARS] + "\n[truncated]"
            text_buf = f"{text_buf}\n\n--- {name} ---\n{t}".strip()
        else:
            fpath = str(p.get("path") or "")
            if fpath:
                text_buf = (
                    f"{text_buf}\n\n[file {name!r} type {mime!r} size {len(data)} bytes "
                    f"saved to {fpath!r}; use read_file to inspect.]"
                ).strip()
            else:
                text_buf = (
                    f"{text_buf}\n\n[file {name!r} type {mime!r} size {len(data)} bytes; "
                    f"not inlined as text -- use workspace tools if needed.]"
                ).strip()

    if not image_parts:
        return text_buf, None
    user_content: List[Dict[str, Any]] = [{"type": "text", "text": text_buf}, *image_parts]
    persist = _desk_serialize_ui_persist(plain, atts)
    return user_content, persist


_DESK_COMMAND_DESCRIPTION_ZH: Dict[str, str] = {
    "new": "开始一个新会话",
    "retry": "重试上一条消息",
    "undo": "撤回上一轮对话",
    "title": "设置当前会话标题",
    "branch": "从当前会话分支继续",
    "compress": "压缩当前上下文",
    "rollback": "查看或恢复文件检查点",
    "stop": "停止正在运行的后台任务",
    "background": "把一个任务放到后台执行",
    "agents": "查看正在运行的任务",
    "queue": "把消息排队到下一轮",
    "steer": "在下一次工具调用后补充指令",
    "status": "查看当前会话状态",
    "profile": "查看当前配置档案",
    "resume": "继续之前的会话",
    "model": "切换本会话模型",
    "personality": "切换小娜的回复风格",
    "yolo": "切换高风险命令审批模式",
    "reasoning": "管理推理强度显示",
    "fast": "切换普通/快速模式",
    "voice": "切换语音相关设置",
    "curator": "管理后台技能维护",
    "reload-mcp": "重新加载 MCP 服务",
    "reload-skills": "重新扫描技能",
    "commands": "查看完整指令列表",
    "help": "显示小娜指令",
    "usage": "查看本会话用量",
    "insights": "查看使用统计",
    "debug": "生成调试报告",
}


def _desk_command_lines() -> List[str]:
    from hermes_cli.commands import COMMAND_REGISTRY

    lines: List[str] = []
    for cmd in COMMAND_REGISTRY:
        if cmd.cli_only or (cmd.gateway_only and cmd.name != "commands"):
            continue
        args = f" {cmd.args_hint}" if cmd.args_hint else ""
        desc = _DESK_COMMAND_DESCRIPTION_ZH.get(cmd.name, cmd.description)
        alias_parts = [
            f"`/{a}`"
            for a in cmd.aliases
            if a.replace("-", "_") != cmd.name.replace("-", "_")
        ]
        alias_note = f"（别名：{', '.join(alias_parts)}）" if alias_parts else ""
        lines.append(f"`/{cmd.name}{args}` - {desc}{alias_note}")
    return lines


def _desk_persist_slash_response(session_id: str, command_text: str, response_text: str) -> None:
    try:
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session(session_id=session_id, source="desktop", model="desk-command")
            db.append_message(session_id, role="user", content=command_text)
            db.append_message(session_id, role="assistant", content=response_text)
        finally:
            db.close()
    except Exception:
        log.debug("desk slash: failed to persist command response", exc_info=True)


def _desk_slash_response(message: str, session_id: str) -> Optional[Dict[str, Any]]:
    text = (message or "").strip()
    if not text.startswith("/"):
        return None
    parts = text.split()
    command = parts[0].lstrip("/").lower()
    if command not in ("help", "commands"):
        return None

    lines = ["📖 **小娜指令**", "", *_desk_command_lines()]
    if command == "commands":
        lines.insert(2, "下面是主聊天里适合学生使用的常用指令：")
        lines.insert(3, "")
    response_text = "\n".join(lines).strip()
    _desk_persist_slash_response(session_id, text, response_text)
    return {
        "ok": True,
        "proto": False,
        "session_id": session_id,
        "final_response": response_text,
        "received_chars": max(1, len(text)),
        "preview": response_text[:500] + ("..." if len(response_text) > 500 else ""),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "model": "",
    }


def current_capability_prompt_summary() -> str:
    try:
        payload = get_desk_catalog_payload_cached()
    except Exception as exc:
        log.warning("desk chat: capability summary temporarily unavailable: %s", exc)
        return "Current Kabuqina product capabilities:\n- Capability status temporarily unavailable."
    return build_capability_prompt_summary(list(payload.get("capabilities") or []))


def _desk_ephemeral_system_prompt(agent_section: Dict[str, Any]) -> Optional[str]:
    configured_prompt = (
        os.environ.get("HERMES_EPHEMERAL_SYSTEM_PROMPT")
        or str((agent_section or {}).get("system_prompt") or "")
    ).strip()
    capability_prompt = current_capability_prompt_summary().strip()
    combined = "\n\n".join(part for part in (configured_prompt, capability_prompt) if part)
    return combined or None


def _desk_chat_build_agent(session_id: str, db: Any) -> Any:
    """Construct AIAgent using the same config + credentials as the CLI."""
    from run_agent import AIAgent
    from hermes_cli.config import load_config
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from hermes_cli.tools_config import _get_platform_tools

    try:
        from tools.terminal_tool import register_task_env_overrides
    except Exception:
        register_task_env_overrides = None
    if register_task_env_overrides:
        ws = (os.environ.get("HERMES_WORKSPACE") or os.environ.get("TERMINAL_CWD") or "").strip()
        if ws:
            try:
                register_task_env_overrides(session_id, {"cwd": ws})
            except Exception:
                log.debug("desk chat: register_task_env_overrides failed", exc_info=True)

    config = load_config()
    model_cfg = config.get("model")
    default_model = ""
    config_provider: Optional[str] = None
    if isinstance(model_cfg, dict):
        default_model = str(model_cfg.get("default") or model_cfg.get("model") or "")
        config_provider = model_cfg.get("provider")
        if isinstance(config_provider, str):
            config_provider = config_provider.strip() or None
    elif isinstance(model_cfg, str) and model_cfg.strip():
        default_model = model_cfg.strip()

    agent_section = config.get("agent") or {}
    try:
        max_turns = int(agent_section.get("max_turns") or 90)
    except (TypeError, ValueError):
        max_turns = 90

    tool_list = sorted(_get_platform_tools(config, "cli"))
    if not tool_list:
        tool_list = None

    runtime = resolve_runtime_provider(requested=config_provider)
    api_key = str(runtime.get("api_key") or "").strip()
    if not api_key:
        raise ValueError(
            "No API credentials available. Configure a model key in Hermes (Settings / Keys or ~/.hermes)."
        )

    kwargs: Dict[str, Any] = {
        "model": default_model,
        "platform": "hermesdesk",
        "session_id": session_id,
        "session_db": db,
        "max_iterations": max_turns,
        "enabled_toolsets": tool_list,
        "quiet_mode": True,
        "provider": runtime.get("provider"),
        "api_mode": runtime.get("api_mode"),
        "base_url": runtime.get("base_url"),
        "api_key": runtime.get("api_key"),
        "command": runtime.get("command"),
        "args": list(runtime.get("args") or []),
        "credential_pool": runtime.get("credential_pool"),
        "ephemeral_system_prompt": _desk_ephemeral_system_prompt(agent_section),
    }
    if isinstance(model_cfg, dict):
        if model_cfg.get("reasoning_config") is not None:
            kwargs["reasoning_config"] = model_cfg.get("reasoning_config")
        if model_cfg.get("max_tokens") is not None:
            try:
                kwargs["max_tokens"] = int(model_cfg.get("max_tokens"))
            except (TypeError, ValueError):
                pass

    return AIAgent(**kwargs)


def _desk_chat_run_in_thread(
    agent: Any,
    user_message: Any,
    history: List[Dict[str, Any]],
    session_id: str,
    persist_user_message: Optional[str] = None,
    stream_delta_callback: Optional[Any] = None,
    progress_event_callback: Optional[Any] = None,
) -> Dict[str, Any]:
    if getattr(agent, "_desk_prepared_session_id", None) != session_id:
        _desk_prepare_active_agent(
            session_id,
            agent,
            stream_delta_callback=stream_delta_callback,
            progress_event_callback=progress_event_callback,
        )
    try:
        if persist_user_message is not None:
            result = agent.run_conversation(
                user_message=user_message,
                conversation_history=history,
                task_id=session_id,
                persist_user_message=persist_user_message,
            )
        else:
            result = agent.run_conversation(
                user_message=user_message,
                conversation_history=history,
                task_id=session_id,
            )
        return {
            "result": result,
            "prompt_tokens": int(getattr(agent, "session_prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(agent, "session_completion_tokens", 0) or 0),
        }
    finally:
        _desk_unregister_active(session_id)


def _desk_strip_thinking_tags(text: str) -> str:
    if not text or "<think>" not in text:
        return text
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _desk_content_to_text(content: Any) -> str:
    """Normalize assistant content (str, list, or OpenAI-compat dict shapes) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        t = content.strip()
        if not t:
            return ""
        if t.startswith(("[", "{")):
            try:
                parsed = json.loads(t)
                if isinstance(parsed, (list, dict)):
                    return _desk_content_to_text(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return _desk_strip_thinking_tags(t)
    if isinstance(content, (int, float, bool)):
        return str(content).strip()
    if isinstance(content, dict):
        inner = content.get("text")
        if inner is None:
            inner = content.get("content")
        if isinstance(inner, (dict, list)):
            return _desk_content_to_text(inner)
        if inner is not None:
            return _desk_strip_thinking_tags(str(inner).strip())
        return _desk_strip_thinking_tags(str(content).strip())
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict):
                pt = str(part.get("type") or "")
                if pt in ("text", "output_text") or "text" in part:
                    parts.append(str(part.get("text") or ""))
                elif isinstance(part.get("content"), str) and part.get("content", "").strip():
                    parts.append(str(part.get("content")))
            elif isinstance(part, str):
                parts.append(part)
        return _desk_strip_thinking_tags("\n".join(p for p in parts if p).strip())
    return _desk_strip_thinking_tags(str(content).strip())


def _desk_text_from_assistant_messages(messages: List[Any]) -> str:
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        t = _desk_content_to_text(msg.get("content"))
        if t:
            return t
    return ""


def _desk_extract_reply_text(conv_result: Any) -> str:
    """Best-effort assistant text from run_conversation return value."""
    if not isinstance(conv_result, dict):
        return str(conv_result).strip() if conv_result is not None else ""

    fr = conv_result.get("final_response")
    if isinstance(fr, str) and fr.strip():
        return _desk_strip_thinking_tags(fr.strip())
    if fr is not None and not isinstance(fr, str):
        s = str(fr).strip()
        if s:
            return _desk_strip_thinking_tags(s)

    messages: List[Dict[str, Any]] = conv_result.get("messages") or []
    t = _desk_text_from_assistant_messages(messages)
    if t:
        return t
    if conv_result.get("failed") and conv_result.get("error"):
        return str(conv_result.get("error")).strip()
    return ""
