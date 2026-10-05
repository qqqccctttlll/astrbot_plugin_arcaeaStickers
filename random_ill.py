import os
import random
import re
import asyncio

from astrbot.api.message_components import Image, Node, Nodes

from . import maybe_compress, schedule_temp_cleanup

async def handle_random_pick(plugin, event):
	message_str = event.message_str.strip()
	if "随插" in message_str:
		after_kw = message_str[message_str.index("随插") + 2:].strip()
		num_match = re.search(r'^(\d+)', after_kw)
		num = int(num_match.group(1)) if num_match else 1
		num = max(1, min(num, 5))
	elif message_str == "sc":
		num = 1
	elif re.match(r'^sc\d+$', message_str):
		num = int(message_str[2:])
		num = max(1, min(num, 5))
	else:
		return

	if not os.path.exists(plugin.illustration_dir):
		yield event.plain_result("图库为空或不存在")
		return
	images = [
		f for f in os.listdir(plugin.illustration_dir)
		if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
	]
	if not images:
		yield event.plain_result("图库为空或不存在")
		return

	temp_files = []
	try:
		if num == 1:
			chosen = random.choice(images)
			img_path = os.path.join(plugin.illustration_dir, chosen)
			final_path = await asyncio.to_thread(maybe_compress, plugin, img_path, temp_files)
			yield event.chain_result([Image.fromFileSystem(final_path)])
		else:
			selected = random.sample(images, min(num, len(images)))
			bot_name = event.get_sender_name() or "Etoile"
			self_id = event.get_self_id() or "0"
			nodes = []
			for img_name in selected:
				img_path = os.path.join(plugin.illustration_dir, img_name)
				final_path = await asyncio.to_thread(maybe_compress, plugin, img_path, temp_files)
				nodes.append(Node(
					content=[Image.fromFileSystem(final_path)],
					name=bot_name,
					uin=self_id,
				))
			yield event.chain_result([Nodes(nodes)])
	finally:
		schedule_temp_cleanup(temp_files)