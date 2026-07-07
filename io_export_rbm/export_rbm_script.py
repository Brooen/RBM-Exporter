import bpy
import bmesh
import struct
import math
import mathutils
import os

def get_image_from_input(input_socket):
    if input_socket.is_linked:
        from_node = input_socket.links[0].from_node
        if from_node.type == 'TEX_IMAGE':
            return from_node.image.name
    return None

import os

def get_texture_paths(material, group_name):
    texture_names_by_group = {
        'CARPAINTMM': [
            'DiffuseMap', 'NormalMap', 'PropertyMap', 'TintMap', 'DamageNormalMap',
            'DamageAlbedoMap', 'DirtMap', 'DecalAlbedoMap', 'DecalNormalMap',
            'DecalPropertyMap', 'LayeredAlbedoMap', 'OverlayAlbedoMap'
        ],
        'WINDOW': [
            'DiffuseMap', 'NormalMap', 'PropertyMap', 'DamagePointNormal', 
            'DamagePointProperty', 'DamageTileNormal', 'DamageTileProperty'
        ],
        'CARLIGHT': [
            'DiffuseMap', 'NormalMap', 'PropertyMap', 'UNKNOWN', 'NormalDetailMap', 
            'EmmisiveMap'
        ]
    }

    texture_paths = []

    if not material.node_tree:
        return texture_paths

    node_tree = material.node_tree
    node_group = None

    # Locate the node group within the material
    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.name == group_name:
            node_group = node
            break

    if node_group:
        for texture_name in texture_names_by_group.get(group_name, []):
            texture_path_input = f"{texture_name} Path"
            texture_path = ""
            image_name = ""

            # Find the texture path (directory)
            for input in node_group.inputs:
                if input.name == texture_path_input:
                    texture_path = input.default_value.strip()  # Get the texture folder and remove extra spaces
                    break

            # Find the image file name (if connected)
            for input in node_group.inputs:
                if input.name == texture_name:
                    image_name = get_image_from_input(input)  # Get the image file
                    if image_name:
                        image_name, _ = os.path.splitext(image_name)  # Remove extension
                        image_name = f"{image_name}.ddsc"  # Ensure .ddsc extension
                    break

            # Combine texture path and image name, enforcing forward slashes
            full_path = f"{texture_path}/{image_name}" if image_name else texture_path
            full_path = full_path.replace("\\", "/")  # Ensure forward slashes

            # Ensure entry is always included, even if path is empty
            path_length = len(full_path.encode('utf-8')) if full_path else 0
            texture_paths.append((path_length, full_path))

    return texture_paths





def get_node_values(material, group_name):
    node_values = {}
    node_tree = material.node_tree
    node_group = None
    
    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.name == group_name:
            node_group = node
            break

    if node_group:
        for input in node_group.inputs:
            if input.type == 'VALUE':
                node_values[input.name] = input.default_value
            elif input.type == 'VECTOR':
                node_values[input.name] = tuple(input.default_value)
    
    return node_values

def get_color_values(material, group_name):
    color_values = {}
    node_tree = material.node_tree
    node_group = None

    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.name == group_name:
            node_group = node
            break

    if node_group:
        for input in node_group.inputs:
            if input.type == 'RGBA':
                color_values[input.name] = tuple(input.default_value)

    return color_values

def get_boolean_values(material, group_name):
    boolean_values = {}
    node_tree = material.node_tree
    node_group = None
    
    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.name == group_name:
            node_group = node
            break

    if node_group:
        for input in node_group.inputs:
            if input.type == 'BOOLEAN':
                boolean_values[input.name] = input.default_value
    
    return boolean_values

def calculate_flags(material):
    flags = {
        'SUPPORT_DECALS': 0x1,
        'SUPPORT_DAMAGE_BLEND': 0x2,
        'SUPPORT_DIRT': 0x4,
        'SUPPORT_PALETTE_FILE': 0x8,
        'SUPPORT_SOFT_TINT': 0x10,
        'SUPPORT_LAYERED': 0x20,
        'SUPPORT_OVERLAY': 0x40,
        'DISABLE_BACKFACE_CULLING': 0x80,
        'TRANSPARENCY_ALPHABLENDING': 0x100,
        'TRANSPARENCY_ALPHATESTING': 0x200,
        'IS_DEFORM': 0x1000,
        'IS_SKINNED': 0x2000,
    }

    flag_value = 0
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree.name == 'CARPAINTMM':
                for input in node.inputs:
                    if input.name in flags and input.default_value:
                        flag_value += flags[input.name]
    return flag_value

def compress_normal(vec):
    x = math.floor((vec.x + 1.0) * 127.0) / 256.0
    y = math.floor((vec.y + 1.0) * 127.0)
    z = math.floor((vec.z + 1.0) * 127.0) * 256.0
    return x + y + z

def process_object(obj, supported_nodegroups):
    """Return a list of render-block dicts, one per material slot on this
    object that uses a supported node group. Geometry is split by
    face.material_index so each block only contains its own triangles."""
    if obj.type != 'MESH':
        print(f"Object {obj.name} is not a mesh, skipping.")
        return []

    mesh = obj.data
    if not mesh.materials:
        print(f"Object {obj.name} has no material slots.")
        return []

    # Build a triangulated, rotated copy of the mesh once.
    mesh_copy = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh_copy)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    rotation_matrix = mathutils.Matrix.Rotation(-math.pi / 2, 4, 'X')

    for v in bm.verts:
        v.co = rotation_matrix @ v.co

    bm.to_mesh(mesh_copy)
    bm.free()
    mesh_copy.update()

    bm = bmesh.new()
    bm.from_mesh(mesh_copy)
    bm.verts.ensure_lookup_table()

    # Global per-vertex data (indexed by vertex index).
    vertices = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]

    uv1 = [(0, 0)] * len(vertices)
    uv2 = [(0, 0)] * len(vertices)
    uv3 = [(0, 0)] * len(vertices)
    normals = [0.0] * len(vertices)
    tangents = [0.0] * len(vertices)

    uv_layers = bm.loops.layers.uv
    uv1_layer = uv_layers[0] if len(uv_layers) > 0 else None
    uv2_layer = uv_layers[1] if len(uv_layers) > 1 else None
    uv3_layer = uv_layers[2] if len(uv_layers) > 2 else None

    for face in bm.faces:
        for loop in face.loops:
            idx = loop.vert.index
            if uv1_layer:
                uv = loop[uv1_layer].uv
                uv1[idx] = (uv.x, -uv.y)
            if uv2_layer:
                uv = loop[uv2_layer].uv
                uv2[idx] = (uv.x, -uv.y)
            if uv3_layer:
                uv = loop[uv3_layer].uv
                uv3[idx] = (uv.x, -uv.y)

    for loop in mesh_copy.loops:
        idx = loop.vertex_index
        normal = loop.normal
        tangent = loop.tangent
        bitangent_sign = -loop.bitangent_sign

        normals[idx] = compress_normal(normal)
        tangents[idx] = math.copysign(compress_normal(tangent), -bitangent_sign)

    # Group triangles by the material slot they belong to.
    faces_by_material = {}
    for face in bm.faces:
        faces_by_material.setdefault(face.material_index, []).append(
            tuple(vert.index for vert in face.verts)
        )

    bm.free()

    objects_data = []

    # Emit one render block per material slot with a supported node group.
    for material_index, mat_faces in sorted(faces_by_material.items()):
        if material_index >= len(mesh.materials):
            continue
        material = mesh.materials[material_index]
        if material is None:
            print(f"Object {obj.name}: material slot {material_index} is empty, skipping.")
            continue

        node_group_name = None
        if material.use_nodes and material.node_tree:
            for node in material.node_tree.nodes:
                if (node.type == 'GROUP' and node.node_tree
                        and node.node_tree.name in supported_nodegroups):
                    node_group_name = node.node_tree.name
                    break

        if not node_group_name:
            print(f"Object {obj.name}: material '{material.name}' has no supported "
                  f"node group, skipping this slot.")
            continue

        # Remap global vertex indices down to just those used by this slot,
        # so each block has a compact, self-contained vertex buffer.
        remap = {}
        local_faces = []
        for tri in mat_faces:
            new_tri = []
            for old_idx in tri:
                new_idx = remap.get(old_idx)
                if new_idx is None:
                    new_idx = len(remap)
                    remap[old_idx] = new_idx
                new_tri.append(new_idx)
            local_faces.append(tuple(new_tri))

        ordered = sorted(remap.items(), key=lambda kv: kv[1])
        local_vertices = [vertices[old] for old, _ in ordered]
        local_uv1 = [uv1[old] for old, _ in ordered]
        local_uv2 = [uv2[old] for old, _ in ordered]
        local_uv3 = [uv3[old] for old, _ in ordered]
        local_normals = [normals[old] for old, _ in ordered]
        local_tangents = [tangents[old] for old, _ in ordered]

        flags_value = calculate_flags(material)
        texture_paths = get_texture_paths(material, node_group_name)
        node_values = get_node_values(material, node_group_name)
        color_values = get_color_values(material, node_group_name)
        boolean_values = get_boolean_values(material, node_group_name)

        print(f"Object: {obj.name}, Slot {material_index} ('{material.name}'), "
              f"Node Group: {node_group_name}, Verts: {len(local_vertices)}, "
              f"Tris: {len(local_faces)}, Flags: {flags_value:#010x}")

        objects_data.append({
            'vertices': local_vertices,
            'flags_value': flags_value,
            'texture_paths': texture_paths,
            'normals': local_normals,
            'tangents': local_tangents,
            'uv1': local_uv1,
            'uv2': local_uv2,
            'uv3': local_uv3,
            'faces': local_faces,
            'face_indices_count': len(local_faces) * 3,
            'node_group_name': node_group_name,
            'node_values': node_values,
            'color_values': color_values,
            'boolean_values': boolean_values,
        })

    if not objects_data:
        print(f"No supported materials found on {obj.name}.")

    return objects_data

def calculate_global_min_max(objects_data):
    all_vertices = [v for obj_data in objects_data for v in obj_data['vertices']]
    min_x = min(v[0] for v in all_vertices)
    min_y = min(v[1] for v in all_vertices)
    min_z = min(v[2] for v in all_vertices)
    max_x = max(v[0] for v in all_vertices)
    max_y = max(v[1] for v in all_vertices)
    max_z = max(v[2] for v in all_vertices)
    return min_x, min_y, min_z, max_x, max_y, max_z

def write_to_file(file_path, objects_data, min_max_positions):
    print("Writing data to file...")
    with open(file_path, "wb") as f:
        header = bytes.fromhex("0500000052424D444C010000001000000000000000")
        f.write(header)

        f.write(struct.pack('<6f', *min_max_positions))

        f.write(struct.pack('<I', len(objects_data)))

        f.write(struct.pack('<I', 8))

        for obj_data in objects_data:
            print(f"Writing data for object with node group {obj_data['node_group_name']}")

            if obj_data['node_group_name'] == 'CARPAINTMM':
                additional_block_start = bytes.fromhex("D60433480E")
                f.write(additional_block_start)
                f.write(struct.pack('<I', obj_data['flags_value']))
                f.write(struct.pack('<f', 1.0))
                
                node_values = obj_data['node_values']
                color_values = obj_data['color_values']
                boolean_values = obj_data['boolean_values']
                specular_gloss = struct.pack('<4f', *node_values.get('SpecularGloss', (0.0, 0.0, 0.0, 0.0)))
                metallic = struct.pack('<4f', *node_values.get('Metallic', (0.0, 0.0, 0.0, 0.0)))
                clearcoat = struct.pack('<4f', *node_values.get('ClearCoat', (0.0, 0.0, 0.0, 0.0)))
                emissive = struct.pack('<4f', *node_values.get('Emissive', (0.0, 0.0, 0.0, 0.0)))
                diffuse_wrap = struct.pack('<4f', *node_values.get('DiffuseWrap', (0.0, 0.0, 0.0, 0.0)))
                dirt_params = struct.pack('<4f', *node_values.get('DirtParams', (0.0, 0.0, 0.0, 0.0)))
                dirt_blend = struct.pack('<4f', *node_values.get('DirtBlend', (0.0, 0.0, 0.0, 0.0)))
                dirt_color = struct.pack('<4f', *color_values.get('DirtColor', (0.0, 0.0, 0.0, 0.0)))
                decal_count = struct.pack('<4f', *node_values.get('DecalCount', (0.0, 0.0, 0.0, 0.0)))
                decal_width = struct.pack('<4f', *node_values.get('DecalWidth', (0.0, 0.0, 0.0, 0.0)))
                decal_blend = struct.pack('<4f', *node_values.get('DecalBlend', (0.0, 0.0, 0.0, 0.0)))
                decal1_color = struct.pack('<4f', *color_values.get('Decal1Color', (0.0, 0.0, 0.0, 0.0)))
                decal2_color = struct.pack('<4f', *color_values.get('Decal2Color', (0.0, 0.0, 0.0, 0.0)))
                decal3_color = struct.pack('<4f', *color_values.get('Decal3Color', (0.0, 0.0, 0.0, 0.0)))
                decal4_color = struct.pack('<4f', *color_values.get('Decal4Color', (0.0, 0.0, 0.0, 0.0)))
                damage = struct.pack('<4f', *node_values.get('Damage', (0.0, 0.0, 0.0, 0.0)))
                damage_blend = struct.pack('<4f', *node_values.get('DamageBlend', (0.0, 0.0, 0.0, 0.0)))
                damage_color = struct.pack('<4f', *color_values.get('DamageColor', (0.0, 0.0, 0.0, 0.0)))
                f.write(specular_gloss)
                f.write(metallic)
                f.write(clearcoat)
                f.write(emissive)
                f.write(diffuse_wrap)
                f.write(dirt_params)
                f.write(dirt_blend)
                f.write(dirt_color)
                f.write(decal_count)
                f.write(decal_width)
                f.write(decal1_color)
                f.write(decal2_color)
                f.write(decal3_color)
                f.write(decal4_color)
                f.write(decal_blend)
                f.write(damage)
                f.write(damage_blend)
                f.write(damage_color)
                if boolean_values.get('SUPPORT_DECALS') == False:
                    f.write(bytes([0x00, 0x00, 0x00, 0x00]))
                else: 
                    f.write(bytes([0x00, 0x00, 0x80, 0x3F]))
                if boolean_values.get('SUPPORT_DAMAGE_BLEND') == False:
                    f.write(bytes([0x00, 0x00, 0x00, 0x00]))
                else: 
                    f.write(bytes([0x00, 0x00, 0x80, 0x3F])) 
                f.write(bytes([0x00, 0x00, 0x00, 0x00])) # support layered, always on
                f.write(bytes([0x00] * 8)) # suport overlay and rotation, always off
                if boolean_values.get('SUPPORT_DIRT') == False:
                    f.write(bytes([0x00, 0x00, 0x00, 0x00]))
                else: 
                    f.write(bytes([0x00, 0x00, 0x80, 0x40]))
                if boolean_values.get('SUPPORT_SOFT_TINT') == False:
                    f.write(bytes([0x00, 0x00, 0x00, 0x00]))
                else: 
                    f.write(bytes([0x00, 0x00, 0x80, 0x41]))                                                            
                f.write(bytes([0x00] * 76))
                f.write(bytes([0x00] * 1024))
                f.write(bytes([0x0C, 0x00, 0x00, 0x00]))

                for path_length, path in obj_data['texture_paths']:
                    f.write(struct.pack('<I', path_length))
                    if path_length > 0:
                        f.write(path.encode('utf-8'))

                f.write(bytes([0x00] * 16))
                f.write(struct.pack('<I', len(obj_data['vertices'])))

                for v in obj_data['vertices']:
                    f.write(struct.pack('<3f', *v))

                f.write(struct.pack('<I', len(obj_data['vertices'])))
                for u1, u2, n, t in zip(obj_data['uv1'], obj_data['uv2'], obj_data['normals'], obj_data['tangents']):
                    f.write(struct.pack('<2f', *u1))
                    f.write(struct.pack('<2f', *u2))
                    f.write(struct.pack('<f', n))
                    f.write(struct.pack('<f', t))

                f.write(struct.pack('<I', len(obj_data['vertices'])))
                for u3 in obj_data['uv3']:
                    f.write(struct.pack('<2f', *u3))

                f.write(struct.pack('<I', obj_data['face_indices_count']))

                for face in obj_data['faces']:
                    f.write(struct.pack('<3H', *face))

                f.write(bytes.fromhex("EFCDAB89"))
            
            if obj_data['node_group_name'] == 'BAVARIUMSHIELD':
                additional_block_start = bytes.fromhex("CD4CD2A501A5A4243EABAA2A3FAFAE2E3FCDCCCC3D010000002500000074657874757265732F64756D6D6965732F64756D6D795F616C7068615F6469662E64647363F0EE113D000080470000804700000000")
                f.write(additional_block_start)

                f.write(struct.pack('<I', len(obj_data['vertices'])))

                for v, u1, n, t in zip(obj_data['vertices'], obj_data['uv1'], obj_data['normals'], obj_data['tangents']):
                    f.write(struct.pack('<3f', *v))
                    f.write(struct.pack('<2f', *u1))
                    f.write(struct.pack('<f', n))
                    f.write(struct.pack('<f', t))

                f.write(struct.pack('<I', obj_data['face_indices_count']))

                for face in obj_data['faces']:
                    f.write(struct.pack('<3H', *face))

                f.write(bytes.fromhex("EFCDAB89"))
                
            if obj_data['node_group_name'] == 'WATERHULL':
                additional_block_start = bytes.fromhex("A1729CF90100000000D0EEF93D000080470000804700000000")
                f.write(additional_block_start)

                f.write(struct.pack('<I', len(obj_data['vertices'])))

                for v in obj_data['vertices']:
                    f.write(struct.pack('<3f', *v))

                f.write(struct.pack('<I', obj_data['face_indices_count']))

                for face in obj_data['faces']:
                    f.write(struct.pack('<3H', *face))

                f.write(bytes.fromhex("EFCDAB89"))
                
            if obj_data['node_group_name'] == 'WINDOW':
                additional_block_start = bytes.fromhex("F603205B01")
                f.write(additional_block_start)

                node_values = obj_data['node_values']
                specular_gloss = struct.pack('<f', node_values.get('SpecularGloss', 0.0))
                specular_fresnel = struct.pack('<f', node_values.get('SpecularFresnel', 0.0))
                diffuse_roughness = struct.pack('<f', node_values.get('DiffuseRoughness', 0.0))
                tint_power = struct.pack('<f', node_values.get('TintPower', 0.0))
                min_alpha = struct.pack('<f', node_values.get('MinAlpha', 0.0))
                uvscale = struct.pack('<f', node_values.get('UVScale', 0.0))

                f.write(specular_gloss)
                f.write(specular_fresnel)
                f.write(diffuse_roughness)
                f.write(tint_power)
                f.write(min_alpha)
                f.write(uvscale)
                unkownf4 = bytes.fromhex("30 80 D6 BE 9A D9 D0 3F 4C 4F 68 BE 00 00 00 00")
                f.write(unkownf4)

                f.write(bytes([0x07, 0x00, 0x00, 0x00]))

                for path_length, path in obj_data['texture_paths']:
                    f.write(struct.pack('<I', path_length))
                    if path_length > 0:
                        f.write(path.encode('utf-8'))

                f.write(bytes([0x00] * 16))

                # Debugging: Print lengths of all lists
                print(f"Number of vertices: {len(obj_data['vertices'])}")
                print(f"Number of UV1s: {len(obj_data['uv1'])}")
                print(f"Number of UV2s: {len(obj_data['uv2'])}")
                print(f"Number of normals: {len(obj_data['normals'])}")
                print(f"Number of tangents: {len(obj_data['tangents'])}")
                print(f"Number of color values: {len(obj_data['color_values'])}")

                f.write(struct.pack('<I', len(obj_data['vertices'])))

                # Assuming color_values are floats in the range 0.0 to 1.0
                float_color_values = obj_data['color_values'].get('ColorAndAlpha', (0.0, 0.0, 0.0, 0.0))
                int_color_values = [int(255 * value) for value in float_color_values]  # Convert float to int (0-255)
                color = struct.pack('<4B', *int_color_values)

                for v, u1, u2, n, t in zip(obj_data['vertices'], obj_data['uv1'], obj_data['uv2'], obj_data['normals'], obj_data['tangents']):
                    f.write(struct.pack('<3f', *v))
                    f.write(struct.pack('<2f', *u1))
                    f.write(struct.pack('<2f', *u2))
                    f.write(struct.pack('<f', n))
                    f.write(struct.pack('<f', t))
                    f.write(color)

                f.write(struct.pack('<I', obj_data['face_indices_count']))

                for face in obj_data['faces']:
                    f.write(struct.pack('<3H', *face))

                f.write(bytes.fromhex("EFCDAB89"))
                
            if obj_data['node_group_name'] == 'CARLIGHT':
                additional_block_start = bytes.fromhex("F1 8B 94 DB 01")
                f.write(additional_block_start)
                
                node_values = obj_data['node_values']
                color_values = obj_data['color_values']
                specular_gloss = struct.pack('<f', node_values.get('SpecularGloss', 0.0))
                reflectivity = struct.pack('<f', node_values.get('Reflectivity', 0.0))
                specular_fresnel = struct.pack('<f', node_values.get('SpecularFresnel', 0.0)) 
                diffuse_modulator = struct.pack('<4f', *color_values.get('DiffuseModulator', (0.0, 0.0, 0.0, 0.0)))              
                tilingx = struct.pack('<f', node_values.get('TilingX', 0.0))
                tilingy = struct.pack('<f', node_values.get('TilingY', 0.0))
                f.write(bytes([0x00] * 4))
                f.write(specular_gloss)
                f.write(reflectivity)
                f.write(bytes([0x00] * 16))
                f.write(specular_fresnel)
                f.write(diffuse_modulator)
                f.write(tilingx)
                f.write(tilingy)
                f.write(bytes([0x00] * 1028))
                f.write(bytes([0x06, 0x00, 0x00, 0x00]))

                for path_length, path in obj_data['texture_paths']:
                    f.write(struct.pack('<I', path_length))
                    if path_length > 0:
                        f.write(path.encode('utf-8'))

                f.write(bytes([0x00] * 16))

                f.write(struct.pack('<I', len(obj_data['vertices'])))

                for v in obj_data['vertices']:
                    f.write(struct.pack('<3f', *v))

                f.write(struct.pack('<I', len(obj_data['vertices'])))
                for u1, u2, n, t in zip(obj_data['uv1'], obj_data['uv2'], obj_data['normals'], obj_data['tangents']):
                    f.write(struct.pack('<2f', *u1))
                    f.write(struct.pack('<2f', *u2))
                    f.write(struct.pack('<f', n))
                    f.write(struct.pack('<f', t))

                f.write(struct.pack('<I', obj_data['face_indices_count']))

                for face in obj_data['faces']:
                    f.write(struct.pack('<3H', *face))

                f.write(bytes.fromhex("EFCDAB89"))

    print(f"Data exported to {file_path}")
