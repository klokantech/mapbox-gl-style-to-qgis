import os
import json
import sys
import traceback
from helper import get_qgis_rule, get_styles
from xml_helper import create_style_file


def generate_qgis_styles(mapbox_gl_style_path):
    if not os.path.isfile(mapbox_gl_style_path):
        raise RuntimeError("File does not exist: {}".format(mapbox_gl_style_path))
    with open(mapbox_gl_style_path, 'r') as f:
        js = json.load(f)

    all_layers = set()
    for l in js["layers"]:
        if "source-layer" in l:
            all_layers.add(l["source-layer"])

    styles_by_target_layer = {}
    for l in js["layers"]:
        if "source-layer" in l:
            layer_type = l["type"]
            source_layer = l["source-layer"]
            if layer_type == "fill":
                geo_type_name = ".polygon"
            elif layer_type == "line":
                geo_type_name = ".linestring"
            elif layer_type == "symbol":
                geo_type_name = ""
            else:
                continue

            if source_layer not in styles_by_target_layer:
                styles_by_target_layer[source_layer] = {
                    "file_name": "{}{}.qml".format(source_layer, geo_type_name),
                    "type": layer_type,
                    "styles": []
                }
            qgis_styles = get_styles(l)
            # target_file_name =
            # print("Create polygon style: {}".format(target_file_name))
            filter_expr = None
            if "filter" in l:
                filter_expr = get_qgis_rule(l["filter"])
                    # print("'{}'  ==>  '{}'".format(l["filter"], filter_expr))
            for s in qgis_styles:
                s["rule"] = filter_expr

            styles_by_target_layer[source_layer]["styles"].extend(qgis_styles)

    for layer_name in styles_by_target_layer:
        styles = styles_by_target_layer[layer_name]["styles"]
        for index, style in enumerate(styles):
            rule = style["rule"]
            styles_with_same_target = filter(lambda s: s["rule"] == rule, styles[:index])
            style["rendering_pass"] = len(styles_with_same_target)
    return styles_by_target_layer


def write_styles(styles_by_target_layer, output_directory):
    for layer_name in styles_by_target_layer:
        style = styles_by_target_layer[layer_name]
        create_style_file(output_directory=output_directory, layer_style=style)
