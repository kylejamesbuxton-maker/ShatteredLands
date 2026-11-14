import bpy

def create_landscape_material():
    mat = bpy.data.materials.new(name="Landscape_Procedural")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create Nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled_grass = nodes.new('ShaderNodeBsdfPrincipled')
    principled_rock = nodes.new('ShaderNodeBsdfPrincipled')
    mix_shader = nodes.new('ShaderNodeMixShader')
    geometry = nodes.new('ShaderNodeNewGeometry')
    separate_xyz = nodes.new('ShaderNodeSeparateXYZ')
    color_ramp = nodes.new('ShaderNodeValToRGB')

    # Set Base Colors (Grass vs Rock)
    principled_grass.inputs['Base Color'].default_value = (0.1, 0.4, 0.05, 1.0) # Green
    principled_rock.inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)  # Dark Grey

    # Calculate Slope using Normal Z vector
    links.new(geometry.outputs['Normal'], separate_xyz.inputs['Vector'])
    links.new(separate_xyz.outputs['Z'], color_ramp.inputs['Factor'])

    # Blend Grass on flat surfaces (Z close to 1) and Rock on steep slopes (Z close to 0)
    links.new(color_ramp.outputs['Color'], mix_shader.inputs['Factor'])
    links.new(principled_rock.outputs['BSDF'], mix_shader.inputs[1])
    links.new(principled_grass.outputs['BSDF'], mix_shader.inputs[2])
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])

# *Verification:* Check Shader Editor to ensure Normal Z drives the Mix Shader factor between grass and cliff rock.

create_landscape_material()
m = bpy.data.materials["Landscape_Procedural"]
print("LINKS", [(l.from_node.bl_idname, l.from_socket.identifier, "->", l.to_node.bl_idname, l.to_socket.identifier) for l in m.node_tree.links])
