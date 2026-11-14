"""
Gjermundbu helmet (Norway, c. 970) — hero asset, freshly forged.

Four-plate rounded bowl, brow band, riveted crest (nose-to-nape) and ear-to-ear bands, top knob, and the
complete spectacle guard: a single forged plate with brow bar, broad rims round both eye openings and a
nose guard, riveted to the brow band. Sized for the 1.8 m mannequins used by the Viking/English scripts.

Run headless:  blender --background --python gjermundbu_helmet.py -- <out_dir> [render]
or paste into Blender's Scripting workspace (builds into the current scene).
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix

HEAD_C = Vector((0.0, -0.005, 1.665)); HEAD_R = 0.108
RX, RY = HEAD_R * 0.9 + 0.018, HEAD_R * 0.98 + 0.018      # bowl half-widths (side / front-back)
BROW = HEAD_C.z + 0.04                                      # lower edge of the bowl
TOP = HEAD_C.z + HEAD_R * 1.08 + 0.052                      # crown: a tall, rounded bowl like the original
RZ = TOP - BROW


def new_steel(name="Forged Steel (new)"):
    """Freshly forged, polished working steel: faint planishing-hammer facets and fine polishing lines, no rust."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if hasattr(m, "use_nodes"): m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); N, L = nt.nodes, nt.links
    out = N.new('ShaderNodeOutputMaterial'); out.location = (700, 0)
    bs = N.new('ShaderNodeBsdfPrincipled'); bs.location = (400, 0); L.new(bs.outputs[0], out.inputs[0])
    tc = N.new('ShaderNodeTexCoord'); tc.location = (-900, 0)
    vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'SMOOTH_F1'; vor.inputs['Scale'].default_value = 70; L.new(tc.outputs['Object'], vor.inputs['Vector'])
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 80); L.new(tc.outputs['Object'], mp.inputs['Vector'])
    lines = N.new('ShaderNodeTexNoise'); lines.inputs['Scale'].default_value = 40; lines.inputs['Detail'].default_value = 2; L.new(mp.outputs[0], lines.inputs['Vector'])
    rough = N.new('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = 0.28; rough.inputs['To Max'].default_value = 0.42; L.new(lines.outputs['Fac'], rough.inputs['Value'])
    L.new(rough.outputs['Result'], bs.inputs['Roughness'])
    h = N.new('ShaderNodeMath'); h.operation = 'ADD'; L.new(vor.outputs['Distance'], h.inputs[0]); h.inputs[1].default_value = 0.0
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06; bump.inputs['Distance'].default_value = 0.004
    L.new(h.outputs[0], bump.inputs['Height']); L.new(bump.outputs['Normal'], bs.inputs['Normal'])
    bs.inputs['Base Color'].default_value = (0.62, 0.63, 0.65, 1); bs.inputs['Metallic'].default_value = 1.0
    m.diffuse_color = (0.62, 0.63, 0.65, 1); m.metallic = 1.0; m.roughness = 0.22
    return m


def blued_steel(name="Blued Steel (new)"):
    """Heat-blued / oil-darkened new steel for the bowl plates: dark blue-grey, satin, faint hammer facets."""
    m = new_steel(name); bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value = (0.07, 0.09, 0.13, 1); m.diffuse_color = (0.07, 0.09, 0.13, 1); bs.inputs['Metallic'].default_value = 0.8
    rr = next(n for n in m.node_tree.nodes if n.type == 'MAP_RANGE'); rr.inputs['To Min'].default_value = 0.38; rr.inputs['To Max'].default_value = 0.5
    return m


def dome_point(theta, phi, lift=0.0):
    """Point on the bowl: theta 0 = crown .. pi/2 = brow; phi around the head (-pi/2 = front)."""
    s, c = math.sin(theta), math.cos(theta)
    n = Vector((s * math.cos(phi) / RX, s * math.sin(phi) / RY, c / RZ)).normalized()
    return Vector((HEAD_C.x + RX * s * math.cos(phi), HEAD_C.y + RY * s * math.sin(phi), BROW + RZ * c)) + n * lift


def surface(bm, fn, nu, nv, keep=None):
    rows = [[bm.verts.new(fn(i / nu, j / nv)) for i in range(nu + 1)] for j in range(nv + 1)]
    for j in range(nv):
        for i in range(nu):
            if keep and not keep((i + 0.5) / nu, (j + 0.5) / nv): continue
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))


def build_bowl(bm):
    surface(bm, lambda u, v: dome_point(v * math.pi / 2 * 0.999 + 0.001, u * 2 * math.pi), 48, 18)


def brow_band(bm):
    surface(bm, lambda u, v: (lambda a: Vector((HEAD_C.x + (RX + 0.004) * math.cos(a), HEAD_C.y + (RY + 0.004) * math.sin(a), BROW - 0.004 + v * 0.026)))(u * 2 * math.pi), 64, 2)


def band(bm, plane="crest", width=0.018, raise_=0.004):
    """Riveted strap over the crown: crest = nose-to-nape, side = ear-to-ear."""
    def fn(u, v):
        t = -math.pi / 2 + math.pi * v                         # brow -> crown -> brow
        theta, phi = abs(t), (-math.pi / 2 if t < 0 else math.pi / 2) if plane == "crest" else (0.0 if t < 0 else math.pi)
        p = dome_point(max(theta, 0.002), phi, raise_ * (1 - (2 * u - 1) ** 2 * 0.5))
        side = Vector((1, 0, 0)) if plane == "crest" else Vector((0, 1, 0))
        return p + side * ((u - 0.5) * width)
    surface(bm, fn, 4, 60)


def rivets(bm, r=0.0035):
    for plane, phis in (("crest", (-math.pi / 2, math.pi / 2)), ("side", (0.0, math.pi))):
        for phi in phis:
            for th in (0.35, 0.75, 1.15, 1.45):
                c = dome_point(th, phi, 0.0075)
                v = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)["verts"]
                bmesh.ops.translate(bm, vec=c, verts=v)
    for k in range(14):                                       # brow band rivets
        a = -math.pi / 2 + (k + 0.5) * 2 * math.pi / 14
        c = Vector((HEAD_C.x + (RX + 0.0075) * math.cos(a), HEAD_C.y + (RY + 0.0075) * math.sin(a), BROW + 0.009))
        v = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)["verts"]; bmesh.ops.translate(bm, vec=c, verts=v)


def knob(bm):
    v = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.013, radius2=0.004, depth=0.02)["verts"]
    bmesh.ops.translate(bm, vec=Vector((HEAD_C.x, HEAD_C.y, TOP + 0.008)), verts=v)


EYE_X, EYE_Z = 0.034, BROW - 0.027        # eye opening centres (arc distance from the middle, height)
EYE_A, EYE_B = 0.023, 0.019               # eye opening semi-axes
RIM = 0.013                               # plate width round the eyes


def face_pos(s, z, lift=0.0):
    """Map (arc distance across the face, height) onto a surface just in front of the face, following the brow curve."""
    R = RY + 0.007 + lift
    a = -math.pi / 2 + s / R
    return Vector((HEAD_C.x + (RX + 0.007 + lift) * math.cos(a), HEAD_C.y + R * math.sin(a), z))


# --- spectacle guard, modelled on the original (Museum of Cultural History, Oslo):
# one forged plate; two large, slightly teardrop eye openings; the rims rise over each eye and dip to a riveted
# point between them; broader lower rims sweep down into a pointed nasal.
G_EYE_S, G_EYE_Z = 0.037, BROW - 0.027        # eye centres (arc distance from the middle, height)
G_A, G_B, G_TILT = 0.024, 0.018, 0.22          # eye-opening semi-axes and outward-down tilt
G_RIM_SIDE, G_RIM_TOP, G_RIM_LOW = 0.012, 0.0085, 0.017
G_TIP = G_EYE_Z - G_B - 0.034                  # nasal tip height


def _eye_local(s, z, sx):
    ds, dz = s - sx * G_EYE_S, z - G_EYE_Z
    t = -G_TILT * sx                           # outer side lower
    return ds * math.cos(t) + dz * math.sin(t), -ds * math.sin(t) + dz * math.cos(t)


def _in_hole(s, z):
    for sx in (1, -1):
        sl, zl = _eye_local(s, z, sx)
        inner = sl * sx < 0 and zl < 0                                    # teardrop: inner-lower corner drawn toward the nose
        if (sl / (G_A * (1.12 if inner else 1.0))) ** 2 + (zl / (G_B * (1.15 if inner else 1.0))) ** 2 <= 1.0: return True
    return False


def _in_plate(s, z):
    for sx in (1, -1):
        sl, zl = _eye_local(s, z, sx)
        bz = G_B + (G_RIM_TOP if zl > 0 else G_RIM_LOW)
        if (sl / (G_A + G_RIM_SIDE)) ** 2 + (zl / bz) ** 2 <= 1.0: return True
    if G_TIP <= z <= G_EYE_Z and abs(s) <= 0.013 * (z - G_TIP) / (G_EYE_Z - G_TIP) + 0.0015: return True   # pointed nasal
    return False


def _contour(inside, centre, n=220, rmax=0.13):
    """Boundary of a star-shaped region by marching outwards along rays from `centre`."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n; r = 0.0
        while r < rmax and inside(centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)): r += 0.0004
        pts.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    return pts


def spectacle_guard(bm):
    flat = bmesh.new()
    loops = [_contour(_in_plate, (0.0, G_EYE_Z - 0.004))]
    for sx in (1, -1):
        loops.append(_contour(lambda s, z: _in_hole(s, z) and (s * sx) > 0, (sx * G_EYE_S, G_EYE_Z), n=120, rmax=0.05))
    edges = []
    for lp in loops:
        vs = [flat.verts.new((x, z, 0.0)) for x, z in lp]
        edges += [flat.edges.new((vs[i], vs[(i + 1) % len(vs)])) for i in range(len(vs))]
    bmesh.ops.triangle_fill(flat, use_beauty=True, use_dissolve=False, edges=edges)
    bmesh.ops.subdivide_edges(flat, edges=[e for e in flat.edges if e.calc_length() > 0.008], cuts=2, use_grid_fill=True)
    bmesh.ops.triangulate(flat, faces=flat.faces)
    # wrap the flat plate round the face; the nasal stands a touch proud
    for v in flat.verts:
        s, z = v.co.x, v.co.y
        lift = 0.002 * max(0.0, 1 - abs(s) / 0.02) * max(0.0, (G_EYE_Z - z) / (G_EYE_Z - G_TIP))
        v.co = face_pos(s, z, lift - 0.002)
    me = bpy.data.meshes.new("tmp"); flat.to_mesh(me); flat.free(); bm.from_mesh(me); bpy.data.meshes.remove(me)

def guard_rivets(bm, r=0.0034):
    top_mid = max(z for s, z in _contour(_in_plate, (0.0, G_EYE_Z - 0.004)) if abs(s) < 0.002)
    for s, z in ((0.0, top_mid - 0.004), (0.062, BROW + 0.002), (-0.062, BROW + 0.002), (0.0, G_EYE_Z - 0.012)):
        v = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)["verts"]; bmesh.ops.translate(bm, vec=face_pos(s, z, 0.003), verts=v)

def to_object(name, bm, mat, thickness=0.0, coll=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(name, me); (coll or bpy.context.scene.collection).objects.link(ob); me.materials.append(mat)
    if thickness:
        s = ob.modifiers.new("Plate Thickness", 'SOLIDIFY'); s.thickness = thickness; s.offset = -1.0; s.use_even_offset = True
    ob.modifiers.new("Weighted Normals", 'WEIGHTED_NORMAL')
    return ob


def build(coll=None):
    steel = new_steel(); blued = blued_steel(); parts = []
    for name, fn, th in (("Gjermundbu Bowl", build_bowl, 0.0025), ("Gjermundbu Brow Band", brow_band, 0.003), ("Gjermundbu Crest Band", lambda b: band(b, "crest"), 0.003),
                         ("Gjermundbu Side Band", lambda b: band(b, "side"), 0.003), ("Gjermundbu Spectacle Guard", spectacle_guard, 0.003),
                         ("Gjermundbu Rivets & Knob", lambda b: (rivets(b), guard_rivets(b), knob(b)), 0.0)):
        bm = bmesh.new(); fn(bm); parts.append(to_object(name, bm, blued if name.startswith("Gjermundbu Bowl") else steel, th, coll))
    return parts


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv:                                          # headless: fresh scene, export GLB, optional render
        out = argv[0]; os.makedirs(out, exist_ok=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        parts = build()
        bpy.ops.object.select_all(action='DESELECT')
        for p in parts: p.select_set(True)
        bpy.ops.export_scene.gltf(filepath=os.path.join(out, "gjermundbu_helmet_v2.glb"), export_format='GLB', use_selection=True, export_apply=True)
        print("EXPORTED", os.path.join(out, "gjermundbu_helmet_v2.glb"), sum(len(p.data.polygons) for p in parts), "faces (before solidify)")
        if len(argv) > 1 and argv[1] == "render":
            sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 96; sc.render.resolution_x, sc.render.resolution_y = 1400, 900
            w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.055, 0.06, 1)
            tgt = Vector((0, 0, HEAD_C.z + 0.03))
            for nm, loc, e, sz in (("Key", (-0.7, -0.9, 2.3), 90, 0.9), ("Fill", (0.8, -0.8, 1.8), 30, 1.2), ("Rim", (0.2, 0.9, 2.2), 70, 0.8)):
                ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = e; ld.size = sz; ob = bpy.data.objects.new(nm, ld); sc.collection.objects.link(ob); ob.location = loc
                ob.rotation_euler = (tgt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
            cd = bpy.data.cameras.new("Cam"); cd.lens = 85; cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
            for nm, loc in (("helmet_v2_front", (0.0, -1.35, HEAD_C.z + 0.04)), ("helmet_v2_angle", (0.85, -1.05, HEAD_C.z + 0.25))):
                cam.location = loc; cam.rotation_euler = (tgt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
                sc.render.filepath = os.path.join(out, nm + ".png"); bpy.ops.render.render(write_still=True); print("RENDERED", nm)
    else:
        build()
