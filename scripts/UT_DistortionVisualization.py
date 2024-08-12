import maya.cmds as cmds
import maya.api.OpenMaya as om
import math

# グローバルプロシージャの定義
def UT_find_symmetric_vertex_pairs(mesh_fn, axis='x', symmetry_on=True):
    verts = mesh_fn.getPoints(om.MSpace.kWorld)
    vertex_pairs = []
    processed_indices = set()
    
    tolerance = 0.0001  # 対称性の判断基準となる許容誤差
    
    for i, v1 in enumerate(verts):
        if i in processed_indices:
            continue
        found_pair = False
        for j, v2 in enumerate(verts):
            if i >= j or j in processed_indices:
                continue

            if symmetry_on:
                if axis == 'x':
                    if abs(v1.x + v2.x) < tolerance and abs(v1.y - v2.y) < tolerance and abs(v1.z - v2.z) < tolerance:
                        vertex_pairs.append((i, j))
                        processed_indices.update([i, j])
                        found_pair = True
                        break
                elif axis == 'y':
                    if abs(v1.y + v2.y) < tolerance and abs(v1.x - v2.x) < tolerance and abs(v1.z - v2.z) < tolerance:
                        vertex_pairs.append((i, j))
                        processed_indices.update([i, j])
                        found_pair = True
                        break
                elif axis == 'z':
                    if abs(v1.z + v2.z) < tolerance and abs(v1.x - v2.x) < tolerance and abs(v1.y - v2.y) < tolerance:
                        vertex_pairs.append((i, j))
                        processed_indices.update([i, j])
                        found_pair = True
                        break
            else:
                vertex_pairs.append((i, i))  # シンメトリーオフのときは自分自身をペアにする
                break

        if not found_pair and symmetry_on:
            vertex_pairs.append((i, i))  # 対応するペアが見つからない場合は自分自身をペアにする
    
    return vertex_pairs

# 頂点の歪みを計算するグローバルプロシージャ
def UT_calculate_symmetric_vertex_distortion(mesh_fn, vertex_pairs):
    def UT_normal(a, b, c):
        ab = b - a
        ac = c - a
        cross_product = ab ^ ac
        cross_product.normalize()
        return cross_product
    
    verts = mesh_fn.getPoints(om.MSpace.kWorld)
    face_count = mesh_fn.numPolygons
    
    vertex_normals = {i: [] for i in range(len(verts))}
    
    for face_id in range(face_count):
        face_vertices = mesh_fn.getPolygonVertices(face_id)
        if len(face_vertices) >= 3:
            a, b, c = verts[face_vertices[0]], verts[face_vertices[1]], verts[face_vertices[2]]
            face_normal = UT_normal(a, b, c)
            for v in face_vertices:
                vertex_normals[v].append(face_normal)
    
    vertex_distortions = [0.0] * len(verts)
    
    for v1, v2 in vertex_pairs:
        normals_v1 = vertex_normals[v1]
        normals_v2 = vertex_normals[v2]
        
        if len(normals_v1) > 1:
            relative_angles_v1 = []
            for i in range(len(normals_v1)):
                for j in range(i + 1, len(normals_v1)):
                    angle = math.degrees(math.acos(max(min(normals_v1[i] * normals_v1[j], 1.0), -1.0)))
                    relative_angles_v1.append(angle)
            average_angle_v1 = sum(relative_angles_v1) / len(relative_angles_v1)
            vertex_distortions[v1] = average_angle_v1

        if v1 != v2 and len(normals_v2) > 1:
            relative_angles_v2 = []
            for i in range(len(normals_v2)):
                for j in range(i + 1, len(normals_v2)):
                    angle = math.degrees(math.acos(max(min(normals_v2[i] * normals_v2[j], 1.0), -1.0)))
                    relative_angles_v2.append(angle)
            average_angle_v2 = sum(relative_angles_v2) / len(relative_angles_v2)
            vertex_distortions[v2] = average_angle_v2

        if v1 != v2:
            vertex_distortions[v1] = vertex_distortions[v2] = max(vertex_distortions[v1], vertex_distortions[v2])
    
    return vertex_distortions

# カラーグラデーションを取得するグローバルプロシージャ
def UT_get_default_color_from_angle(angle):
    if angle <= 0:
        return (0.5, 0.5, 0.5)
    elif angle >= 60:
        return (1.0, 0.0, 0.0)
    elif angle <= 30:
        t = angle / 30.0
        return ((1 - t) * 0.5, (1 - t) * 0.5, (1 - t) * 1.0)
    else:
        t = (angle - 30) / 30.0
        return (t, 0.0, 1.0 - t)

def UT_get_fusion_color_from_angle(angle):
    if angle <= 0:
        return (0.0, 0.0, 1.0)
    elif angle >= 60:
        return (1.0, 0.0, 0.0)
    elif angle <= 30:
        t = angle / 30.0
        return ((1 - t) * 0.0, (1 - t) * 1.0, (1 - t) * 0.0)
    else:
        t = (angle - 30) / 30.0
        return (1.0, 1.0 - t, 0.0)

def UT_get_zebra_color_from_angle(angle):
    if angle <= 0:
        return (1.0, 1.0, 1.0)
    elif angle >= 60:
        return (0.0, 0.0, 0.0)
    else:
        stripes = int(angle // 10) % 2
        return (1.0, 1.0, 1.0) if stripes == 0 else (0.0, 0.0, 0.0)

# 頂点カラーを適用するグローバルプロシージャ
def UT_apply_vertex_colors(progress_control, status_text, axis='x', symmetry_on=True, fusion_style=False, zebra_style=False):
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("メッシュオブジェクトを選択してください。")
        return
    
    obj = selection[0]
    shapes = cmds.listRelatives(obj, shapes=True)
    if not shapes:
        cmds.warning("選択したオブジェクトにはシェイプノードがありません。")
        return
    
    mesh_shape = shapes[0]
    
    selection_list = om.MSelectionList()
    selection_list.add(mesh_shape)
    dag_path = selection_list.getDagPath(0)
    mesh_fn = om.MFnMesh(dag_path)
    
    vertex_pairs = UT_find_symmetric_vertex_pairs(mesh_fn, axis=axis, symmetry_on=symmetry_on)
    vertex_distortions = UT_calculate_symmetric_vertex_distortion(mesh_fn, vertex_pairs)
    
    if zebra_style:
        vertex_colors = [UT_get_zebra_color_from_angle(angle) for angle in vertex_distortions]
    elif fusion_style:
        vertex_colors = [UT_get_fusion_color_from_angle(angle) for angle in vertex_distortions]
    else:
        vertex_colors = [UT_get_default_color_from_angle(angle) for angle in vertex_distortions]

    color_set = 'distortionColorSet'
    existing_color_sets = cmds.polyColorSet(obj, query=True, allColorSets=True) or []
    if color_set not in existing_color_sets:
        cmds.polyColorSet(obj, create=True, colorSet=color_set)
    cmds.polyColorSet(obj, currentColorSet=True, colorSet=color_set)

    color_array = om.MColorArray([om.MColor(vert_color) for vert_color in vertex_colors])
    mesh_fn.setVertexColors(color_array, list(range(len(vertex_colors))))

    for i, _ in enumerate(vertex_colors):
        progress = (i + 1) / len(vertex_colors)
        cmds.progressBar(progress_control, edit=True, progress=int(progress * 100))
        cmds.text(status_text, edit=True, label=f"Applying vertex colors: {int(progress * 100)}%")
    
    cmds.polyOptions(obj, colorShadedDisplay=True)
    cmds.setAttr("%s.displayColors" % obj, 1)
    cmds.select(obj)

# 頂点カラーの表示を切り替えるグローバルプロシージャ
def UT_toggle_vertex_colors():
    selection = cmds.ls(selection=True)
    if not selection:
        cmds.warning("メッシュオブジェクトを選択してください。")
        return
    
    obj = selection[0]
    display_colors = cmds.getAttr("%s.displayColors" % obj)
    cmds.setAttr("%s.displayColors" % obj, not display_colors)
    cmds.select(obj)

# 頂点カラーを更新するグローバルプロシージャ
def UT_update_vertex_colors(progress_control, status_text, axis='x', symmetry_on=True, fusion_style=False, zebra_style=False):
    UT_apply_vertex_colors(progress_control, status_text, axis, symmetry_on, fusion_style, zebra_style)

# UIを作成するグローバルプロシージャ
def UT_create_ui():
    if cmds.window("UT_distortionUI", exists=True):
        cmds.deleteUI("UT_distortionUI")

    window = cmds.window("UT_distortionUI", title="UT Distortion Visualization", widthHeight=(400, 350))
    
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
    
    cmds.text(label="頂点の歪みを可視化します", align="center", height=20, annotation="このツールは、頂点の歪みを視覚化します。")

    symmetry_check = cmds.checkBox(label="シンメトリーを有効にする", value=True, annotation="シンメトリーを無効にすると、各頂点が個別に処理されます。")
    
    axis_option = cmds.optionMenu(label="対称軸を選択:", annotation="対称軸を選択します。")
    cmds.menuItem(label='X軸')
    cmds.menuItem(label='Y軸')
    cmds.menuItem(label='Z軸')
    
    fusion_style_check = cmds.checkBox(label="Fusion 360スタイルのグラデーションを使用する", value=False, annotation="Fusion 360の曲率マップ解析に似たグラデーションを使用します。")
    zebra_style_check = cmds.checkBox(label="ゼブラ解析スタイルを使用する", value=False, annotation="ゼブラ解析スタイルの白黒グラデーションを使用します。")
    
    progress_control = cmds.progressBar(maxValue=100, width=380, height=20, annotation="処理の進行状況を表示します。")
    status_text = cmds.text(label="準備完了", align="center", height=20, annotation="現在のステータスを表示します。")
    
    cmds.separator(height=10, style='in')
    cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 120), (2, 120), (3, 120)], columnSpacing=[(1, 10), (2, 10), (3, 10)])
    
    apply_button = cmds.button(label="Apply Colors", height=40, command=lambda x: UT_start_task(apply_button, update_button, progress_control, status_text, axis_option, symmetry_check, fusion_style_check, zebra_style_check, UT_apply_vertex_colors), annotation="選択したメッシュに頂点カラーを適用します。")
    update_button = cmds.button(label="Update Colors", height=40, command=lambda x: UT_start_task(apply_button, update_button, progress_control, status_text, axis_option, symmetry_check, fusion_style_check, zebra_style_check, UT_update_vertex_colors), annotation="頂点カラーを更新します。")
    cmds.button(label="Toggle Colors", height=40, command=lambda x: UT_toggle_vertex_colors(), annotation="頂点カラーの表示をON/OFFします。")
    
    cmds.showWindow(window)

# 非同期タスクを開始するグローバルプロシージャ
def UT_start_task(apply_button, update_button, progress_control, status_text, axis_option, symmetry_check, fusion_style_check, zebra_style_check, task_function):
    cmds.button(apply_button, edit=True, enable=False)
    cmds.button(update_button, edit=True, enable=False)
    cmds.progressBar(progress_control, edit=True, progress=0)
    cmds.text(status_text, edit=True, label="Starting...")

    selected_axis = cmds.optionMenu(axis_option, query=True, value=True)
    axis = 'x'
    if selected_axis == 'X軸':
        axis = 'x'
    elif selected_axis == 'Y軸':
        axis = 'y'
    elif selected_axis == 'Z軸':
        axis = 'z'
    
    symmetry_on = cmds.checkBox(symmetry_check, query=True, value=True)
    fusion_style = cmds.checkBox(fusion_style_check, query=True, value=True)
    zebra_style = cmds.checkBox(zebra_style_check, query=True, value=True)

    def task_wrapper():
        task_function(progress_control, status_text, axis, symmetry_on, fusion_style, zebra_style)
        cmds.button(apply_button, edit=True, enable=True)
        cmds.button(update_button, edit=True, enable=True)
        cmds.text(status_text, edit=True, label="Done")

    cmds.scriptJob(runOnce=True, idleEvent=task_wrapper)

# グローバルプロシージャの呼び出し
if __name__ == "__main__":
    UT_create_ui()
