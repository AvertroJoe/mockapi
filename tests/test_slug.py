from cli.slug import deslugify, group_endpoints, last_segment, parent_path, slugify


def test_slugify_basic():
    assert slugify("Vulnerability scanning") == "vulnerability-scanning"


def test_slugify_collapses_punctuation_and_repeats():
    assert slugify("  NIST!!  800--53 ") == "nist-800-53"


def test_slugify_empty_string():
    assert slugify("   ") == ""


def test_deslugify_roundtrip_friendly():
    assert deslugify("vulnerability-scanning") == "Vulnerability Scanning"
    assert deslugify("nist") == "Nist"


def test_last_segment():
    assert last_segment("/api/Defender/nist") == "nist"
    assert last_segment("/api/Defender") == "Defender"
    assert last_segment("/") == ""


def test_parent_path():
    assert parent_path("/api/Defender/nist") == "/api/Defender"
    assert parent_path("/api/Defender") == "/api"
    assert parent_path("/Defender") == "/"


def _ep(id_, path):
    return {"id": id_, "path": path}


def test_group_endpoints_forms_group_with_root_and_children():
    endpoints = [
        _ep("1", "/api/Defender"),
        _ep("2", "/api/Defender/vulnerability-scanning"),
        _ep("3", "/api/Defender/nist"),
        _ep("4", "/api/users"),  # unrelated, stays ungrouped
    ]
    groups, ungrouped = group_endpoints(endpoints)

    assert len(groups) == 1
    group = groups[0]
    assert group.parent_path == "/api/Defender"
    assert group.root["id"] == "1"
    assert [c["id"] for c in group.children] == ["3", "2"]  # sorted by path

    assert [e["id"] for e in ungrouped] == ["4"]


def test_group_endpoints_requires_root_to_actually_exist():
    # "/api/Defender/nist" and "/api/Defender/vulnerability-scanning" share
    # the parent "/api/Defender", but with no literal endpoint registered
    # there, there's no real root to group them under.
    endpoints = [
        _ep("1", "/api/Defender/vulnerability-scanning"),
        _ep("2", "/api/Defender/nist"),
    ]
    groups, ungrouped = group_endpoints(endpoints)

    assert groups == []
    assert [e["id"] for e in ungrouped] == ["2", "1"]


def test_group_endpoints_lone_sibling_stays_ungrouped():
    endpoints = [_ep("1", "/api/Defender/nist")]
    groups, ungrouped = group_endpoints(endpoints)

    assert groups == []
    assert [e["id"] for e in ungrouped] == ["1"]


def test_group_endpoints_unrelated_siblings_sharing_a_shallow_ancestor_stay_ungrouped():
    # "/api/Defender" and "/api/users" incidentally share the ancestor
    # "/api", but neither was created under the other — "/api" isn't a
    # real endpoint, so this must NOT be treated as a group.
    endpoints = [_ep("1", "/api/Defender"), _ep("2", "/api/users")]
    groups, ungrouped = group_endpoints(endpoints)

    assert groups == []
    assert [e["id"] for e in ungrouped] == ["1", "2"]


def test_group_endpoints_root_with_single_child_still_groups():
    endpoints = [_ep("1", "/api/Defender"), _ep("2", "/api/Defender/nist")]
    groups, ungrouped = group_endpoints(endpoints)

    assert len(groups) == 1
    assert groups[0].root["id"] == "1"
    assert [c["id"] for c in groups[0].children] == ["2"]
    assert ungrouped == []
