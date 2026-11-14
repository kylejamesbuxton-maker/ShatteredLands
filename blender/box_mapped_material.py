import bpy


def create_box_mapped_material(image, name="Wall_BoxMapped", tile=1.0, blend=0.2):
    """Image texture projected from all three axes (box mapping) so vertical walls don't stretch.

    image: a bpy.types.Image. tile: repeats per metre (Mapping scale). blend: softens the seams where
    two projections meet (0 = hard edge). Object coordinates are in the object's own space, so apply
    the object's scale (Ctrl+A > Scale) or the texture will stretch with it.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')

    # Set Image Texture to Box mapping to prevent vertical wall stretching
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = image
    tex_node.projection = 'BOX'
    tex_node.projection_blend = blend  # Blends edge seams smoothly

    # Link Object coordinates from Texture Coordinate node
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (tile, tile, tile)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], tex_node.inputs['Vector'])
    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])

    tex_coord.location, mapping.location, tex_node.location = (-900, 0), (-700, 0), (-450, 0)
    return mat

# *Verification:* View the building in Rendered mode; wall textures tile evenly on vertical faces without stretching.
