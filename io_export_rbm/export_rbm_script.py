import bpy
import bmesh
import struct
import math
import mathutils

def get_image_from_input(input_socket):
    if input_socket.is_linked:
        from_node = input_socket.links[0].from_node
        if from_node.type == 'TEX_IMAGE':
            return from_node.image.name
    return None

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

    base_path = ''
    texture_paths = []

    if not material.node_tree:
        return texture_paths
    
    node_tree = material.node_tree
    node_group = None
    
    for node in node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.name == group_name:
            node_group = node
            break
    
    if node_group:
        for input in node_group.inputs:
            if input.name == 'Base Path':
                base_path = input.default_value
                break

        texture_names = texture_names_by_group.get(group_name, [])
        for texture_name in texture_names:
            path_length = 0
            path = ''
            for input in node_group.inputs:
                if input.name == texture_name:
                    image_name = get_image_from_input(input)
                    if image_name:
                        # Remove the current extension and change it to .ddsc
                        base_name, _ = os.path.splitext(image_name)
                        new_image_name = f"{base_name}.ddsc"
                        path = f"{base_path}/{new_image_name}"
                        path_length = len(path.encode('utf-8'))
            texture_paths.append((path_length, path))
    
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
    material = obj.active_material
    if material is None:
        print(f"Object {obj.name} has no material.")
        return None

    node_group_name = None
    if material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree.name in supported_nodegroups:
                node_group_name = node.node_tree.name
                break

    if not node_group_name:
        print(f"No supported node group found in the material of {obj.name}.")
        return None

    flags_value = calculate_flags(material)
    print(f"Object: {obj.name}, Node Group: {node_group_name}, Calculated flags value: {flags_value:#010x}")

    texture_paths = get_texture_paths(material, node_group_name)
    print(f"Object: {obj.name}, Texture paths:")
    for length, path in texture_paths:
        print(f"Length: {length}, Path: {path}")

    node_values = get_node_values(material, node_group_name)
    print(f"Object: {obj.name}, Node values:")
    for name, value in node_values.items():
        print(f"Name: {name}, Value: {value}")

    color_values = get_color_values(material, node_group_name)
    print(f"Object: {obj.name}, Color values:")
    for name, value in color_values.items():
        print(f"Name: {name}, Value: {value}")

    boolean_values = get_boolean_values(material, node_group_name)
    print(f"Object: {obj.name}, Boolean values:")
    for name, value in boolean_values.items():
        print(f"Name: {name}, Value: {value}")

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

    faces = [tuple(vert.index for vert in face.verts) for face in bm.faces]
    face_indices_count = len(faces) * 3

    bm.free()

    object_data = {
        'vertices': vertices,
        'flags_value': flags_value,
        'texture_paths': texture_paths,
        'normals': normals,
        'tangents': tangents,
        'uv1': uv1,
        'uv2': uv2,
        'uv3': uv3,
        'faces': faces,
        'face_indices_count': face_indices_count,
        'node_group_name': node_group_name,
        'node_values': node_values,
        'color_values': color_values,
        'boolean_values': boolean_values,
    }

    return object_data

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
                specular_gloss_global = struct.pack('<f', node_values.get('SpecularGlossGlobal', 0.0))
                specular_gloss_zones = struct.pack('<3f', *node_values.get('SpecularGlossZones', (0.0, 0.0, 0.0)))
                metallic_global = struct.pack('<f', node_values.get('MetallicGlobal', 0.0))
                metallic_zones = struct.pack('<3f', *node_values.get('MetallicZones', (0.0, 0.0, 0.0)))
                clearcoat_global = struct.pack('<f', node_values.get('ClearCoatGlobal', 0.0))
                clearcoat_zones = struct.pack('<3f', *node_values.get('ClearCoatZones', (0.0, 0.0, 0.0)))
                emissive_global = struct.pack('<f', node_values.get('EmissiveGlobal', 0.0))
                emissive_zones = struct.pack('<3f', *node_values.get('EmissiveZones', (0.0, 0.0, 0.0)))
                diffuse_wrap_global = struct.pack('<f', node_values.get('DiffuseWrapGlobal', 0.0))
                diffuse_wrap_zones = struct.pack('<3f', *node_values.get('DiffuseWrapZones', (0.0, 0.0, 0.0)))
                dirt_params_global = struct.pack('<f', node_values.get('DirtParamsGlobal', 0.0))
                dirt_params_zones = struct.pack('<3f', *node_values.get('DirtParamsZones', (0.0, 0.0, 0.0)))
                dirt_blend_global = struct.pack('<f', node_values.get('DirtBlendGlobal', 0.0))
                dirt_blend_zones = struct.pack('<3f', *node_values.get('DirtBlendZones', (0.0, 0.0, 0.0)))
                dirt_color = struct.pack('<4f', *color_values.get('DirtColor', (0.0, 0.0, 0.0, 0.0)))
                decal_count_global = struct.pack('<f', node_values.get('DecalCountGlobal', 0.0))
                decal_count_zones = struct.pack('<3f', *node_values.get('DecalCountZones', (0.0, 0.0, 0.0)))
                decal_width_global = struct.pack('<f', node_values.get('DecalWidthGlobal', 0.0))
                decal_width_zones = struct.pack('<3f', *node_values.get('DecalWidthZones', (0.0, 0.0, 0.0)))
                decal_blend_global = struct.pack('<f', node_values.get('DecalBlendGlobal', 0.0))
                decal_blend_zones = struct.pack('<3f', *node_values.get('DecalBlendZones', (0.0, 0.0, 0.0)))
                decal1_color = struct.pack('<4f', *color_values.get('Decal1Color', (0.0, 0.0, 0.0, 0.0)))
                decal2_color = struct.pack('<4f', *color_values.get('Decal2Color', (0.0, 0.0, 0.0, 0.0)))
                decal3_color = struct.pack('<4f', *color_values.get('Decal3Color', (0.0, 0.0, 0.0, 0.0)))
                decal4_color = struct.pack('<4f', *color_values.get('Decal4Color', (0.0, 0.0, 0.0, 0.0)))
                damage_global = struct.pack('<f', node_values.get('DamageGlobal', 0.0))
                damage_zones = struct.pack('<3f', *node_values.get('DamageZones', (0.0, 0.0, 0.0)))
                damage_blend_global = struct.pack('<f', node_values.get('DamageBlendGlobal', 0.0))
                damage_blend_zones = struct.pack('<3f', *node_values.get('DamageBlendZones', (0.0, 0.0, 0.0)))
                damage_color = struct.pack('<4f', *color_values.get('DamageColor', (0.0, 0.0, 0.0, 0.0)))
                f.write(specular_gloss_global)
                f.write(specular_gloss_zones)
                f.write(metallic_global)
                f.write(metallic_zones)
                f.write(clearcoat_global)
                f.write(clearcoat_zones)
                f.write(emissive_global)
                f.write(emissive_zones)
                f.write(diffuse_wrap_global)
                f.write(diffuse_wrap_zones)
                f.write(dirt_params_global)
                f.write(dirt_params_zones)
                f.write(dirt_blend_global)
                f.write(dirt_blend_zones)
                f.write(dirt_color)
                f.write(decal_count_global)
                f.write(decal_count_zones)
                f.write(decal_width_global)
                f.write(decal_width_zones)
                f.write(decal_blend_global)
                f.write(decal_blend_zones)
                f.write(decal1_color)
                f.write(decal2_color)
                f.write(decal3_color)
                f.write(decal4_color)
                f.write(damage_global)
                f.write(damage_zones)
                f.write(damage_blend_global)
                f.write(damage_blend_zones)
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
                f.write(bytes([0x00] * 16))

                f.write(bytes([0x07, 0x00, 0x00, 0x00]))

                for path_length, path in obj_data['texture_paths']:
                    f.write(struct.pack('<I', path_length))
                    if path_length > 0:
                        f.write(path.encode('utf-8'))

                f.write(bytes([0x00] * 16))

                f.write(struct.pack('<I', len(obj_data['vertices'])))
                for v, u1, u2, n, t in zip(obj_data['vertices'], obj_data['uv1'], obj_data['uv2'], obj_data['normals'], obj_data['tangents']):
                    f.write(struct.pack('<3f', *v))
                    f.write(struct.pack('<2f', *u1))
                    f.write(struct.pack('<2f', *u2))
                    f.write(struct.pack('<f', n))
                    f.write(struct.pack('<f', t))
                    f.write(bytes([0xff, 0xff, 0xff, 0xff]))

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
                f.write(specular_gloss)
                f.write(reflectivity)
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
