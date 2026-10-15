extends Node2D

## M1 状态机骨架。无资源。
## 形制锁定重导（#8）之前，idle/run/jump/fall/land/dodge/slash 全部用色块。
## 不读取 godot/assets 里待删的弯刃 idle、slash。

signal tut_run_started
signal tut_jump_started
signal tut_fall_started
signal tut_landed
signal tut_slash_started
signal tut_dodge_ended
signal state_changed(previous: String, current: String)

# 形制板粉十字。只是画板像素，不是玩家根点，也不是 manifest.root_px。
const WEAPON_GRIP_SHEET_PX := Vector2(873, 315)
const STARTER_MELEE_ID := "starter_melee"
const RELIC_SWORD_ID := "relic_sword"

const RUN_SPEED := 180.0
const AIR_SPEED := 150.0
const JUMP_VELOCITY := -720.0
const GRAVITY := 1000.0
const DODGE_SPEED := 240.0

# 占位时长。不是设计锁。重导之前不读旧 manifest 的 duration_ms。
const PLACEHOLDER_SEC := {
	"dodge": 0.24,
	"land": 0.18,
	"slash": 0.40,
}

const PLACEHOLDER_COLOR := {
	"idle": Color("8a93a3"),
	"run": Color("3d7ec9"),
	"jump": Color("3c9a6a"),
	"fall": Color("7a5cc4"),
	"land": Color("c47a3c"),
	"dodge": Color("c9b23d"),
	"slash": Color("c45c5c"),
}

@export var floor_y := 560.0

var state := "idle"
var state_time := 0.0
var velocity := Vector2.ZERO
var facing := 1
var on_floor := true
var floor_enabled := true
var contract_mode := false
var dodge_from_air := false
var dodge_ended_sent := false

var _plate: ColorRect
var _plate_label: Label
var _body: ColorRect
var _nose: ColorRect

func _ready() -> void:
	_install_input_map()
	_build_visuals()
	position.y = floor_y
	on_floor = true
	_sync_visual()

func _physics_process(delta: float) -> void:
	if contract_mode:
		return
	_simulate(delta, _intent_from_input())

func state_name() -> String:
	return state

func has_real_clip(_clip: String) -> bool:
	# 弯刃 idle/slash 不作样本。#8 重导之前一律没有可播帧。
	return false

func clip_duration(clip: String) -> float:
	return float(PLACEHOLDER_SEC.get(clip, 0.2))

func weapon_note() -> String:
	return "%s != %s; WEAPON_GRIP_SHEET_PX=(%d,%d) sheet-only, not gameplay root" % [
		STARTER_MELEE_ID,
		RELIC_SWORD_ID,
		int(WEAPON_GRIP_SHEET_PX.x),
		int(WEAPON_GRIP_SHEET_PX.y),
	]

func debug_reset() -> void:
	contract_mode = true
	state = "idle"
	state_time = 0.0
	velocity = Vector2.ZERO
	facing = 1
	floor_enabled = true
	on_floor = true
	dodge_from_air = false
	dodge_ended_sent = false
	position = Vector2(180, floor_y)
	_sync_visual()

func debug_step(delta: float, move: float, jump: bool, dodge: bool, attack: bool) -> void:
	contract_mode = true
	_simulate(delta, {
		"move": move,
		"jump": jump,
		"dodge": dodge,
		"attack": attack,
	})

func _intent_from_input() -> Dictionary:
	return {
		"move": Input.get_axis("move_left", "move_right"),
		"jump": Input.is_action_just_pressed("jump"),
		"dodge": Input.is_action_just_pressed("dodge"),
		"attack": Input.is_action_just_pressed("attack"),
	}

func _simulate(delta: float, intent: Dictionary) -> void:
	match state:
		"idle", "run":
			_tick_ground(delta, intent)
		"jump":
			_tick_jump(delta, intent)
		"fall":
			_tick_fall(delta, intent)
		"land":
			_tick_land(delta, intent)
		"dodge":
			_tick_dodge(delta, intent)
		"slash":
			_tick_slash(delta, intent)
	_advance_frames(delta)

func _tick_ground(delta: float, intent: Dictionary) -> void:
	var move := float(intent["move"])
	if absf(move) > 0.01:
		facing = 1 if move > 0.0 else -1
	# 同一帧：闪 > 跳 > 攻击 > 跑。避免跳和闪挤在同一帧变成从 jump 闪。
	if bool(intent["dodge"]):
		_enter("dodge")
		return
	if bool(intent["jump"]):
		_enter("jump")
		return
	if state == "idle" and bool(intent["attack"]):
		_enter("slash")
		return
	if absf(move) > 0.01:
		velocity.x = move * RUN_SPEED
		velocity.y = 0.0
		if state != "run":
			_enter("run")
	else:
		velocity.x = 0.0
		velocity.y = 0.0
		if state != "idle":
			_enter("idle")
	_integrate(delta)
	if (state == "idle" or state == "run") and not on_floor:
		_enter("fall")

func _tick_jump(delta: float, intent: Dictionary) -> void:
	# jump 中不接受 dodge。
	var move := float(intent["move"])
	velocity.y += GRAVITY * delta
	if absf(move) > 0.01:
		facing = 1 if move > 0.0 else -1
		velocity.x = move * AIR_SPEED
	state_time += delta
	_integrate(delta)
	# 重导之前没有 jump 帧，离地后只在升顶进入 fall。
	if velocity.y >= 0.0:
		_enter("fall")

func _tick_fall(delta: float, intent: Dictionary) -> void:
	var move := float(intent["move"])
	velocity.y += GRAVITY * delta
	if absf(move) > 0.01:
		facing = 1 if move > 0.0 else -1
		velocity.x = move * AIR_SPEED
	_integrate(delta)
	state_time += delta
	# 落地优先于本帧才按下的闪。
	if on_floor:
		_enter("land")
		return
	if bool(intent["dodge"]):
		_enter("dodge")

func _tick_land(delta: float, intent: Dictionary) -> void:
	velocity = Vector2.ZERO
	_integrate(delta)
	state_time += delta
	if state_time < clip_duration("land"):
		return
	if absf(float(intent["move"])) > 0.01:
		_enter("run")
	else:
		_enter("idle")

func _tick_dodge(delta: float, intent: Dictionary) -> void:
	var move := float(intent["move"])
	velocity.x = float(facing) * DODGE_SPEED
	if dodge_from_air:
		velocity.y += GRAVITY * delta
	else:
		velocity.y = 0.0
	_integrate(delta)
	state_time += delta
	if not dodge_from_air and not on_floor:
		_emit_dodge_ended()
		_enter("fall")
		return
	if state_time < clip_duration("dodge"):
		return
	_emit_dodge_ended()
	if not on_floor:
		_enter("fall")
	elif absf(move) > 0.01:
		facing = 1 if move > 0.0 else -1
		_enter("run")
	else:
		_enter("idle")

func _tick_slash(delta: float, _intent: Dictionary) -> void:
	velocity.x = 0.0
	velocity.y = 0.0
	_integrate(delta)
	state_time += delta
	if state_time >= clip_duration("slash"):
		_enter("idle")

func _enter(next: String) -> void:
	if state == next:
		return
	var previous := state
	state = next
	state_time = 0.0
	match next:
		"idle":
			velocity.x = 0.0
		"run":
			tut_run_started.emit()
		"jump":
			velocity.y = JUMP_VELOCITY
			tut_jump_started.emit()
		"fall":
			tut_fall_started.emit()
		"land":
			velocity.x = 0.0
			velocity.y = 0.0
			tut_landed.emit()
		"slash":
			velocity.x = 0.0
			tut_slash_started.emit()
		"dodge":
			dodge_from_air = not on_floor
			dodge_ended_sent = false
	state_changed.emit(previous, next)

func _emit_dodge_ended() -> void:
	if dodge_ended_sent:
		return
	dodge_ended_sent = true
	tut_dodge_ended.emit()

func _integrate(delta: float) -> void:
	position.x += velocity.x * delta
	position.y += velocity.y * delta
	if floor_enabled and position.y >= floor_y:
		position.y = floor_y
		if velocity.y > 0.0:
			velocity.y = 0.0
		on_floor = true
	else:
		on_floor = false

func _advance_frames(_delta: float) -> void:
	_sync_visual()

func _sync_visual() -> void:
	if _body == null:
		return
	var tint: Color = PLACEHOLDER_COLOR.get(state, Color.WHITE)
	_body.color = tint
	_nose.color = tint.darkened(0.35)
	_plate.color = tint
	_plate_label.text = state
	_nose.position = Vector2(16.0 if facing > 0 else -24.0, -36.0)

func _build_visuals() -> void:
	_body = ColorRect.new()
	_body.size = Vector2(36, 64)
	_body.position = Vector2(-18, -64)
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_body.z_index = 1
	add_child(_body)
	_nose = ColorRect.new()
	_nose.size = Vector2(8, 8)
	_nose.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_nose.z_index = 2
	add_child(_nose)
	_plate = ColorRect.new()
	_plate.size = Vector2(92, 18)
	_plate.position = Vector2(-46, -88)
	_plate.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_plate.z_index = 3
	add_child(_plate)
	_plate_label = Label.new()
	_plate_label.position = Vector2(-42, -89)
	_plate_label.add_theme_font_size_override("font_size", 14)
	_plate_label.add_theme_color_override("font_color", Color("111111"))
	_plate_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_plate_label.z_index = 4
	add_child(_plate_label)

func _install_input_map() -> void:
	_bind_keys("move_left", [KEY_A, KEY_LEFT])
	_bind_keys("move_right", [KEY_D, KEY_RIGHT])
	_bind_keys("move_up", [KEY_W, KEY_UP])
	_bind_keys("move_down", [KEY_S, KEY_DOWN])
	_bind_keys("jump", [KEY_SPACE, KEY_K])
	_bind_keys("dodge", [KEY_SHIFT, KEY_L])
	_bind_keys("attack", [KEY_J, KEY_Z])

func _bind_keys(action: String, keys: Array) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action, 0.5)
	for keycode in keys:
		if _has_physical_key(action, int(keycode)):
			continue
		var event := InputEventKey.new()
		event.physical_keycode = keycode
		InputMap.action_add_event(action, event)

func _has_physical_key(action: String, keycode: int) -> bool:
	for event in InputMap.action_get_events(action):
		if event is InputEventKey and int(event.physical_keycode) == keycode:
			return true
	return false
