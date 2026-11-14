"""
Viking Asset Refinement — turns low-poly placeholder characters and armour into render-ready assets.

Run in Blender's Scripting workspace (Alt+P). Targets the SELECTED objects, or every mesh in the scene
if nothing is selected. Safe to re-run: it only touches mesh objects, never stacks duplicate modifiers,
rebuilds materials in place, and replaces the lights/camera it created on a previous run.

 1. Geometry  - marks and creases sharp edges (> 35 deg) so Subdivision keeps plate edges crisp,
                Solidify on open shells (cloth, fur, leather, helmet plates) with per-material thickness,
                Bevel + Weighted Normal on metal and gilt pieces, Subdivision Surface (viewport 1 / render 2).
 2. Materials - procedural PBR node networks, no image textures:
                steel (hammered bump, scratches, edge wear), mail (ring pattern), leather (pores, creases,
                worn edges), fur (clumped volumetric displacement), cloth (woven bump + sheen),
                gold/bronze (tarnish in recesses), wood, paint (chipped over wood), horn, skin/mannequin.
 3. Scene     - 3-point area lighting sized to the row of models, 85 mm camera with depth of field on the
                centre model, Cycles (falls back to EEVEE with AO / reflections / bloom where available).

Material type is read from each material's name (e.g. "Iron/Steel", "Leather", "Fur", "Cloth Woad Blue",
"Gold Trim"), so it works on scenes from viking_armor_tiers.py and similar naming.
"""
import bpy
import bmesh
import math
from mathutils import Vector

TAG = "Refine"                  # prefix for everything this script creates
SHARP_ANGLE = math.radians(35)

# ============================================================== classification
CATEGORIES = [                  # first match wins (checked against the lower-case material name)
    ("mail",     ("mail", "ring")),
    ("gold",     ("gold", "gilt", "brass", "bronze")),
    ("silver",   ("silver",)),
    ("steel",    ("iron", "steel", "metal")),
    ("fur",      ("fur", "pelt", "sheepskin")),
    ("leather",  ("leather", "rawhide", "hide")),
    ("paint",    ("paint",)),
    ("wood",     ("wood", "yew", "ash", "plank")),
    ("horn",     ("horn", "bone", "antler")),
    ("cloth",    ("cloth", "wool", "linen", "trim", "cord", "rope", "padding", "velvet", "string", "surcoat", "tunic")),
    ("skin",     ("mannequin", "skin", "body")),
]
SOLIDIFY_THICKNESS = {"cloth": 0.006, "fur": 0.02, "leather": 0.005, "steel": 0.003, "silver": 0.003,
                      "gold": 0.002, "mail": 0.006, "paint": 0.004, "wood": 0.008, "horn": 0.004, "skin": 0.0}
HARD_SURFACE = {"steel", "silver", "gold", "wood", "paint", "horn"}


def classify_name(name):
    n = name.lower()
    for cat, keys in CATEGORIES:
        if any(k in n for k in keys): return cat
    return "cloth"


def classify_object(ob):
    mats = [s.material for s in ob.material_slots if s.material]
    return classify_name(mats[0].name) if mats else "cloth"

# ============================================================== node helpers
def _sock(node, key, outputs=False):
    """Socket lookup that copes with ShaderNodeMix's duplicate A/B names and renamed Principled inputs."""
    coll = node.outputs if outputs else node.inputs
    if isinstance(key, int): return coll[key]
    if node.bl_idname == 'ShaderNodeMix':
        suffix = {'RGBA': 'Color', 'FLOAT': 'Float', 'VECTOR': 'Vector'}[node.data_type]
        ident = {'A': 'A_' + suffix, 'B': 'B_' + suffix, 'Result': 'Result_' + suffix, 'Factor': 'Factor_Float'}.get(key, key)
        for s in coll:
            if s.identifier == ident: return s
    for k in ([key] if isinstance(key, str) else key):
        if k in coll: return coll[k]
    return None


class Graph:
    """Tiny builder for shader node trees."""
    def __init__(self, mat):
        if hasattr(mat, "use_nodes"): mat.use_nodes = True
        self.nt = mat.node_tree; self.nt.nodes.clear(); self.x = -1400
        self.out = self.node('ShaderNodeOutputMaterial', loc=(900, 0))
        self.bsdf = self.node('ShaderNodeBsdfPrincipled', loc=(500, 0))
        self.link(self.bsdf, 0, self.out, 'Surface')
        self.coords = self.node('ShaderNodeTexCoord', loc=(-1600, 0))
    def node(self, kind, loc=None, **props):
        n = self.nt.nodes.new(kind)
        n.location = loc or (self.x, 0); self.x += 40
        for k, v in props.items():
            if hasattr(n, k): setattr(n, k, v)
        return n
    def link(self, a, ao, b, bi):
        sa, sb = _sock(a, ao, True), _sock(b, bi)
        if sa is not None and sb is not None: self.nt.links.new(sa, sb)
    def set(self, node, key, value):
        s = _sock(node, key)
        if s is not None: s.default_value = value
    # --- common building blocks
    def noise(self, scale, detail=6.0, rough=0.55, vec=None, kind=None, dim='3D'):
        n = self.node('ShaderNodeTexNoise')
        if hasattr(n, "noise_dimensions"): n.noise_dimensions = dim
        if kind and hasattr(n, "noise_type"): n.noise_type = kind           # 4.1+: FBM / HETERO_TERRAIN / RIDGED... (old Musgrave)
        self.set(n, 'Scale', scale); self.set(n, 'Detail', detail); self.set(n, 'Roughness', rough)
        self.link(vec or self.coords, 'Object' if vec is None else 0, n, 'Vector'); return n
    def voronoi(self, scale, feature='F1', vec=None):
        n = self.node('ShaderNodeTexVoronoi', feature=feature); self.set(n, 'Scale', scale)
        self.link(vec or self.coords, 'Object' if vec is None else 0, n, 'Vector'); return n
    def mapping(self, scale=(1, 1, 1)):
        m = self.node('ShaderNodeMapping'); self.set(m, 'Scale', scale); self.link(self.coords, 'Object', m, 'Vector'); return m
    def ramp(self, src, out, stops):
        r = self.node('ShaderNodeValToRGB'); els = r.color_ramp.elements
        while len(els) < len(stops): els.new(0.5)
        for e, (pos, col) in zip(els, stops):
            e.position = pos; e.color = col if len(col) == 4 else (*col, 1.0)
        self.link(src, out, r, 'Fac'); return r
    def math(self, op, a=None, ao=0, b=None, bo=0, value=None, clamp=False):
        m = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        if a is not None: self.link(a, ao, m, 0)
        if b is not None: self.link(b, bo, m, 1)
        elif value is not None: m.inputs[1].default_value = value
        return m
    def mix(self, kind, fac, a, b, blend='MIX'):
        m = self.node('ShaderNodeMix', data_type=kind)
        if kind == 'RGBA': m.blend_type = blend
        for key, src in (('Factor', fac), ('A', a), ('B', b)):
            if isinstance(src, tuple) and len(src) == 2 and hasattr(src[0], "outputs"): self.link(src[0], src[1], m, key)
            else: self.set(m, key, src)
        return m
    def bump(self, height_src, out, strength, distance=0.01, normal=None):
        b = self.node('ShaderNodeBump'); self.set(b, 'Strength', strength); self.set(b, 'Distance', distance)
        self.link(height_src, out, b, 'Height')
        if normal is not None: self.link(normal, 'Normal', b, 'Normal')
        return b
    def edge_wear(self, lo=0.5, hi=0.56):
        """Convex edges (Cycles pointiness); harmlessly flat in EEVEE."""
        g = self.node('ShaderNodeNewGeometry')
        m = self.node('ShaderNodeMapRange'); self.set(m, 'From Min', lo); self.set(m, 'From Max', hi)
        self.link(g, 'Pointiness', m, 'Value'); return m
    def principled(self, **vals):
        names = {"metallic": "Metallic", "roughness": "Roughness", "sheen": ("Sheen Weight", "Sheen"), "sheen_rough": "Sheen Roughness",
                 "coat": ("Coat Weight", "Clearcoat"), "sss": ("Subsurface Weight", "Subsurface"), "spec": ("Specular IOR Level", "Specular")}
        for k, v in vals.items(): self.set(self.bsdf, names[k], v)

# ============================================================== procedural PBR materials
def rgb(mat):
    c = mat.diffuse_color; return (c[0], c[1], c[2], 1.0)


def darker(c, f): return (c[0] * f, c[1] * f, c[2] * f, 1.0)


def mat_steel(g, base, silver=False):
    hammer = g.voronoi(55.0, 'SMOOTH_F1')               # hammer-planished facets
    grain = g.noise(180.0, 8, 0.6)
    scr_map = g.mapping((1.0, 1.0, 60.0)); scratches = g.noise(90.0, 2, 0.4, vec=scr_map)
    scr = g.math('GREATER_THAN', scratches, 'Fac', value=0.62)
    wear = g.edge_wear()
    col = g.mix('RGBA', (grain, 'Fac'), darker(base, 0.75), base)
    col = g.mix('RGBA', (wear, 'Result'), (col, 'Result'), (0.85, 0.86, 0.88, 1.0) if not silver else (0.95, 0.95, 0.96, 1.0))
    g.link(col, 'Result', g.bsdf, 'Base Color')
    rough = g.math('MULTIPLY_ADD', grain, 'Fac', value=0.18); rough.inputs[2].default_value = 0.16 if not silver else 0.1
    rough = g.math('SUBTRACT', rough, 0, scr, 0); rough.use_clamp = True
    g.link(rough, 0, g.bsdf, 'Roughness')
    h = g.math('ADD', hammer, 'Distance', grain, 'Fac'); h = g.math('SUBTRACT', h, 0, scr, 0)
    g.link(g.bump(h, 0, 0.18, 0.004), 'Normal', g.bsdf, 'Normal')
    g.principled(metallic=1.0)


def mat_mail(g, base):
    m = g.mapping((1.0, 1.0, 1.6))
    cells = g.voronoi(140.0, 'F1', vec=m)
    ring = g.math('SUBTRACT', cells, 'Distance', value=0.3); ring = g.math('ABSOLUTE', ring, 0)
    ring = g.math('LESS_THAN', ring, 0, value=0.12)                                        # ring outlines
    grime = g.noise(40.0, 4, 0.6)
    col = g.mix('RGBA', (ring, 0), darker(base, 0.35), base)
    col = g.mix('RGBA', (grime, 'Fac'), (col, 'Result'), darker(base, 0.6), 'MULTIPLY')
    g.link(col, 'Result', g.bsdf, 'Base Color')
    r = g.math('MULTIPLY_ADD', ring, 0, value=-0.15); r.inputs[2].default_value = 0.68
    g.link(r, 0, g.bsdf, 'Roughness')
    g.link(g.bump(ring, 0, 0.25, 0.0015), 'Normal', g.bsdf, 'Normal')
    g.principled(metallic=0.85)


def mat_leather(g, base):
    pores = g.noise(420.0, 3, 0.5)
    creases = g.voronoi(14.0, 'DISTANCE_TO_EDGE')
    crease = g.math('LESS_THAN', creases, 'Distance', value=0.03)
    tone = g.noise(6.0, 5, 0.6)
    wear = g.edge_wear()
    col = g.mix('RGBA', (tone, 'Fac'), darker(base, 0.7), base)
    col = g.mix('RGBA', (wear, 'Result'), (col, 'Result'), (min(1, base[0] * 1.3), min(1, base[1] * 1.25), min(1, base[2] * 1.2), 1.0))   # worn, lighter edges
    col = g.mix('RGBA', (crease, 0), (col, 'Result'), darker(base, 0.5))
    g.link(col, 'Result', g.bsdf, 'Base Color')
    r = g.math('MULTIPLY_ADD', tone, 'Fac', value=0.2); r.inputs[2].default_value = 0.45
    g.link(r, 0, g.bsdf, 'Roughness')
    h = g.math('SUBTRACT', pores, 'Fac', crease, 0)
    g.link(g.bump(h, 0, 0.25, 0.002), 'Normal', g.bsdf, 'Normal')
    g.principled(sheen=0.1)


def mat_fur(g, base, mat):
    clumps = g.voronoi(45.0, 'F1')
    strands_map = g.mapping((1.0, 1.0, 9.0)); strands = g.noise(160.0, 6, 0.7, vec=strands_map)
    tips = g.math('MULTIPLY', clumps, 'Distance', strands, 'Fac')
    col = g.ramp(tips, 0, [(0.0, darker(base, 0.45)), (0.35, base), (0.8, (min(1, base[0] * 1.7), min(1, base[1] * 1.6), min(1, base[2] * 1.5), 1.0))])
    g.link(col, 'Color', g.bsdf, 'Base Color')
    g.principled(roughness=0.92, sheen=0.8, sheen_rough=0.6, spec=0.2)
    g.link(g.bump(tips, 0, 1.0, 0.02), 'Normal', g.bsdf, 'Normal')
    disp = g.node('ShaderNodeDisplacement'); g.set(disp, 'Scale', 0.012); g.set(disp, 'Midlevel', 0.3)     # clumped depth
    g.link(tips, 0, disp, 'Height'); g.link(disp, 0, g.out, 'Displacement')
    for holder in (mat, getattr(mat, "cycles", None)):
        if holder is not None and hasattr(holder, "displacement_method"):
            try: holder.displacement_method = 'BOTH'
            except Exception: pass


def mat_cloth(g, base):
    wx = g.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X'); g.set(wx, 'Scale', 260.0); g.link(g.coords, 'Object', wx, 'Vector')
    wz = g.node('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z'); g.set(wz, 'Scale', 260.0); g.link(g.coords, 'Object', wz, 'Vector')
    weave = g.math('MULTIPLY', wx, 'Fac', wz, 'Fac')
    slub = g.noise(25.0, 4, 0.6)
    col = g.mix('RGBA', (slub, 'Fac'), darker(base, 0.82), base)
    col = g.mix('RGBA', (weave, 0), (col, 'Result'), darker(base, 0.88), 'MULTIPLY')
    g.link(col, 'Result', g.bsdf, 'Base Color')
    g.principled(roughness=0.9, sheen=0.5, sheen_rough=0.45, spec=0.3)
    h = g.math('ADD', weave, 0, slub, 'Fac')
    g.link(g.bump(h, 0, 0.22, 0.002), 'Normal', g.bsdf, 'Normal')


def mat_gold(g, base):
    tarnish = g.noise(30.0, 6, 0.65)
    cavity = g.node('ShaderNodeAmbientOcclusion'); g.set(cavity, 'Distance', 0.02)
    dirt = g.math('MULTIPLY', tarnish, 'Fac', value=1.0)
    occl = g.math('SUBTRACT', None, value=0.0); occl.inputs[0].default_value = 1.0; g.link(cavity, 'AO', occl, 1)   # 1 - AO
    amt = g.math('ADD', dirt, 0, occl, 0); amt = g.math('MULTIPLY', amt, 0, value=0.55); amt.use_clamp = True
    col = g.mix('RGBA', (amt, 0), base, (base[0] * 0.35, base[1] * 0.38, base[2] * 0.25, 1.0))
    g.link(col, 'Result', g.bsdf, 'Base Color')
    r = g.math('MULTIPLY_ADD', amt, 0, value=0.5); r.inputs[2].default_value = 0.14
    g.link(r, 0, g.bsdf, 'Roughness')
    g.link(g.bump(tarnish, 'Fac', 0.08, 0.002), 'Normal', g.bsdf, 'Normal')
    g.principled(metallic=1.0, coat=0.15)


def mat_wood(g, base):
    m = g.mapping((1.0, 6.0, 1.0)); dist = g.noise(4.0, 4, 0.5, vec=m)
    rings = g.node('ShaderNodeTexWave', wave_type='RINGS'); g.set(rings, 'Scale', 6.0); g.set(rings, 'Distortion', 6.0); g.link(g.coords, 'Object', rings, 'Vector')
    col = g.mix('RGBA', (rings, 'Fac'), darker(base, 0.7), base)
    g.link(col, 'Result', g.bsdf, 'Base Color')
    g.principled(roughness=0.6)
    g.link(g.bump(rings, 'Fac', 0.12, 0.003), 'Normal', g.bsdf, 'Normal')


def mat_paint(g, base):
    chips = g.noise(18.0, 8, 0.7); wear = g.edge_wear(0.5, 0.54)
    amt = g.math('ADD', chips, 'Fac', wear, 'Result'); bare = g.math('GREATER_THAN', amt, 0, value=0.9)
    col = g.mix('RGBA', (bare, 0), base, (0.36, 0.26, 0.15, 1.0))                          # wood showing through
    g.link(col, 'Result', g.bsdf, 'Base Color')
    r = g.math('MULTIPLY_ADD', bare, 0, value=0.2); r.inputs[2].default_value = 0.62
    g.link(r, 0, g.bsdf, 'Roughness')
    g.link(g.bump(bare, 0, 0.15, 0.001), 'Normal', g.bsdf, 'Normal')


def mat_horn(g, base):
    m = g.mapping((1.0, 1.0, 12.0)); streak = g.noise(20.0, 5, 0.6, vec=m)
    col = g.mix('RGBA', (streak, 'Fac'), darker(base, 0.75), base)
    g.link(col, 'Result', g.bsdf, 'Base Color'); g.principled(roughness=0.35, sss=0.1, coat=0.3)


def mat_skin(g, base):
    n = g.noise(90.0, 4, 0.5)
    g.set(g.bsdf, 'Base Color', base); g.principled(roughness=0.55, sss=0.15)
    g.link(g.bump(n, 'Fac', 0.05, 0.002), 'Normal', g.bsdf, 'Normal')


def rebuild_material(mat):
    if mat.get(TAG + "_done"): return
    base = rgb(mat); cat = classify_name(mat.name); g = Graph(mat)
    {"steel": lambda: mat_steel(g, base), "silver": lambda: mat_steel(g, base, True), "mail": lambda: mat_mail(g, base),
     "leather": lambda: mat_leather(g, base), "fur": lambda: mat_fur(g, base, mat), "cloth": lambda: mat_cloth(g, base),
     "gold": lambda: mat_gold(g, base), "wood": lambda: mat_wood(g, base), "paint": lambda: mat_paint(g, base),
     "horn": lambda: mat_horn(g, base), "skin": lambda: mat_skin(g, base)}[cat]()
    mat[TAG + "_done"] = True

# ============================================================== geometry refinement
def mark_sharp_and_crease(me, angle):
    """Flag hard edges sharp and give them a strong crease so Subdivision keeps them crisp."""
    bm = bmesh.new(); bm.from_mesh(me)
    sharp = []
    for e in bm.edges:
        hard = e.is_boundary or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > angle)
        e.smooth = not hard
        if hard: sharp.append(e.index)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    if hasattr(me, "use_auto_smooth"):                      # Blender <= 4.0
        me.use_auto_smooth = True; me.auto_smooth_angle = angle
    vals = [0.0] * len(me.edges)
    for i in sharp: vals[i] = 0.85
    attr = me.attributes.get("crease_edge") or me.attributes.new("crease_edge", 'FLOAT', 'EDGE')
    attr.data.foreach_set("value", vals)


def is_open_shell(me):
    bm = bmesh.new(); bm.from_mesh(me)
    open_edges = sum(1 for e in bm.edges if e.is_boundary); bm.free()
    return open_edges > 0


def has_mod(ob, kind):
    return any(m.type == kind for m in ob.modifiers)


def add_mod(ob, kind, name, **props):
    m = ob.modifiers.new("%s %s" % (TAG, name), kind)
    for k, v in props.items():
        if hasattr(m, k):
            try: setattr(m, k, v)
            except Exception: pass
    return m


def refine_object(ob):
    if ob.type != 'MESH' or ob.data is None or len(ob.data.polygons) == 0: return False
    cat = classify_object(ob); me = ob.data
    if me.users > 1: ob.data = me = me.copy()                # never edit shared mesh data behind another object's back
    mark_sharp_and_crease(me, SHARP_ANGLE)
    if not has_mod(ob, 'SOLIDIFY') and is_open_shell(me) and SOLIDIFY_THICKNESS.get(cat, 0) > 0:
        add_mod(ob, 'SOLIDIFY', "Shell Thickness", thickness=SOLIDIFY_THICKNESS[cat], offset=1.0, use_even_offset=True, use_rim=True)
    if cat in HARD_SURFACE and not has_mod(ob, 'BEVEL'):
        add_mod(ob, 'BEVEL', "Edge Bevel", width=0.0015, segments=2, limit_method='ANGLE', angle_limit=SHARP_ANGLE, harden_normals=True)
    if not has_mod(ob, 'SUBSURF'):
        add_mod(ob, 'SUBSURF', "Subdivision", levels=1, render_levels=2, quality=3, use_creases=True, use_limit_surface=True,
                boundary_smooth='PRESERVE_CORNERS')
    if not has_mod(ob, 'WEIGHTED_NORMAL'):
        add_mod(ob, 'WEIGHTED_NORMAL', "Weighted Normals", keep_sharp=True, weight=50, mode='FACE_AREA')
    return True

# ============================================================== lighting / camera / render
def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9)); hi = -lo
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c); lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
    return lo, hi


def remove_tagged(kind):
    for ob in list(bpy.data.objects):
        if ob.name.startswith(TAG + " ") and ob.type == kind: bpy.data.objects.remove(ob, do_unlink=True)


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def setup_lights(lo, hi):
    remove_tagged('LIGHT')
    c = (lo + hi) / 2; width = max(hi.x - lo.x, 2.0); height = max(hi.z - lo.z, 1.8)
    scene = bpy.context.scene; dist = width * 0.6 + 4
    rigs = [("Key", (c.x - width * 0.35, c.y - dist, c.z + height * 0.9), 1100, width * 0.5, (1.0, 0.95, 0.88)),
            ("Fill", (c.x + width * 0.45, c.y - dist * 0.8, c.z + height * 0.3), 380, width * 0.7, (0.85, 0.9, 1.0)),
            ("Rim", (c.x, c.y + dist * 0.7, c.z + height * 1.1), 1300, width * 0.45, (1.0, 0.98, 0.95))]
    for name, loc, power, size, color in rigs:
        ld = bpy.data.lights.new("%s %s Light" % (TAG, name), 'AREA'); ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = size, max(size * 0.4, 1.0); ld.energy = power * (width / 6.0); ld.color = color
        ob = bpy.data.objects.new("%s %s Light" % (TAG, name), ld); scene.collection.objects.link(ob)
        ob.location = loc; look_at(ob, (c.x, c.y, c.z + height * 0.15))


def centre_model(objs, c):
    """The object closest to the middle of the row, preferring whole characters (parents / mannequins)."""
    roots = [o for o in objs if o.parent is None] or objs
    return min(roots, key=lambda o: abs(o.matrix_world.translation.x - c.x) + abs(o.matrix_world.translation.y - c.y))


def setup_camera(lo, hi, focus_obj):
    remove_tagged('CAMERA')
    scene = bpy.context.scene; c = (lo + hi) / 2
    width = max(hi.x - lo.x, 1.0) * 1.08; height = max(hi.z - lo.z, 1.0) * 1.15
    cd = bpy.data.cameras.new(TAG + " Cinematic Camera"); cd.lens = 85.0; cd.sensor_width = 36.0
    aspect = scene.render.resolution_x / scene.render.resolution_y
    fov = 2 * math.atan(cd.sensor_width / (2 * cd.lens))
    dist = max(width / 2, height * aspect / 2) / math.tan(fov / 2)
    cam = bpy.data.objects.new(TAG + " Cinematic Camera", cd); scene.collection.objects.link(cam)
    cam.location = (c.x, c.y - dist, c.z + height * 0.08); look_at(cam, (c.x, c.y, c.z))
    cd.dof.use_dof = True; cd.dof.focus_object = focus_obj; cd.dof.aperture_fstop = 5.6
    cd.clip_end = max(1000.0, dist * 3)
    scene.camera = cam


def setup_render():
    scene = bpy.context.scene
    try:
        scene.render.engine = 'CYCLES'
        cy = scene.cycles
        for prop, val in (("samples", 256), ("use_denoising", True), ("use_adaptive_sampling", True), ("feature_set", 'SUPPORTED')):
            if hasattr(cy, prop):                            # options differ between Blender versions
                try: setattr(cy, prop, val)
                except Exception: pass
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            if any(d.type != 'CPU' for d in prefs.get_devices_for_type(prefs.compute_device_type)): cy.device = 'GPU'
        except Exception: pass
        scene.render.film_transparent = False
    except Exception:
        setup_eevee()
    if scene.world is None: scene.world = bpy.data.worlds.new(TAG + " World")
    w = scene.world
    if hasattr(w, "use_nodes"): w.use_nodes = True
    bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg: bg.inputs[0].default_value = (0.05, 0.055, 0.06, 1.0); bg.inputs[1].default_value = 1.0
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'


def setup_eevee():
    scene = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try: scene.render.engine = eng; break
        except Exception: continue
    ev = scene.eevee
    for prop, val in (("use_gtao", True), ("use_ssr", True), ("use_ssr_refraction", True), ("use_bloom", True),   # legacy EEVEE
                      ("use_raytracing", True), ("use_shadows", True), ("taa_render_samples", 128)):              # EEVEE Next
        if hasattr(ev, prop):
            try: setattr(ev, prop, val)
            except Exception: pass

# ============================================================== main
def target_objects():
    sel = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    return sel or [o for o in bpy.context.scene.objects if o.type == 'MESH']


def main():
    objs = target_objects()
    if not objs:
        print("Refine: no mesh objects found."); return
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    for m in mats: rebuild_material(m)
    n = sum(1 for o in objs if refine_object(o))
    lo, hi = world_bounds(objs)
    setup_render(); setup_lights(lo, hi)
    setup_camera(lo, hi, centre_model(objs, (lo + hi) / 2))
    print("Refine: %d objects refined, %d materials rebuilt, lights + 85 mm camera placed, engine %s" % (n, len(mats), bpy.context.scene.render.engine))


if __name__ == "__main__":
    main()
