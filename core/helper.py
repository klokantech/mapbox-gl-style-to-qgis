import copy

_comparision_operators = {
    "==": "=",
    "<=": "<=",
    ">=": ">=",
    "<": "<",
    ">": ">",
    "!=": "!="
}

_combining_operators = {
    "all": "and",
    "any": "or",
    "none": "and not"
}

_membership_operators = {
    "in": "in",
    "!in": "not in"
}

_existential_operators = {
    "has": "is not null",
    "!has": "is null"
}

"""
 * the upper bound map scales by zoom level.
 * E.g. a style for zoom level 14 shall be applied for map scales <= 50'000
 * If the are more zoom levels applied, they need to be ascending.
 * E.g. a second style will be applied for zoom level 15, that is map scale <= 25'000, the first style
   for zoom level 14 will no longer be active.
"""
upper_bound_map_scales_by_zoom_level = {
    0: 10000000000,
    1: 1000000000,
    2: 500000000,
    3: 200000000,
    4: 50000000,
    5: 25000000,
    6: 12500000,
    7: 6500000,
    8: 3000000,
    9: 1500000,
    10: 750000,
    11: 400000,
    12: 200000,
    13: 100000,
    14: 50000,
    15: 25000,
    16: 12500,
    17: 5000,
    18: 2500,
    19: 1500,
    20: 750,
    21: 500,
    22: 250,
    23: 100
}


def get_styles(paint, layer_id=None):
    base_style = {
        "zoom_level": None,
        "min_scale_denom": None,
        "max_scale_denom": None
    }
    if layer_id:
        base_style["name"] = layer_id

    values_by_zoom = {}

    all_values = []
    all_values.extend(get_properties_by_zoom(paint, "fill-color"))
    all_values.extend(get_properties_by_zoom(paint, "fill-outline-color"))
    all_values.extend(get_properties_by_zoom(paint, "fill-translate"))
    all_values.extend(get_properties_by_zoom(paint, "fill-opacity"))

    for v in all_values:
        zoom = v["zoom_level"]
        if zoom is None:
            base_style[v["name"]] = v["value"]
        else:
            if zoom not in values_by_zoom:
                values_by_zoom[zoom] = []
            values_by_zoom[zoom].append(v)

    resulting_styles = []
    if not values_by_zoom:
        resulting_styles.append(base_style)
    else:
        clone = base_style
        for zoom in sorted(values_by_zoom.keys()):
            values = values_by_zoom[zoom]
            clone = copy.deepcopy(clone)
            clone["zoom_level"] = zoom
            for v in values:
                clone[v["name"]] = v["value"]
            resulting_styles.append(clone)
        styles_backwards = list(reversed(resulting_styles))
        for index, s in enumerate(styles_backwards):
            if index < len(resulting_styles)-1:
                next_style = styles_backwards[index+1]
                for k in s:
                    if k not in next_style:
                        next_style[k] = s[k]

    resulting_styles = sorted(resulting_styles, key=lambda s: s["zoom_level"])
    _apply_scale_range(resulting_styles)
    # print "apply scales: ", resulting_styles

    return resulting_styles


def _apply_scale_range(styles):
    for index, s in enumerate(styles):
        if s["zoom_level"] is None:
            continue

        max_scale_denom = upper_bound_map_scales_by_zoom_level[s["zoom_level"]]
        if index == len(styles) - 1:
            min_scale_denom = 1
        else:
            zoom_of_next = styles[index+1]["zoom_level"]
            min_scale_denom = upper_bound_map_scales_by_zoom_level[zoom_of_next]
        s["min_scale_denom"] = min_scale_denom
        s["max_scale_denom"] = max_scale_denom


def get_properties_by_zoom(paint, fill_property):
    value = _get_value_safe(paint, fill_property)
    stops = None
    if value:
        stops = _get_value_safe(value, "stops")
    properties = []
    if stops:
        for s in stops:
            properties.append({
                "name": fill_property,
                "zoom_level": int(s[0]),
                "value": s[1]})
    elif value:
        properties.append({
            "name": fill_property,
            "zoom_level": None,
            "value": value})
    return properties


def _get_rules_for_stops(stops):
    rules = []
    for s in stops:
        zoom_level = int(s[0])
        scale = upper_bound_map_scales_by_zoom_level[zoom_level]
        rule = get_qgis_rule(["<=", "@map_scale", scale])
        rules.append({"rule": rule, "value": s[1]})
    return rules


def _get_value_safe(value, path):
    result = None
    if value and isinstance(value, dict) and path and path in value:
        result = value[path]
    return result


def get_qgis_rule(mb_filter):
    op = mb_filter[0]
    if op in _comparision_operators:
        result = _get_comparision_expr(mb_filter)
    elif op in _combining_operators:
        is_none = op == "none"
        all_exprs = map(lambda f: get_qgis_rule(f), mb_filter[1:])
        all_exprs = filter(lambda e: e is not None, all_exprs)
        full_expr = " {} ".format(_combining_operators[op]).join(all_exprs)
        if is_none:
            full_expr = "not {}".format(full_expr)
        result = full_expr
    elif op in _membership_operators:
        result = _get_membership_expr(mb_filter)
    elif op in _existential_operators:
        result = _get_existential_expr(mb_filter)
    else:
        raise NotImplementedError("Not Implemented Operator: '{}', Filter: {}".format(op, mb_filter))

    if result:
        result = "({})".format(result)
    return result


def _get_comparision_expr(mb_filter):
    assert mb_filter[0] in _comparision_operators
    assert len(mb_filter) == 3
    op = _comparision_operators[mb_filter[0]]
    attr = mb_filter[1]
    value = mb_filter[2]
    if attr == '$type':
        return None
    attr_in_quotes = not attr.startswith("@")
    if attr_in_quotes:
        attr = "\"{}\"".format(attr)
    return "{attr} {op} '{value}'".format(attr=attr, op=op, value=value)


def _get_membership_expr(mb_filter):
    assert mb_filter[0] in _membership_operators
    assert len(mb_filter) >= 3
    what = "\"{}\"".format(mb_filter[1])
    op = _membership_operators[mb_filter[0]]
    collection = "({})".format(", ".join(map(lambda e: "'{}'".format(e), mb_filter[2:])))
    return "{what} {op} {coll}".format(what=what, op=op, coll=collection)


def _get_existential_expr(mb_filter):
    assert mb_filter[0] in _existential_operators
    assert len(mb_filter) == 2
    op = _existential_operators[mb_filter[0]]
    key = mb_filter[1]
    return "attribute($currentfeature, '{key}') {op}".format(key=key, op=op)
