"""
NeuroPaw — v6_stage2.py
Этап 2: подписи сервоприводов «07 / MG996R» на выносках (всегда к камере, светлый текст
на тёмной подложке), подписи плат и CAN, легенда, слой «Servo_map» (оболочка полупрозрачная,
сервы окрашены по управляющей плате). Обычный слой ViewLayer остаётся как был (без подписей).
Запуск после build_v6.py:
blender --background robodog_v6.blend --python scripts/v6_stage2.py   (сохраняет robodog_v6.blend)
"""
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from v6lib import checks, rig  # noqa: E402
from v6lib.geom import MM, Mesh, mat  # noqa: E402
from v6lib.layout import BASE, LEGS, N, P, SERVOS, stand_pose  # noqa: E402

checks.relink()
ARM = rig.ARM
sc = bpy.context.scene
BCOL = {"ESP32_Body": (0.0, 0.78, 0.85), "ESP32_Senses": (0.62, 0.25, 1.0),
        "ESP32_Brain": (0.1, 0.85, 0.4), "ESP32_Comms": (0.25, 0.4, 1.0)}
BOARD_NAME = {"ESP32_Body": "Тело · ESP32 DevKit", "ESP32_Senses": "Органы чувств · S3-DevKitC-1",
              "ESP32_Brain": "Мозг · S3-CAM", "ESP32_Comms": "Связь · C3 SuperMini"}
TEXT_SIZE = 7.5          # мм


def _clean():
    old = bpy.data.collections.get("Labels")
    if old:
        for o in list(old.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        for c in list(old.children_recursive):
            bpy.data.collections.remove(c)
        bpy.data.collections.remove(old)
    for n in ("Cam_servo_map",):
        if n in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
    for vl in list(sc.view_layers):
        if vl.name == "Servo_map":
            sc.view_layers.remove(vl)


def _collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or sc.collection).children.link(c)
    return c


def _emit(name, rgb, s=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = s
    m.diffuse_color = (*rgb, 1)
    return m


def _font():
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return bpy.data.fonts.load(p, check_existing=True)
    return None


FONT = None
M_TEXT = M_BACK = M_LEAD = None


def label(name, text, target_mm, anchor_mm, bone, cam, coll, rgb):
    """Выноска от target к anchor; в anchor — пустышка с поворотом камеры, текст и подложка."""
    t, a = Vector(target_mm), Vector(anchor_mm)
    d = a - t
    m = Mesh().mat(M_LEAD).cyl(tuple((t + a) / 2), tuple(d.normalized()), 0.5, d.length, 8)
    m.mat(_emit(f"lbl_dot_{name}", rgb, 1.5)).sphere(tuple(t), 2.2)
    rig.make(f"{name}_leader", m, coll, bone, origin=tuple(t))
    e = bpy.data.objects.new(f"{name}_anchor", None)
    e.empty_display_size = 0.004
    coll.objects.link(e)
    rig.attach(e, bone, a)
    c = e.constraints.new('COPY_ROTATION')         # «рекламный щит»: параллельно кадру, текст прямо
    c.target = cam
    cu = bpy.data.curves.new(f"{name}_text", 'FONT')
    cu.body, cu.size = text, TEXT_SIZE * MM
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    if FONT:
        cu.font = FONT
    to = bpy.data.objects.new(f"{name}_text", cu)
    to.data.materials.append(M_TEXT)
    coll.objects.link(to)
    to.parent = e
    to.location = (0, 0, 0.0004)
    bpy.context.view_layer.update()
    w, h = to.dimensions.x + 4 * MM, max(to.dimensions.y, TEXT_SIZE * 0.75 * MM) + 3 * MM
    bk = Mesh().mat(M_BACK).box((-w / 2 / MM, w / 2 / MM), (-h / 2 / MM, h / 2 / MM), (-0.3, 0))
    bk.mat(_emit(f"lbl_bar_{name}", rgb, 1.5)).box((-w / 2 / MM - 1.6, -w / 2 / MM), (-h / 2 / MM, h / 2 / MM), (-0.3, 0.05))
    me = bpy.data.meshes.new(f"{name}_back")
    bk.bm.transform(__import__("mathutils").Matrix.Scale(MM, 4))
    bk.bm.to_mesh(me)
    bk.bm.free()
    for mm in bk.mats:
        me.materials.append(mm)
    bo = bpy.data.objects.new(f"{name}_back", me)
    coll.objects.link(bo)
    bo.parent = e
    return e


def servo_anchor(no, c):
    """Где ставить подпись сервы (мм): наружу от тела и вверх, без наложений."""
    for leg, (xs, ys, n0) in LEGS.items():
        if no == n0:
            return c + Vector((xs * 15, ys * 62, 78))
        if no == n0 + 1:
            return c + Vector((xs * 10, ys * 70, 34))
        if no == n0 + 2:
            return c + Vector((xs * 20, ys * 72, -6))
    return c + Vector({13: (5, 0, 95), 14: (-12, 0, 92), 15: (-38, 0, 55), 16: (-10, -88, 0),
                       17: (-30, 80, -8), 18: (62, 0, -22), 19: (0, 52, 42), 20: (0, -52, 42)}[no])


def center(o):
    return sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices) / MM


def recolor_servos():
    """Копии материалов корпуса по плате: цвет = mix(тип, плата, атрибут слоя servo_map)."""
    cache = {}
    for o in bpy.data.objects:
        if "servo_no" not in o:
            continue
        base = o.material_slots[0].material
        key = (base.name.split("@")[0], o["board"])
        if key not in cache:
            m = base.copy()
            m.name = f"{key[0]}@{o['board']}"
            nt = m.node_tree
            b = nt.nodes["Principled BSDF"]
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_type, at.attribute_name = 'VIEW_LAYER', "servo_map"
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = 'RGBA'
            mx.inputs[6].default_value = b.inputs["Base Color"].default_value[:]
            mx.inputs[7].default_value = (*BCOL[o["board"]], 1)
            nt.links.new(at.outputs["Fac"], mx.inputs[0])
            nt.links.new(mx.outputs[2], b.inputs["Base Color"])
            em = nt.nodes.new("ShaderNodeMath")
            em.operation = 'MULTIPLY'
            em.inputs[1].default_value = 0.6
            nt.links.new(at.outputs["Fac"], em.inputs[0])
            b.inputs["Emission Color"].default_value = (*BCOL[o["board"]], 1)
            nt.links.new(em.outputs[0], b.inputs["Emission Strength"])
            cache[key] = m
        o.material_slots[0].link = 'OBJECT'
        o.material_slots[0].material = cache[key]


def ghost_shell():
    """Оболочка: альфа = 1 − 0.85 · servo_map (полупрозрачна только в слое Servo_map)."""
    cache = {}
    for o in bpy.data.collections["Shell"].all_objects:
        for s in o.material_slots:
            base = s.material
            if base is None or base.name.endswith("@ghost"):
                continue
            if base.name not in cache:
                m = base.copy()
                m.name = f"{base.name}@ghost"
                nt = m.node_tree
                b = nt.nodes["Principled BSDF"]
                at = nt.nodes.new("ShaderNodeAttribute")
                at.attribute_type, at.attribute_name = 'VIEW_LAYER', "servo_map"
                ma = nt.nodes.new("ShaderNodeMath")
                ma.operation = 'MULTIPLY_ADD'
                ma.inputs[1].default_value, ma.inputs[2].default_value = -0.86, 1.0
                nt.links.new(at.outputs["Fac"], ma.inputs[0])
                nt.links.new(ma.outputs[0], b.inputs["Alpha"])
                m.surface_render_method = 'DITHERED'
                cache[base.name] = m
            s.link = 'OBJECT'
            s.material = cache[base.name]


def legend(cam, coll):
    """Легенда — дочерняя камере (левый верхний угол кадра); масштаб = ortho_scale."""
    root = bpy.data.objects.new("Legend", None)
    coll.objects.link(root)
    root.parent = cam
    counts = {}
    for s in SERVOS:
        counts[s[3]] = counts.get(s[3], 0) + 1
    by_board = {}
    for s in SERVOS:
        by_board.setdefault(s[5], []).append(s[0])
    lines = [("Карта сервоприводов NeuroPaw v6 · цвет = управляющая плата", None)]
    for b, nos in by_board.items():
        lines.append((f"{BOARD_NAME[b]} — {len(nos)} серв ({min(nos):02d}–{max(nos):02d})", BCOL[b]))
    lines.append(("Типы: " + " · ".join(f"{t} × {n}" for t, n in counts.items()), None))
    lines.append(("CAN 500 кбит/с: Органы [120 Ом] — Мозг — Связь — Тело [120 Ом]", (1.0, 0.85, 0.1)))
    lines.append(("Подпись: номер / тип; оболочка полупрозрачна", None))
    for i, (txt, rgb) in enumerate(lines):
        cu = bpy.data.curves.new(f"Legend_{i}", 'FONT')
        cu.body, cu.size = txt, 0.022 if i == 0 else 0.018
        if FONT:
            cu.font = FONT
        to = bpy.data.objects.new(f"Legend_{i}", cu)
        to.data.materials.append(M_TEXT)
        coll.objects.link(to)
        to.parent = root
        to.location = (0.03 if rgb else 0.0, -0.032 * i, 0)
        if rgb:
            sq = Mesh().mat(_emit(f"leg_sq_{i}", rgb, 1.5)).box((0, 18), (-2, 14), (0, 0.1))
            me = bpy.data.meshes.new(f"Legend_sq_{i}")
            sq.bm.transform(__import__("mathutils").Matrix.Scale(MM, 4))
            sq.bm.to_mesh(me)
            sq.bm.free()
            me.materials.append(sq.mats[0])
            so = bpy.data.objects.new(f"Legend_sq_{i}", me)
            coll.objects.link(so)
            so.parent = root
            so.location = (0.0, -0.032 * i, 0)
    bk = Mesh().mat(M_BACK).box((-12, 760), (-32 * len(lines) + 6, 32), (-1, -0.5))
    me = bpy.data.meshes.new("Legend_back")
    bk.bm.transform(__import__("mathutils").Matrix.Scale(MM, 4))
    bk.bm.to_mesh(me)
    bk.bm.free()
    me.materials.append(bk.mats[0])
    bo = bpy.data.objects.new("Legend_back", me)
    coll.objects.link(bo)
    bo.parent = root
    place_legend(cam)
    return root


def place_legend(cam):
    """Легенда в левом верхнем углу при текущем ortho_scale камеры (кадр 16:9)."""
    s = cam.data.ortho_scale
    root = bpy.data.objects["Legend"]
    root.scale = (s * 0.55,) * 3
    root.location = (-s / 2 + s * 0.02, s * 9 / 32 - s * 0.035, -0.2)


def build():
    global FONT, M_TEXT, M_BACK, M_LEAD
    _clean()
    FONT = _font()
    M_TEXT = _emit("Label_text", (0.95, 0.96, 0.98), 2.0)
    M_BACK = mat("Label_back", (0.02, 0.02, 0.025), 0.6)
    M_LEAD = _emit("Label_leader", (0.85, 0.86, 0.9), 0.8)
    rig.pose({})
    cam = bpy.data.objects.new("Cam_servo_map", bpy.data.cameras.new("Cam_servo_map"))
    sc.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale = 'ORTHO', 0.62
    cam.location = (1.2, -1.4, 1.1)
    cam.rotation_euler = (Vector((0, 0, 0.19)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    labels = _collection("Labels")
    c_srv = _collection("Servo_labels", labels)
    c_brd = _collection("Board_labels", labels)
    c_leg = _collection("Legend", labels)
    for no, name, joint, kind, rr, board, ch, power in SERVOS:
        o = bpy.data.objects[name]
        c = center(o)
        label(f"Label_{no:02d}", f"{no:02d} / {kind}", c, servo_anchor(no, c), o.parent_bone, cam, c_srv,
              BCOL[board])
    for b, off in (("ESP32_Body", (0, 0, 70)), ("ESP32_Senses", (-35, 0, 95)),
                   ("ESP32_Brain", (40, 0, 62)), ("ESP32_Comms", (0, 30, 60))):
        o = bpy.data.objects[b]
        c = center(o)
        label(f"Label_{b}", BOARD_NAME[b], c, c + Vector(off), o.parent_bone, cam, c_brd, BCOL[b])
    for n, txt, off in (("CAN_transceiver_Senses", "CAN · 120 Ом", (-60, 40, -25)),
                        ("CAN_transceiver_Body", "CAN · 120 Ом", (0, 55, 40)),
                        ("CAN_transceiver_Comms", "CAN · Связь", (-10, 0, 40))):
        o = bpy.data.objects[n]
        c = center(o)
        label(f"Label_{n}", txt, c, c + Vector(off), o.parent_bone, cam, c_brd, (1.0, 0.85, 0.1))
    legend(cam, c_leg)
    recolor_servos()
    ghost_shell()
    # слои: ViewLayer — без подписей; Servo_map — подписи, servo_map = 1
    base = sc.view_layers[0]
    base["servo_map"] = 0.0
    base.layer_collection.children["Labels"].exclude = True
    vl = sc.view_layers.new("Servo_map")
    vl["servo_map"] = 1.0
    sc.camera = cam
    rig.pose(stand_pose())
    print(f"[stage2] подписей серв {len(c_srv.objects) // 4}, плат/CAN {len(c_brd.objects) // 4}; "
          f"слои: {[v.name for v in sc.view_layers]}")


build()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BASE, "robodog_v6.blend"))
print("[stage2] сохранено")
