from pulseai.registry.merge import REMOVE_KEY, merge


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
