from astrbot.api import logger

from . import get_config

def save_config(plugin) -> tuple[bool, str | None]:
	try:
		plugin.plugin_config.save_config()
		return True, None
	except Exception as e:
		return False, str(e)

def coerce_value(raw, old):
	if isinstance(old, bool):
		low = raw.strip().lower()
		if low in ("true", "1", "yes", "on"):
			return True, True
		if low in ("false", "0", "no", "off"):
			return False, True
		return None, False

	if isinstance(old, int):
		try:
			return int(raw), True
		except ValueError:
			return None, False

	if isinstance(old, float):
		try:
			return float(raw), True
		except ValueError:
			return None, False

	if isinstance(old, str):
		return raw, True

	if isinstance(old, list):
		return [s.strip() for s in raw.split(",") if s.strip()], True

	return None, False

def is_admin(event) -> bool:
	try:
		return bool(event.is_admin())
	except Exception as e:
		logger.error(f"检查失败: {e}")
		return False

def _config_list(plugin) -> str:
	lines = ["配置列表："]
	for k in sorted(plugin.plugin_config.keys()):
		v = plugin.plugin_config[k]
		lines.append(f"{k}({type(v).__name__})")
	return "\n".join(lines)

async def handle_arc_set(plugin, event, parts):
	if not is_admin(event):
		yield event.plain_result("仅bot管理员可用")
		return

	if len(parts) < 3:
		yield event.plain_result(_config_list(plugin))
		return

	key = parts[2].strip()

	if key not in plugin.plugin_config:
		yield event.plain_result(
			f'错误的"{key}"出现在"set"\n{_config_list(plugin)}'
		)
		return

	if len(parts) < 4:
		yield event.plain_result(
			f'错误的""出现在"{key}"\n{_config_list(plugin)}'
		)
		return

	raw = parts[3]
	old = plugin.plugin_config[key]
	parsed, ok = coerce_value(raw, old)

	if not ok:
		yield event.plain_result(
			f'错误的"{raw}"出现在"{key}"\n{_config_list(plugin)}'
		)
		return

	plugin.plugin_config[key] = parsed
	ok, save_err = save_config(plugin)
	if not ok:
		plugin.plugin_config[key] = old
		yield event.plain_result(f"保存失败: {save_err}")
		return

	yield event.plain_result(f"已更新: {key} = {parsed!r}")