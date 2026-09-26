extends Node2D

var manifest: Dictionary
var textures: Dictionary = {}
var sprites: Dictionary = {}
var clip := "idle"
var frame_index := 0
var elapsed := 0.0
var playing := true
var loop_attack := false
var show_weapon := true
var show_fx := true
var speed := 1.0
var hit_count := 0
var status: Label
var root_position := Vector2(420, 530)
const DISPLAY_SCALE := 3.0

func _ready() -> void:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://assets/manifest.json"))
	if not parsed is Dictionary:
		push_error("Missing or invalid animation manifest. Run the Blender exporter first.")
		get_tree().quit(1)
		return
	manifest = parsed
	for clip_data in manifest.clips.values():
		for frame in clip_data.frames:
			for layer in manifest.layers:
				var path: String = "res://assets/" + str(frame.paths[layer])
				var texture = load(path) as Texture2D
				if texture == null:
					push_error("Missing animation layer: " + path)
					get_tree().quit(1)
					return
				textures[path] = texture
	for layer in manifest.layers:
		var sprite := Sprite2D.new()
		sprite.name = layer
		sprite.centered = false
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		sprite.scale = Vector2.ONE * DISPLAY_SCALE
		sprite.position = root_position - Vector2(manifest.root_px[0], manifest.root_px[1]) * DISPLAY_SCALE
		add_child(sprite)
		sprites[layer] = sprite
	var title := Label.new()
	var total_ms := 0
	for frame in manifest.clips.slash.frames:
		total_ms += int(frame.duration_ms)
	title.text = "HERO / PIXEL SLASH     %d POSES · %d ms" % [manifest.clips.slash.frames.size(), total_ms]
	title.position = Vector2(28, 20)
	title.add_theme_font_size_override("font_size", 22)
	add_child(title)
	var labels := ["Attack", "Pause / Play", "Previous", "Next", "Loop", "Sword", "Effect", "Speed"]
	var callbacks := [_attack, _pause, _step.bind(-1), _step.bind(1), _loop, _weapon, _effect, _speed]
	for i in range(labels.size()):
		var button := Button.new()
		button.text = labels[i]
		button.position = Vector2(26 + i * 114, 565)
		button.size = Vector2(108, 35)
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(callbacks[i])
		add_child(button)
	status = Label.new()
	status.position = Vector2(28, 612)
	status.add_theme_font_size_override("font_size", 15)
	add_child(status)
	_apply_frame()
	if "--verify" in OS.get_cmdline_user_args():
		_verify()

func _draw() -> void:
	draw_rect(Rect2(0, 0, 960, 660), Color("#0e1420"))
	draw_rect(Rect2(20, 66, 920, 476), Color("#1b2330"))
	draw_line(Vector2(24, 530), Vector2(936, 530), Color("#485568"), 1)
	for x in range(36, 930, 24):
		draw_line(Vector2(x, 530), Vector2(x, 534), Color("#485568"), 1)

func _process(delta: float) -> void:
	if playing:
		_advance(delta * speed)

func _advance(seconds: float) -> void:
	elapsed += seconds
	while elapsed + 0.0000001 >= float(manifest.clips[clip].frames[frame_index].duration_ms) / 1000.0:
		elapsed -= float(manifest.clips[clip].frames[frame_index].duration_ms) / 1000.0
		frame_index += 1
		if frame_index >= manifest.clips[clip].frames.size():
			if clip == "slash" and not loop_attack:
				clip = str(manifest.clips[clip].next)
			frame_index = 0
		if manifest.clips[clip].frames[frame_index].event == "hit":
			hit_count += 1
		_apply_frame()

func _apply_frame() -> void:
	var frame: Dictionary = manifest.clips[clip].frames[frame_index]
	for layer in manifest.layers:
		sprites[layer].texture = textures["res://assets/" + str(frame.paths[layer])]
		sprites[layer].visible = (layer != "weapon" or show_weapon) and (layer != "fx" or show_fx)
	status.text = "%s  %02d/%02d  |  %d ms  |  %.1fx  |  loop %s  sword %s  fx %s  |  SPACE attack / arrows step" % [clip.to_upper(), frame_index + 1, manifest.clips[clip].frames.size(), frame.duration_ms, speed, loop_attack, show_weapon, show_fx]

func _attack() -> void:
	clip = "slash"
	frame_index = 0
	elapsed = 0
	playing = true
	_apply_frame()

func _pause() -> void:
	playing = not playing

func _step(direction: int) -> void:
	playing = false
	if clip != "slash":
		clip = "slash"
		frame_index = 0
	else:
		frame_index = posmod(frame_index + direction, manifest.clips[clip].frames.size())
	elapsed = 0
	_apply_frame()

func _loop() -> void:
	loop_attack = not loop_attack
	if loop_attack:
		_attack()
	_apply_frame()

func _weapon() -> void:
	show_weapon = not show_weapon
	_apply_frame()

func _effect() -> void:
	show_fx = not show_fx
	_apply_frame()

func _speed() -> void:
	speed = 0.5 if speed == 1.0 else (1.5 if speed == 0.5 else 1.0)
	_apply_frame()

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_SPACE: _attack()
			KEY_LEFT: _step(-1)
			KEY_RIGHT: _step(1)
			KEY_P: _pause()
			KEY_L: _loop()
			KEY_W: _weapon()
			KEY_F: _effect()

func _verify() -> void:
	set_process(false)
	var errors: Array[String] = []
	_attack()
	_advance(0.084)
	if frame_index != 0: errors.append("First 85 ms hold failed")
	_advance(0.002)
	if frame_index != 1: errors.append("Frame timing boundary failed")
	_advance(0.674)
	if clip != "idle" or frame_index != 0: errors.append("Attack did not return to idle after 760 ms")
	if hit_count != 1: errors.append("Hit event must occur once")
	_attack()
	_advance(0.4)
	_attack()
	if frame_index != 0 or elapsed != 0: errors.append("Replay did not reset playback")
	_weapon()
	if sprites.weapon.visible or not sprites.hands.visible: errors.append("Equipment visibility is coupled to hands")
	_effect()
	if sprites.fx.visible or not sprites.body.visible: errors.append("Effect visibility is coupled to body")
	_step(1)
	if playing or frame_index != 1: errors.append("Frame stepping failed")
	loop_attack = true
	_attack()
	_advance(0.760)
	if clip != "slash" or frame_index != 0: errors.append("Loop transition failed")
	var result := {"errors": errors, "loaded_layer_textures": textures.size(), "checked": ["timing", "return_to_idle", "hit_event", "replay", "layer_toggles", "step", "loop"]}
	var path := ProjectSettings.globalize_path("res://").path_join("../preview/godot_checks.json")
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "\t"))
	print(JSON.stringify(result))
	get_tree().quit(0 if errors.is_empty() else 1)
