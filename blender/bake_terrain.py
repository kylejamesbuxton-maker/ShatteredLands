# Bakes terrain_patch.blend into game assets: height grid + albedo / tangent normal / roughness maps.
# Normals are baked from the 160k-face displaced mesh onto a coarse game-resolution copy, so the
# normal map carries exactly the detail the game mesh can't (ruts' edges, clods, pebbles, cracks).
import bpy, bmesh, sys, os, json, struct
out_dir = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "terrain_patch.blend"))
ter = bpy.data.objects["TerrainPatch"]
for m in ter.modifiers:
    if m.type == 'PARTICLE_SYSTEM': m.show_render = m.show_viewport = False
SIZE, HN, LOWN, RES = 20.0, 201, 56, 1024
dg = bpy.context.evaluated_depsgraph_get(); ev = ter.evaluated_get(dg); em = ev.to_mesh()
# ---- height grid (HN x HN), row-major by +y then +x, metres
grid = [[0.0] * HN for _ in range(HN)]; cnt = [[0] * HN for _ in range(HN)]
for v in em.vertices:
    i = round((v.co.x + SIZE / 2) / SIZE * (HN - 1)); j = round((v.co.y + SIZE / 2) / SIZE * (HN - 1))
    if 0 <= i < HN and 0 <= j < HN: grid[j][i] += v.co.z; cnt[j][i] += 1
flat = [grid[j][i] / max(1, cnt[j][i]) for j in range(HN) for i in range(HN)]
zmin, zmax = min(flat), max(flat)
with open(os.path.join(out_dir, "terrain_height.bin"), "wb") as fh:
    fh.write(struct.pack("<%dH" % len(flat), *[round((z - zmin) / (zmax - zmin) * 65535) for z in flat]))
json.dump({"n": HN, "size_m": SIZE, "zmin": zmin, "zmax": zmax}, open(os.path.join(out_dir, "terrain_height.json"), "w"))
def h_at(x, y):
    fx = (x + SIZE / 2) / SIZE * (HN - 1); fy = (y + SIZE / 2) / SIZE * (HN - 1)
    i0, j0 = max(0, min(HN - 2, int(fx))), max(0, min(HN - 2, int(fy))); tx, ty = fx - i0, fy - j0
    g = lambda i, j: flat[j * HN + i]
    return (g(i0, j0) * (1 - tx) + g(i0 + 1, j0) * tx) * (1 - ty) + (g(i0, j0 + 1) * (1 - tx) + g(i0 + 1, j0 + 1) * tx) * ty
ev.to_mesh_clear()
# ---- coarse "game mesh" copy (~36 cm spacing) carrying the same UVs
bpy.ops.mesh.primitive_grid_add(x_subdivisions=LOWN, y_subdivisions=LOWN, size=SIZE)
low = bpy.context.active_object; low.name = "BakeTarget"
for v in low.data.vertices: v.co.z = h_at(v.co.x, v.co.y)
for p in low.data.polygons: p.use_smooth = True
mat = ter.data.materials[0]; low.data.materials.append(mat)   # same material; bake image node lives in it
nt = mat.node_tree
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 16
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.25; bk.max_ray_distance = 0.6; bk.margin = 4
def bake(kind, name, res, **kw):
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    if kind == 'NORMAL': img.colorspace_settings.name = 'Non-Color'
    if kind == 'ROUGHNESS': img.colorspace_settings.name = 'Non-Color'
    n = nt.nodes.new('ShaderNodeTexImage'); n.image = img; nt.nodes.active = n
    bpy.ops.object.select_all(action='DESELECT'); ter.select_set(True); low.select_set(True); bpy.context.view_layer.objects.active = low
    if kind == 'DIFFUSE': bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
    if kind == 'NORMAL': bk.normal_space = 'TANGENT'
    bpy.ops.object.bake(type=kind)
    img.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    path = os.path.join(out_dir, name + ".jpg"); img.save_render(path) if False else None
    img.filepath_raw = path; img.file_format = 'JPEG'; img.save()
    nt.nodes.remove(n); print("BAKED", kind, path, os.path.getsize(path))
bake('DIFFUSE', "terrain_albedo", RES)
bake('NORMAL', "terrain_normal", RES)
bake('ROUGHNESS', "terrain_rough", 512)
print("HEIGHT", HN, "zmin %.3f zmax %.3f" % (zmin, zmax))
