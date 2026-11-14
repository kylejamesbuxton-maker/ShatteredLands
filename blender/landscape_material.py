import bpy


def create_landscape_material(grass_from=0.86, rock_below=0.72):
    """Grass on flat ground, rock on steep slopes, blended by the surface normal's Z.

    grass_from / rock_below: normal-Z thresholds for the colour ramp (1.0 = flat, 0.0 = vertical).
    0.86 is about a 30 degree slope, 0.72 about 44 degrees; between them the two shaders blend.
    """
    mat = bpy.data.materials.new(name="Landscape_Procedural")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # Create Nodes (laid out left to right so the Shader Editor reads cleanly)
    output = nodes.new('ShaderNodeOutputMaterial');           output.location = (600, 0)
    principled_grass = nodes.new('ShaderNodeBsdfPrincipled'); principled_grass.location = (100, -250); principled_grass.label = "Grass"
    principled_rock = nodes.new('ShaderNodeBsdfPrincipled');  principled_rock.location = (100, 350);   principled_rock.label = "Rock"
    mix_shader = nodes.new('ShaderNodeMixShader');            mix_shader.location = (400, 0)
    geometry = nodes.new('ShaderNodeNewGeometry');            geometry.location = (-700, 0)
    separate_xyz = nodes.new('ShaderNodeSeparateXYZ');        separate_xyz.location = (-500, 0)
    color_ramp = nodes.new('ShaderNodeValToRGB');             color_ramp.location = (-300, 0); color_ramp.label = "Slope"

    # Set Base Colors (Grass vs Rock)
    principled_grass.inputs['Base Color'].default_value = (0.1, 0.4, 0.05, 1.0)  # Green
    principled_rock.inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)    # Dark Grey
    principled_grass.inputs['Roughness'].default_value = 0.9
    principled_rock.inputs['Roughness'].default_value = 0.75

    # Tighten the ramp: below rock_below -> all rock (black), above grass_from -> all grass (white)
    color_ramp.color_ramp.elements[0].position = rock_below
    color_ramp.color_ramp.elements[1].position = grass_from

    # Calculate Slope using Normal Z vector (index 0 = the Fac/Factor input on Blender 4.x and 5.x alike)
    links.new(geometry.outputs['Normal'], separate_xyz.inputs[0])
    links.new(separate_xyz.outputs['Z'], color_ramp.inputs[0])

    # Blend Grass on flat surfaces (Z close to 1) and Rock on steep slopes (Z close to 0)
    links.new(color_ramp.outputs['Color'], mix_shader.inputs[0])
    links.new(principled_rock.outputs['BSDF'], mix_shader.inputs[1])
    links.new(principled_grass.outputs['BSDF'], mix_shader.inputs[2])
    links.new(mix_shader.outputs['Shader'], output.inputs['Surface'])
    return mat


if __name__ == "__main__":
    mat = create_landscape_material()
    ob = bpy.context.active_object
    if ob is not None and ob.type == 'MESH':                 # assign to the selected terrain, if any
        ob.data.materials.clear(); ob.data.materials.append(mat)
        print("Landscape_Procedural assigned to", ob.name)

# *Verification:* Check Shader Editor to ensure Normal Z drives the Mix Shader factor between grass and cliff rock.
