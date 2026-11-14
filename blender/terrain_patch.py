# Muddy cart-track terrain patch: dense grid + Voronoi/Musgrave displacement stack + procedural PBR shader + dead grass.
#   blender --background --python terrain_patch.py -- <out_dir>
import bpy, bmesh, sys, os, math, random
from mathutils import Vector, noise
out_dir = sys.argv[sys.argv.index("--") + 1]; os.makedirs(out_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(7)
SIZE, SUB = 20.0, 400                     # 20 m patch, 400x400 quads (5 cm)

# ---------------------------------------------------------------- dense grid
bpy.ops.mesh.primitive_grid_add(x_subdivisions=SUB, y_subdivisions=SUB, size=SIZE)
ter = bpy.context.active_object; ter.name = "TerrainPatch"; me = ter.data

# ---------------------------------------------------------------- masks (vertex groups), all noise-driven
def track_x(y): return math.sin(y * 0.16) * 2.6 + math.sin(y * 0.41 + 1.3) * 0.5   # gently wandering cart track
GAUGE, RUT_W = 0.74, 0.17
vg = {n: ter.vertex_groups.new(name=n) for n in ("ruts", "rutlips", "track", "troughs", "rocks", "grass")}
W = {n: [] for n in vg}
for v in me.vertices:
    x, y = v.co.x, v.co.y; p = Vector((x, y, 0))
    dx = x - track_x(y)
    # wheel ruts wobble in width and depth along their length (musgrave-style fractal)
    wob = noise.fractal(Vector((y * 0.35, 3.1, 0)), 0.8, 2.0, 4)
    r = 0.0; lip = 0.0
    for s in (-1, 1):
        d = abs(dx - s * (GAUGE + 0.06 * wob)); w = RUT_W * (1 + 0.35 * wob)
        r = max(r, math.exp(-(d / w) ** 2)); lip = max(lip, math.exp(-((d - w * 1.6) / (w * 0.7)) ** 2) * (d > w))
    track = math.exp(-(dx / 1.5) ** 4)
    # muddy troughs: low-frequency fractal pockets, strongest along the track
    t = noise.fractal(p * 0.22 + Vector((11, 4, 0)), 1.0, 2.1, 5)
    trough = max(0.0, min(1.0, (t - 0.05) * 2.2)) * (0.45 + 0.55 * track)
    # rocky outcrops: sparse fractal islands, kept off the track
    k = noise.fractal(p * 0.13 + Vector((-7, 19, 0)), 0.9, 2.0, 5)
    rock = max(0.0, min(1.0, (k - 0.28) * 3.5)) * (1 - track) ** 2
    # dead grass: patchy, on drier ground away from ruts, mud and rock
    gn = noise.fractal(p * 0.45 + Vector((5, -3, 0)), 0.9, 2.2, 4)
    grass = max(0.0, min(1.0, (gn + 0.1) * 2.5)) * (1 - trough) * (1 - rock) * (1 - track * 0.85)
    for n, val in (("ruts", r), ("rutlips", lip), ("track", track), ("troughs", trough), ("rocks", rock), ("grass", grass)):
        W[n].append(val)
for n, g in vg.items():
    vals = W[n]
    for i, val in enumerate(vals):
        if val > 0.002: g.add([i], val, 'REPLACE')

# ---------------------------------------------------------------- displacement stack (legacy Musgrave / Voronoi textures)
def tex(name, kind, **kw):
    t = bpy.data.textures.new(name, type=kind)
    for k, val in kw.items(): setattr(t, k, val)
    return t
def disp(name, t, strength, mid=0.5, group=None, coords='GLOBAL'):
    m = ter.modifiers.new(name, 'DISPLACE'); m.texture = t; m.strength = strength; m.mid_level = mid
    m.direction = 'Z'; m.texture_coords = coords
    if group: m.vertex_group = group
    return m
T_undul = tex("Musgrave_Undulation", 'MUSGRAVE', musgrave_type='FBM', noise_scale=5.5, octaves=6, lacunarity=2.0, dimension_max=0.9, noise_basis='BLENDER_ORIGINAL')
T_trough = tex("Voronoi_Troughs", 'VORONOI', distance_metric='DISTANCE', color_mode='INTENSITY', noise_scale=1.6, weight_1=1.0, weight_2=0.0, noise_intensity=1.0)
T_crack = tex("Voronoi_Outcrops", 'VORONOI', distance_metric='DISTANCE', color_mode='INTENSITY', noise_scale=1.15, weight_1=-0.6, weight_2=1.0, noise_intensity=1.0)
T_rockmus = tex("Musgrave_RockBreakup", 'MUSGRAVE', musgrave_type='RIDGED_MULTIFRACTAL', noise_scale=0.9, octaves=6, lacunarity=2.2, dimension_max=0.7, offset=1.0, gain=2.0, noise_basis='IMPROVED_PERLIN')
T_rutfloor = tex("Musgrave_RutFloor", 'MUSGRAVE', musgrave_type='HETERO_TERRAIN', noise_scale=0.6, octaves=5, lacunarity=2.0, dimension_max=1.0, offset=0.6, noise_basis='IMPROVED_PERLIN')
T_micro = tex("Musgrave_Micro", 'MUSGRAVE', musgrave_type='FBM', noise_scale=0.09, octaves=4, lacunarity=2.3, dimension_max=0.6, noise_basis='IMPROVED_PERLIN')
T_clods = tex("Voronoi_Clods", 'VORONOI', distance_metric='DISTANCE_SQUARED', color_mode='INTENSITY', noise_scale=0.12, weight_1=1.0, weight_2=0.0, noise_intensity=1.0)

disp("1 Undulation (Musgrave fBm)", T_undul, 0.55)
disp("2 Muddy troughs (Voronoi F1)", T_trough, -0.32, mid=0.0, group="troughs")
disp("3 Trampled track (Musgrave)", T_undul, -0.06, mid=0.0, group="track")
disp("4 Outcrops (Voronoi crackle)", T_crack, 0.42, mid=0.1, group="rocks")
disp("5 Outcrop breakup (ridged Musgrave)", T_rockmus, 0.1, mid=0.4, group="rocks")
disp("6 Cart ruts (hetero Musgrave)", T_rutfloor, -0.16, mid=0.0, group="ruts")
disp("7 Pushed-up rut lips (Voronoi clods)", T_clods, 0.06, mid=0.0, group="rutlips")
disp("8 Micro relief (Musgrave, everywhere)", T_micro, 0.022)
disp("9 Clods (Voronoi, everywhere)", T_clods, 0.012)
T_grain = tex("Musgrave_Grain", 'MUSGRAVE', musgrave_type='MULTIFRACTAL', noise_scale=0.031, octaves=3, lacunarity=2.7, dimension_max=0.5, noise_basis='VORONOI_F2_F1')
m10 = disp("10 Grain (Musgrave, object space)", T_grain, 0.006, coords='OBJECT')
em_ = bpy.data.objects.new("GrainSpace", None); bpy.context.collection.objects.link(em_); em_.rotation_euler = (0.37, 0.21, 0.83); em_.location = (0.113, -0.271, 0.05); m10.texture_coords_object = em_
for p in me.polygons: p.use_smooth = True

# ---------------------------------------------------------------- bake masks + height to colour attributes for the shader
dg = bpy.context.evaluated_depsgraph_get(); ev = ter.evaluated_get(dg); em = ev.to_mesh()
zs = [v.co.z for v in em.vertices]; zmin, zmax = min(zs), max(zs)
def add_attr(name, vals):
    a = me.attributes.new(name, 'FLOAT', 'POINT')
    for i, val in enumerate(vals): a.data[i].value = val
add_attr("height01", [(z - zmin) / (zmax - zmin) for z in zs])
add_attr("wet", [min(1.0, W["troughs"][i] * 1.2 + W["ruts"][i]) for i in range(len(zs))])
add_attr("rock", W["rocks"]); add_attr("grass", W["grass"])
# flat-plane check on the evaluated surface
em.calc_loop_triangles()
flat_up = sum(1 for p in em.polygons if p.normal.z > 0.999999)
bm = bmesh.new(); bm.from_mesh(em); bm.faces.ensure_lookup_table(); bm.normal_update()
coplanar = sum(1 for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) < 1e-5)
min_angle = min(e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) for e in bm.edges if len(e.link_faces) == 2)
print("FLATCHECK faces", len(bm.faces), "perfectly_level_faces", flat_up, "coplanar_neighbour_pairs", coplanar, "min_dihedral_rad %.2e" % min_angle, "relief_m %.3f" % (zmax - zmin))
bm.free(); ev.to_mesh_clear()

# ---------------------------------------------------------------- procedural PBR shader
mat = bpy.data.materials.new("CartTrackGround"); ter.data.materials.append(mat)
mat.use_nodes = True; nt = mat.node_tree; N, Lk = nt.nodes, nt.links
for n in list(N): N.remove(n)
def node(t, x, y, **kw):
    n = N.new(t); n.location = (x, y)
    for k, v in kw.items():
        if k in n.inputs: n.inputs[k].default_value = v
        else: setattr(n, k, v)
    return n
def _sock(n, key, outputs):
    coll = n.outputs if outputs else n.inputs
    if isinstance(key, int): return coll[key]
    if n.bl_idname == 'ShaderNodeMix':
        suffix = {'RGBA': 'Color', 'FLOAT': 'Float', 'VECTOR': 'Vector'}[n.data_type]
        ident = {'A': 'A_' + suffix, 'B': 'B_' + suffix, 'Result': 'Result_' + suffix, 'Factor': 'Factor_Float'}.get(key, key)
        for s in coll:
            if s.identifier == ident: return s
    return coll[key]
def L(a, ao, b, bi): Lk.new(_sock(a, ao, True), _sock(b, bi, False))
def setin(n, key, val): _sock(n, key, False).default_value = val
out = node('ShaderNodeOutputMaterial', 1800, 0); bsdf = node('ShaderNodeBsdfPrincipled', 1500, 0); L(bsdf, 0, out, 'Surface')
tc = node('ShaderNodeTexCoord', -1600, 0)
attr = {n: node('ShaderNodeAttribute', -1600, -300 - k * 160, attribute_name=n) for k, n in enumerate(("wet", "rock", "grass", "height01"))}
# damp earth: two browns broken up by fractal noise
n_earth = node('ShaderNodeTexNoise', -1300, 300, noise_dimensions='3D'); n_earth.inputs['Scale'].default_value = 1.8; n_earth.inputs['Detail'].default_value = 10; n_earth.inputs['Roughness'].default_value = 0.6
L(tc, 'Object', n_earth, 'Vector')
c_earth = node('ShaderNodeValToRGB', -1050, 300); c_earth.color_ramp.elements[0].color = (0.035, 0.024, 0.016, 1); c_earth.color_ramp.elements[1].color = (0.085, 0.06, 0.038, 1)
L(n_earth, 'Fac', c_earth, 'Fac')
# pebbles: small voronoi cells, each with its own tone and roughness
vp = node('ShaderNodeTexVoronoi', -1300, 0, feature='F1'); vp.inputs['Scale'].default_value = 26; vp.inputs['Randomness'].default_value = 1.0
L(tc, 'Object', vp, 'Vector')
peb_mask = node('ShaderNodeMapRange', -1050, 40); peb_mask.inputs['From Min'].default_value = 0.16; peb_mask.inputs['From Max'].default_value = 0.08
L(vp, 'Distance', peb_mask, 'Value')
peb_dens = node('ShaderNodeTexNoise', -1300, -180); peb_dens.inputs['Scale'].default_value = 0.7; L(tc, 'Object', peb_dens, 'Vector')
dens_r = node('ShaderNodeMapRange', -1050, -180); dens_r.inputs['From Min'].default_value = 0.45; dens_r.inputs['From Max'].default_value = 0.62
L(peb_dens, 'Fac', dens_r, 'Value')
peb = node('ShaderNodeMath', -850, 0, operation='MULTIPLY'); L(peb_mask, 'Result', peb, 0); L(dens_r, 'Result', peb, 1)
peb_tone = node('ShaderNodeSeparateColor', -1050, -60); L(vp, 'Color', peb_tone, 'Color')
peb_col = node('ShaderNodeValToRGB', -850, -120); peb_col.color_ramp.elements[0].color = (0.09, 0.08, 0.07, 1); peb_col.color_ramp.elements[1].color = (0.28, 0.25, 0.21, 1)
L(peb_tone, 0, peb_col, 'Fac')
# outcrop rock: grey stone with crack lines
n_rock = node('ShaderNodeTexNoise', -1300, -420); n_rock.inputs['Scale'].default_value = 6; n_rock.inputs['Detail'].default_value = 12; L(tc, 'Object', n_rock, 'Vector')
c_rock = node('ShaderNodeValToRGB', -1050, -420); c_rock.color_ramp.elements[0].color = (0.16, 0.15, 0.135, 1); c_rock.color_ramp.elements[1].color = (0.42, 0.4, 0.36, 1)
L(n_rock, 'Fac', c_rock, 'Fac')
vcr = node('ShaderNodeTexVoronoi', -1300, -620, feature='DISTANCE_TO_EDGE'); vcr.inputs['Scale'].default_value = 3.5; L(tc, 'Object', vcr, 'Vector')
crack = node('ShaderNodeMapRange', -1050, -620); crack.inputs['From Min'].default_value = 0.035; crack.inputs['From Max'].default_value = 0.0   # 1 on the crack lines only; L(vcr, 'Distance', crack, 'Value')
# dead grass: straw tones in noisy patches
n_gr = node('ShaderNodeTexNoise', -1300, -820); n_gr.inputs['Scale'].default_value = 9; n_gr.inputs['Detail'].default_value = 6; L(tc, 'Object', n_gr, 'Vector')
c_gr = node('ShaderNodeValToRGB', -1050, -820); c_gr.color_ramp.elements[0].color = (0.16, 0.12, 0.05, 1); c_gr.color_ramp.elements[1].color = (0.36, 0.29, 0.14, 1)
L(n_gr, 'Fac', c_gr, 'Fac')
gr_patch = node('ShaderNodeMath', -850, -820, operation='MULTIPLY'); L(attr["grass"], 'Fac', gr_patch, 0); L(n_gr, 'Fac', gr_patch, 1)
gr_mask = node('ShaderNodeMapRange', -650, -820); gr_mask.inputs['From Min'].default_value = 0.18; gr_mask.inputs['From Max'].default_value = 0.42; L(gr_patch, 'Value', gr_mask, 'Value')
# mud: darker, wetter where the ground is low
mud = node('ShaderNodeMix', -650, 300, data_type='RGBA'); setin(mud, 'B', (0.018, 0.012, 0.008, 1))
L(c_earth, 'Color', mud, 'A'); L(attr["wet"], 'Fac', mud, 'Factor')
m1 = node('ShaderNodeMix', -450, 200, data_type='RGBA'); L(mud, 'Result', m1, 'A'); L(peb_col, 'Color', m1, 'B'); L(peb, 'Value', m1, 'Factor')
rockf = node('ShaderNodeMath', -650, -450, operation='MULTIPLY'); L(attr["rock"], 'Fac', rockf, 0); rockf.inputs[1].default_value = 1.4
rockc = node('ShaderNodeMix', -450, -450, data_type='RGBA'); L(c_rock, 'Color', rockc, 'A'); setin(rockc, 'B', (0.06, 0.055, 0.05, 1)); L(crack, 'Result', rockc, 'Factor')
rockc.clamp_factor = True
m2 = node('ShaderNodeMix', -250, 100, data_type='RGBA', clamp_factor=True); L(m1, 'Result', m2, 'A'); L(rockc, 'Result', m2, 'B'); L(rockf, 'Value', m2, 'Factor')
m3 = node('ShaderNodeMix', -50, 0, data_type='RGBA'); L(m2, 'Result', m3, 'A'); L(c_gr, 'Color', m3, 'B'); L(gr_mask, 'Result', m3, 'Factor')
L(m3, 'Result', bsdf, 'Base Color')
# roughness: glossy wet mud, varied pebbles, matte rock and grass
r_base = node('ShaderNodeMapRange', -450, -150); r_base.inputs['To Min'].default_value = 0.88; r_base.inputs['To Max'].default_value = 0.16; L(attr["wet"], 'Fac', r_base, 'Value')
r_peb = node('ShaderNodeMapRange', -450, -300); r_peb.inputs['To Min'].default_value = 0.35; r_peb.inputs['To Max'].default_value = 0.85; L(peb_tone, 1, r_peb, 'Value')
rm1 = node('ShaderNodeMix', -250, -200, data_type='FLOAT'); L(r_base, 'Result', rm1, 'A'); L(r_peb, 'Result', rm1, 'B'); L(peb, 'Value', rm1, 'Factor')
rm2 = node('ShaderNodeMix', -50, -250, data_type='FLOAT', clamp_factor=True); L(rm1, 'Result', rm2, 'A'); setin(rm2, 'B', 0.8); L(rockf, 'Value', rm2, 'Factor')
rm3 = node('ShaderNodeMix', 150, -250, data_type='FLOAT'); L(rm2, 'Result', rm3, 'A'); setin(rm3, 'B', 0.95); L(gr_mask, 'Result', rm3, 'Factor')
L(rm3, 'Result', bsdf, 'Roughness')
# bump: pebble domes + earth grain + rock cracks, softened in liquid mud
bh = node('ShaderNodeMath', 150, -500, operation='ADD'); L(peb, 'Value', bh, 0); L(n_earth, 'Fac', bh, 1)
crk_r = node('ShaderNodeMath', 150, -650, operation='MULTIPLY', use_clamp=True); L(crack, 'Result', crk_r, 0); L(rockf, 'Value', crk_r, 1)
bh2 = node('ShaderNodeMath', 350, -500, operation='SUBTRACT'); L(bh, 'Value', bh2, 0); L(crk_r, 'Value', bh2, 1)
bump = node('ShaderNodeBump', 1200, -400); bump.inputs['Strength'].default_value = 0.45; bump.inputs['Distance'].default_value = 0.02
L(bh2, 'Value', bump, 'Height'); L(bump, 'Normal', bsdf, 'Normal')
bsdf.inputs['Specular IOR Level'].default_value = 0.5

# ---------------------------------------------------------------- dead grass clumps scattered on the "grass" mask
bm = bmesh.new()
for b in range(7):
    a = b / 7 * math.pi * 2 + random.uniform(-.3, .3); lean = random.uniform(0.25, 0.7); h = random.uniform(0.12, 0.26)
    base = Vector((math.cos(a) * 0.012, math.sin(a) * 0.012, 0)); tip = base + Vector((math.cos(a) * lean * h, math.sin(a) * lean * h, h))
    side = Vector((-math.sin(a), math.cos(a), 0)) * 0.004
    v1, v2, v3 = bm.verts.new(base - side), bm.verts.new(base + side), bm.verts.new(tip)
    bm.faces.new((v1, v2, v3))
cm = bpy.data.meshes.new("DeadGrassClump"); bm.to_mesh(cm); bm.free()
clump = bpy.data.objects.new("DeadGrassClump", cm); bpy.context.collection.objects.link(clump); clump.location = (0, 0, -50); clump.hide_render = False
gm = bpy.data.materials.new("DeadGrass"); gm.use_nodes = True; gb = gm.node_tree.nodes["Principled BSDF"]
gb.inputs["Base Color"].default_value = (0.3, 0.23, 0.1, 1); gb.inputs["Roughness"].default_value = 0.9
try: gm.surface_render_method = 'DITHERED'
except Exception: pass
cm.materials.append(gm)
ps_mod = ter.modifiers.new("DeadGrass", 'PARTICLE_SYSTEM'); ps = ps_mod.particle_system; st = ps.settings
st.type = 'HAIR'; st.count = 26000; st.hair_length = 1.0; st.render_type = 'OBJECT'; st.instance_object = clump
st.use_rotations = True; st.rotation_mode = 'OB_Z'; st.phase_factor_random = 2.0; st.particle_size = 1.0; st.size_random = 0.6
st.use_advanced_hair = True; st.use_modifier_stack = True
ps.vertex_group_density = "grass"

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "terrain_patch.blend"))
print("SAVED_TERRAIN")
