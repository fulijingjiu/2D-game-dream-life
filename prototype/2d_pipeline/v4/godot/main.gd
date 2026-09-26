extends Node2D

var manifest: Dictionary
var cache: Dictionary = {}
var actor: Sprite2D
var status: Label
var clip := "idle"
var frame_index := 0
var elapsed := 0.0
var playing := true
var looping := false
var speed := 1.0
var hits := 0

func _ready() -> void:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string("res://assets/manifest.json"))
	if not parsed is Dictionary:
		push_error("Generate the frame manifest first.")
		get_tree().quit(1)
		return
	manifest = parsed
	for animation in manifest.clips.values():
		for frame in animation.frames:
			var texture = load("res://assets/" + str(frame.path)) as Texture2D
			if texture == null:
				push_error("Missing frame: " + str(frame.path))
				get_tree().quit(1)
				return
			cache[frame.path] = texture
	actor = Sprite2D.new()
	actor.centered = false
	actor.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	actor.scale = Vector2(2,2)
	actor.position = Vector2(420,560) - Vector2(manifest.root_px[0],manifest.root_px[1]) * 2
	add_child(actor)
	var title := Label.new()
	title.text = "PIXEL HERO / COMPLETE DRAWN FRAMES"
	title.position = Vector2(28,22)
	title.add_theme_font_size_override("font_size",24)
	add_child(title)
	var labels := ["Attack", "Pause / Play", "Previous", "Next", "Loop", "Speed"]
	var actions := [_attack, _pause, _step.bind(-1), _step.bind(1), _loop, _speed]
	for i in range(labels.size()):
		var button := Button.new()
		button.text = labels[i]
		button.position = Vector2(28+i*150,600)
		button.size = Vector2(142,38)
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(actions[i])
		add_child(button)
	status = Label.new()
	status.position = Vector2(28,664)
	status.add_theme_font_size_override("font_size",16)
	add_child(status)
	_apply_frame()
	if "--verify" in OS.get_cmdline_user_args(): _verify()

func _draw() -> void:
	draw_rect(Rect2(0,0,960,720),Color("#0e1420"))
	draw_rect(Rect2(20,66,920,514),Color("#18212f"))
	draw_line(Vector2(24,560),Vector2(936,560),Color("#485568"),1)

func _process(delta: float) -> void:
	if playing: _advance(delta*speed)

func _advance(seconds: float) -> void:
	elapsed += seconds
	while elapsed+0.0000001 >= float(manifest.clips[clip].frames[frame_index].duration_ms)/1000.0:
		elapsed -= float(manifest.clips[clip].frames[frame_index].duration_ms)/1000.0
		frame_index += 1
		if frame_index >= manifest.clips[clip].frames.size():
			if clip == "slash" and not looping: clip = str(manifest.clips[clip].next)
			frame_index = 0
		if manifest.clips[clip].frames[frame_index].event == "hit": hits += 1
		_apply_frame()

func _apply_frame() -> void:
	var frame: Dictionary = manifest.clips[clip].frames[frame_index]
	actor.texture = cache[frame.path]
	status.text = "%s  %02d/%02d  |  %d ms  |  %.1fx  |  loop %s  |  SPACE attack / arrows step" % [clip.to_upper(),frame_index+1,manifest.clips[clip].frames.size(),frame.duration_ms,speed,looping]

func _attack() -> void:
	clip = "slash"
	frame_index = 0
	elapsed = 0
	playing = true
	_apply_frame()

func _pause() -> void: playing = not playing

func _step(direction: int) -> void:
	playing = false
	if clip != "slash":
		clip = "slash"
		frame_index = 0
	else: frame_index = posmod(frame_index+direction,manifest.clips[clip].frames.size())
	elapsed = 0
	_apply_frame()

func _loop() -> void:
	looping = not looping
	if looping: _attack()
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

func _verify() -> void:
	set_process(false)
	var errors: Array[String] = []
	var duration := 0.0
	for frame in manifest.clips.slash.frames: duration += float(frame.duration_ms)/1000.0
	_attack()
	_advance(0.069)
	if frame_index != 0: errors.append("Initial hold failed")
	_advance(0.002)
	if frame_index != 1: errors.append("Timing boundary failed")
	_advance(duration-0.071)
	if clip != "idle": errors.append("Did not return to idle")
	if hits != 1: errors.append("Expected one hit event")
	_attack()
	_advance(0.2)
	_attack()
	if frame_index != 0 or elapsed != 0: errors.append("Replay reset failed")
	_step(1)
	if playing or frame_index != 1: errors.append("Step failed")
	looping = true
	_attack()
	_advance(duration)
	if clip != "slash" or frame_index != 0: errors.append("Loop failed")
	var result := {"errors":errors,"loaded_textures":cache.size(),"duration_ms":roundi(duration*1000),"checks":["timing","idle_transition","hit_event","replay","step","loop"]}
	var file := FileAccess.open(ProjectSettings.globalize_path("res://").path_join("../preview/2026-09-26-播放检查.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"\t"))
	print(JSON.stringify(result))
	get_tree().quit(0 if errors.is_empty() else 1)
