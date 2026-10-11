from pulseai.registry.merge import REMOVE_KEY, merge


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(v, key) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def test_dicts_merge_recursively() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": 1}
    assert merge(base, {"a": {"y": 3}}) == {"a": {"x": 1, "y": 3}, "b": 1}


def test_scalars_and_plain_lists_are_replaced() -> None:
    assert merge({"a": [1, 2], "b": "x"}, {"a": [3], "b": "y"}) == {"a": [3], "b": "y"}


def test_id_lists_merge_by_id_and_keep_order() -> None:
    base = {"items": [{"id": "a", "v": 1}, {"id": "b", "v": 2}]}
    override = {"items": [{"id": "b", "v": 20}, {"id": "c", "v": 3}]}
    assert merge(base, override) == {
        "items": [{"id": "a", "v": 1}, {"id": "b", "v": 20}, {"id": "c", "v": 3}]
    }


def test_remove_flag_deletes_item() -> None:
    base = {"items": [{"id": "a"}, {"id": "b"}]}
    assert merge(base, {"items": [{"id": "a", REMOVE_KEY: True}]}) == {"items": [{"id": "b"}]}


def test_remove_unknown_id_is_ignored() -> None:
    base = {"items": [{"id": "a"}]}
    assert merge(base, {"items": [{"id": "zzz", REMOVE_KEY: True}]}) == base


def test_empty_list_override_clears() -> None:
    assert merge({"items": [{"id": "a"}]}, {"items": []}) == {"items": []}


def test_remove_flags_never_leak_into_results() -> None:
    result = merge({}, {"items": [{"id": "a", "nested": {"x": 1}}, {"id": "b", REMOVE_KEY: True}]})
    assert result == {"items": [{"id": "a", "nested": {"x": 1}}]}


def test_inputs_are_not_mutated() -> None:
    base = {"a": {"x": 1}, "items": [{"id": "a", "v": 1}]}
    override = {"a": {"y": 2}, "items": [{"id": "a", "v": 2}]}
    merge(base, override)
    assert base == {"a": {"x": 1}, "items": [{"id": "a", "v": 1}]}


def test_remove_false_on_existing_id_keeps_item_without_marker() -> None:
    base = {"items": [{"id": "a", "v": 1}]}
    result = merge(base, {"items": [{"id": "a", REMOVE_KEY: False, "v": 2}]})
    assert result == {"items": [{"id": "a", "v": 2}]}


def test_remove_key_in_mappings_never_leaks() -> None:
    assert merge({"a": 1}, {REMOVE_KEY: True}) == {"a": 1}
    assert merge({"a": {"x": 1}}, {"a": {REMOVE_KEY: False, "y": 2}}) == {"a": {"x": 1, "y": 2}}
    assert merge({}, {"a": {REMOVE_KEY: "yes", "y": 2}}) == {"a": {"y": 2}}


def test_markers_in_base_are_stripped_everywhere() -> None:
    base = {
        "items": [
            {"id": "a", REMOVE_KEY: True},
            {"id": "b", "nested": {REMOVE_KEY: False, "x": 1}},
        ],
        "other": {REMOVE_KEY: True, "y": 2},
    }
    result = merge(base, {"items": [{"id": "c"}]})
    assert result == {"items": [{"id": "b", "nested": {"x": 1}}, {"id": "c"}], "other": {"y": 2}}
    assert not _contains_key(result, REMOVE_KEY)


def test_results_never_alias_inputs() -> None:
    base = {"a": {"x": [1]}, "items": [{"id": "a", "n": {"k": 1}}, {"id": "b", "n": {"k": 2}}]}
    override = {"c": {"z": [3]}, "items": [{"id": "a", "m": {"k": 3}}, {"id": "d", "n": {"k": 4}}]}
    result = merge(base, override)
    result["a"]["x"].append(99)
    result["c"]["z"].append(99)
    for item in result["items"]:
        for value in item.values():
            if isinstance(value, dict):
                value["k"] = 99
    assert base == {
        "a": {"x": [1]},
        "items": [{"id": "a", "n": {"k": 1}}, {"id": "b", "n": {"k": 2}}],
    }
    assert override == {
        "c": {"z": [3]},
        "items": [{"id": "a", "m": {"k": 3}}, {"id": "d", "n": {"k": 4}}],
    }


def test_replaced_values_do_not_alias_override() -> None:
    override = {"a": [1, 2], "b": {"x": 1}}
    result = merge({"a": [0]}, override)
    result["a"].append(3)
    result["b"]["x"] = 2
    assert override == {"a": [1, 2], "b": {"x": 1}}


def test_removed_id_added_again_goes_to_the_end() -> None:
    base = {"items": [{"id": "a", "v": 1}, {"id": "b"}]}
    override = {"items": [{"id": "a", REMOVE_KEY: True}, {"id": "a", "v": 2}]}
    assert merge(base, override) == {"items": [{"id": "b"}, {"id": "a", "v": 2}]}


def test_duplicate_ids_in_base_collapse_to_the_last_occurrence() -> None:
    base = {"items": [{"id": "a", "v": 1}, {"id": "b"}, {"id": "a", "v": 3}]}
    assert merge(base, {"items": [{"id": "c"}]}) == {
        "items": [{"id": "a", "v": 3}, {"id": "b"}, {"id": "c"}]
    }
