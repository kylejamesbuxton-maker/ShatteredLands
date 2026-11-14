# Adds weapons + keyed animations to viking_build.blend, renders key poses, saves viking_anim.blend
#   blender --background --python animate_viking.py -- <models_dir> [render]
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix, Quaternion
args = sys.argv[sys.argv.index("--") + 1:]
mdir = args[0]; do_render = len(args) > 1 and args[1] == "render"
bpy.ops.wm.open_mainfile(filepath=os.path.join(mdir, "viking_build.blend"))
rig = bpy.data.objects["VikingRig"]; B = rig.data.bones; P = rig.pose.bones
for pb in P: pb.rotation_mode = 'QUATERNION'

def mat(name, color, metal=0.0, rough=0.8):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1); m.metallic = metal; m.roughness = rough
    return m
M_steel = mat("Steel", (0.62, 0.65, 0.68), 0.9, 0.3); M_grip = mat("Grip", (0.06, 0.035, 0.02)); M_gold = mat("Gilt", (0.55, 0.38, 0.08), 0.9, 0.35)
M_paint = mat("ShieldPaint", (0.6, 0.6, 0.6)); M_rim = mat("ShieldRim", (0.12, 0.07, 0.035)); M_boss = mat("Boss", (0.35, 0.36, 0.38), 0.85, 0.4)

# ---------------------------------------------------------------- grip frames from the rest pose
def hand_frame(s):
    h = B["hand_" + s].head_local; mid = B["middle_01_" + s].head_local
    idx = B["index_01_" + s].head_local; pk = B["pinky_01_" + s].head_local; th = B["thumb_01_" + s].head_local
    hy = (mid - h).normalized()                       # along the hand, toward the knuckles
    bd = (idx - pk); bd = (bd - hy * bd.dot(hy)).normalized()   # grip axis: pinky -> index (blade exits here)
    pn = hy.cross(bd).normalized()
    if (th - h).dot(pn) < 0: pn = -pn                 # toward the palm
    grip = h + (mid - h) * 0.85 + pn * 0.018
    return grip, bd, pn, hy

def box(bm, center, ax, ay, az, sx, sy, sz, mi):
    """cube with half-sizes along three axes"""
    r = bmesh.ops.create_cube(bm, size=2)
    for v in r["verts"]:
        x, y, z = v.co; v.co = center + ax * (x * sx) + ay * (y * sy) + az * (z * sz)
    for f in {f for v in r["verts"] for f in v.link_faces}: f.material_index = mi

def make_obj(name, bm, mats, bone):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for m in mats: ob.data.materials.append(m)
    for p in ob.data.polygons: p.use_smooth = True
    ob.parent = rig; g = ob.vertex_groups.new(name=bone); g.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    md = ob.modifiers.new("Armature", 'ARMATURE'); md.object = rig
    return ob

for n in ("Sword", "Shield"):
    if n in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[n])

g, bd, pn, hy = hand_frame("r"); BD_R, PN_R = bd.copy(), pn.copy()
bm = bmesh.new()
box(bm, g, bd, pn, hy, 0.055, 0.016, 0.016, 0)                 # leather grip
box(bm, g - bd * 0.07, bd, pn, hy, 0.022, 0.03, 0.022, 1)        # pommel
box(bm, g + bd * 0.065, bd, pn, hy, 0.012, 0.09, 0.014, 1)       # crossguard
r = bmesh.ops.create_cube(bm, size=2)                           # tapered blade
for v in r["verts"]:
    x, y, z = v.co; t = (x + 1) / 2
    v.co = g + bd * (0.08 + t * 0.78) + pn * (y * 0.024 * (1 - 0.55 * t)) + hy * (z * 0.004)
for f in {f for v in r["verts"] for f in v.link_faces}: f.material_index = 2
sword = make_obj("Sword", bm, [M_grip, M_gold, M_steel], "hand_r")

g, bd, pn, hy = hand_frame("l")
c = g + hy * 0.035; nrm = hy; u = bd; w = nrm.cross(u).normalized()
bm = bmesh.new(); uv_lay = bm.loops.layers.uv.new("UVMap")
r = bmesh.ops.create_circle(bm, cap_ends=True, segments=28, radius=1.0)
front = r["verts"]
for v in front: x, y, _ = v.co; v.co = c + u * (x * 0.43) + w * (y * 0.43) + nrm * 0.012
ext = bmesh.ops.extrude_face_region(bm, geom=list({f for v in front for f in v.link_faces}))
for v in [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]: v.co -= nrm * 0.018
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
for f in bm.faces:
    f.material_index = 0 if abs(f.normal.dot(nrm)) > 0.9 else 1
    for l in f.loops:
        d = l.vert.co - c; l[uv_lay].uv = (0.5 + d.dot(u) / 0.86, 0.5 + d.dot(w) / 0.86)
bs = bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1.0)
for v in bs["verts"]:
    x, y, z = v.co; v.co = c + u * (x * 0.085) + w * (y * 0.085) + nrm * (0.012 + max(z, 0) * 0.055)
for f in {f for v in bs["verts"] for f in v.link_faces}: f.material_index = 2
shield = make_obj("Shield", bm, [M_paint, M_rim, M_boss], "hand_l")

# ---------------------------------------------------------------- posing (absolute rotations in armature space, parents first)
def Rx(a): return Matrix.Rotation(a, 3, 'X')
def Ry(a): return Matrix.Rotation(a, 3, 'Y')
def Rz(a): return Matrix.Rotation(a, 3, 'Z')
def rest(n): return B[n].matrix_local.to_3x3()
def upd(): bpy.context.view_layer.update()
def set_abs(n, R, head=None):
    pb = P[n]; Mx = R.to_4x4(); Mx.translation = head if head is not None else pb.head.copy(); pb.matrix = Mx; upd()
def rot(n, Rw, head=None): set_abs(n, Rw @ rest(n), head)
def aim(n, d, twist=0.0):
    d = Vector(d).normalized(); R0 = rest(n)
    R = d.to_track_quat('Y', 'Z').to_matrix() if False else (R0.col[1].rotation_difference(d).to_matrix() @ R0)
    if twist: R = Matrix.Rotation(twist, 3, d) @ R
    set_abs(n, R)
def follow(child, parent, wrist=None):
    R = P[parent].matrix.to_3x3().normalized() @ (rest(parent).inverted() @ rest(child))
    if wrist is not None: R = wrist @ R
    set_abs(child, R)

def solve_wrist(elev):
    """bend the wrist (about the palm normal) so the blade points at the wanted elevation (radians above horizontal)"""
    Rh = P["hand_r"].matrix.to_3x3().normalized(); K = Rh @ rest("hand_r").inverted()
    axis = (K @ PN_R).normalized(); best = (9, 0)
    for i in range(-30, 31):
        w = i * 0.05; d = Matrix.Rotation(w, 3, axis) @ (K @ BD_R)
        e = math.asin(max(-1, min(1, d.z)))
        fwd = -d.y   # prefer blades that point forward-ish rather than straight back, except in the windup
        score = abs(e - elev) - (0.15 * fwd if elev > -0.7 else 0)
        if score < best[0]: best = (score, w)
    set_abs("hand_r", Matrix.Rotation(best[1], 3, axis) @ Rh)
FINGERS = [b.name for b in B if any(b.name.startswith(k) for k in ("index", "middle", "ring", "pinky"))]
THUMBS = [b.name for b in B if b.name.startswith("thumb")]
def apply_pose(p):
    for pb in P: pb.matrix_basis = Matrix.Identity(4)
    upd()
    T, L, cr = p.get("T", 0), p.get("L", 0), p.get("crouch", 0)
    rot("pelvis", Rz(T * 0.15), B["pelvis"].head_local + Vector((0, 0, -cr + p.get("bob", 0))))
    rot("spine_01", Rz(T * 0.4) @ Rx(L * 0.4)); rot("spine_02", Rz(T * 0.7) @ Rx(L * 0.75)); rot("spine_03", Rz(T) @ Rx(L))
    C = Rz(T) @ Rx(L)
    for n in ("clavicle_l", "clavicle_r"): rot(n, C)
    rot("neck_01", Rz(T * 0.45) @ Rx(L * 0.4)); rot("head", Rz(T * 0.12) @ Rx(-L * 0.3))
    for s, uk, fk, tk in (("r", "ur", "fr", "twr"), ("l", "ul", "fl", "twl")):
        aim("upperarm_" + s, C @ Vector(p[uk]), p.get(tk + "u", 0))
        aim("lowerarm_" + s, C @ Vector(p[fk]), p.get(tk, 0))
        follow("hand_" + s, "lowerarm_" + s)
        if s == "r" and "blade" in p: solve_wrist(p["blade"])
    for side, (th, kn) in (("l", p["legL"]), ("r", p["legR"])):
        Rt = Rx(-th) @ Rz((0.05 if side == "l" else -0.05) * p.get("splay", 1))
        rot("thigh_" + side, Rt); rot("calf_" + side, Rt @ Rx(kn)); rot("foot_" + side, Rx(p.get("toe", 0) * 0)); rot("ball_" + side, Matrix.Identity(3))
    # clenched fists around the grips
    for n in FINGERS: P[n].rotation_quaternion = Quaternion((1, 0, 0), CURL)
    for n in THUMBS: P[n].rotation_quaternion = Quaternion((1, 0, 0), CURL * 0.4)
    upd()

CURL = float(os.environ.get("VK_CURL", "1.25"))
GUARD = dict(T=0.1, L=0.08, crouch=0.05, ur=(-0.42, -0.35, -0.84), fr=(-0.2, -0.82, 0.52), twr=0.0, blade=0.8,
             ul=(0.45, -0.45, -0.77), fl=(-0.45, -0.88, 0.12), twl=0.0, legL=(0.35, 0.45), legR=(-0.25, 0.35))
POSES = {
 "guard": GUARD,
 "over_wind": dict(GUARD, T=-0.45, L=-0.06, ur=(-0.3, 0.08, 0.95), fr=(-0.05, 0.75, -0.55), blade=-1.0),
 "over_hit": dict(GUARD, T=0.38, L=0.2, crouch=0.09, ur=(-0.18, -0.96, -0.12), fr=(0.05, -0.8, -0.6), blade=-0.45),
 "diag_wind": dict(GUARD, T=-0.6, L=0.0, ur=(-0.82, 0.12, 0.55), fr=(-0.12, 0.8, 0.58), blade=-0.2),
 "diag_hit": dict(GUARD, T=0.52, L=0.16, crouch=0.08, ur=(0.36, -0.85, -0.36), fr=(0.62, -0.55, -0.56), blade=-0.5),
 "idle_a": dict(T=0, L=0.02, crouch=0, blade=-0.6, ur=(-0.18, -0.15, -0.97), fr=(-0.1, -0.62, -0.78), ul=(0.25, -0.22, -0.94), fl=(-0.18, -0.82, -0.54), legL=(0.05, 0.05), legR=(-0.05, 0.05)),
}
POSES["idle_b"] = dict(POSES["idle_a"], L=0.045, bob=-0.004)
WALK_ARMS = dict(T=0, L=0.07, crouch=0.01, blade=-0.4, ur=(-0.2, -0.3, -0.93), fr=(-0.1, -0.75, -0.65), ul=(0.32, -0.3, -0.9), fl=(-0.25, -0.85, -0.45))
POSES["walk0"] = dict(WALK_ARMS, legL=(0.45, 0.1), legR=(-0.35, 0.35), bob=-0.012, T=0.06)
POSES["walk1"] = dict(WALK_ARMS, legL=(0.0, 0.05), legR=(0.12, 0.95), bob=0.012, T=0.0)
POSES["walk2"] = dict(WALK_ARMS, legL=(-0.35, 0.35), legR=(0.45, 0.1), bob=-0.012, T=-0.06)
POSES["walk3"] = dict(WALK_ARMS, legL=(0.12, 0.95), legR=(0.0, 0.05), bob=0.012, T=0.0)

CLIPS = {
 "idle":  [(0, "idle_a"), (30, "idle_b"), (60, "idle_a")],
 "walk":  [(0, "walk0"), (8, "walk1"), (15, "walk2"), (23, "walk3"), (30, "walk0")],
 "guard": [(0, "guard"), (30, dict(GUARD, L=0.1, crouch=0.06)), (60, "guard")],
 "over":  [(0, "guard"), (11, "over_wind"), (15, "over_hit"), (24, "guard")],
 "diag":  [(0, "guard"), (11, "diag_wind"), (15, "diag_hit"), (24, "guard")],
}
rig.animation_data_create()
for name, keys in CLIPS.items():
    act = bpy.data.actions.new(name); act.use_fake_user = True; rig.animation_data.action = act
    for f, pose in keys:
        apply_pose(POSES[pose] if isinstance(pose, str) else pose)
        for pb in P:
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if pb.name == "pelvis": pb.keyframe_insert("location", frame=f)
    print("CLIP", name, "frames", keys[-1][0])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(mdir, "viking_anim.blend"))
print("SAVED_ANIM")

if do_render:
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'; scene.render.resolution_x, scene.render.resolution_y = 560, 700
    world = bpy.data.worlds.new("W"); scene.world = world
    try:
        world.use_nodes = True; world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.47, 0.5, 1)
    except Exception: pass
    sd = bpy.data.lights.new("Sun", 'SUN'); sd.energy = 3.2; sun = bpy.data.objects.new("Sun", sd); scene.collection.objects.link(sun); sun.rotation_euler = (0.9, 0.2, -0.6)
    fd = bpy.data.lights.new("Fill", 'AREA'); fd.energy = 120; fd.size = 3; fl = bpy.data.objects.new("Fill", fd); scene.collection.objects.link(fl); fl.location = (-2.5, -2, 1.6); fl.rotation_euler = (1.2, 0, -0.9)
    cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); scene.collection.objects.link(cam); scene.camera = cam; cd.lens = 45
    tg = bpy.data.objects.new("T", None); scene.collection.objects.link(tg); tg.location = (0, 0, 1.0)
    tc = cam.constraints.new('TRACK_TO'); tc.target = tg; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    if "Mail" in bpy.data.objects: bpy.data.objects["Mail"].hide_render = True
    views = args[2].split(",") if len(args) > 2 else ["guard:over:11", "over:15", "diag:11", "diag:15", "walk:8", "idle:0"]
    for vw in views:
        parts = vw.split(":"); clip, frame = parts[0], int(parts[-1])
        rig.animation_data.action = bpy.data.actions[clip]; scene.frame_set(frame)
        for side, loc in (("front", (2.2, -3.6, 1.5)), ("side", (-4.0, -0.6, 1.4))):
            cam.location = loc
            scene.render.filepath = os.path.join(mdir, "pose_%s_%d_%s.png" % (clip, frame, side))
            bpy.ops.render.render(write_still=True)
        print("RENDERED", clip, frame)
