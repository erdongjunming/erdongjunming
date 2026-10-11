import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from jsonschema import Draft202012Validator, validators

CONTRACT = ROOT / "contracts" / "v1"
checks = []


def checked(name, count=1):
    checks.append({"check": name, "count": count, "result": "passed"})


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, (path, "duplicate key", key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


schema = read_json(CONTRACT / "schema.json")
golden = read_json(CONTRACT / "golden.json")
manifest = read_json(ROOT / "module-manifest.json")
Draft202012Validator.check_schema(schema)
checked("draft_2020_12_schema")
strict_checker = Draft202012Validator.TYPE_CHECKER.redefine(
    "integer", lambda checker, value: type(value) is int
)
StrictValidator = validators.extend(Draft202012Validator, type_checker=strict_checker)


def validate(name, value):
    target = {"$ref": "#/$defs/" + name, "$defs": schema["$defs"]}
    StrictValidator(target).validate(value)


def digest(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_refs(value):
    if isinstance(value, dict):
        if "$ref" in value:
            prefix = "#/$defs/"
            assert value["$ref"].startswith(prefix)
            assert value["$ref"][len(prefix):] in schema["$defs"]
        for child in value.values():
            check_refs(child)
    elif isinstance(value, list):
        for child in value:
            check_refs(child)


check_refs(schema)
checked("local_schema_references")
for sample in golden["schema_samples"]:
    validate(sample["type"], sample["value"])
validate("Task", golden["task"])
checked("schema_samples_and_task", len(golden["schema_samples"]) + 1)

for invalid in (
    {"env_version": "reg4/1.0.0", "registers": [True, 2, 3, 4]},
    {"env_version": "reg4/1.0.0", "registers": [1.0, 2, 3, 4]},
    {"env_version": "reg4/1.0.0", "registers": [1, 2, 3, 9]},
    {"env_version": "reg4/1.0.0", "registers": [1, 2, 3, 4], "extra": 1},
):
    assert not StrictValidator({"$ref": "#/$defs/State", "$defs": schema["$defs"]}).is_valid(invalid)
checked("negative_state_schema_cases", 4)

type_tree = ast.parse((CONTRACT / "types.pyi").read_text(encoding="utf-8"))
port_tree = ast.parse((CONTRACT / "ports.pyi").read_text(encoding="utf-8"))
typed = {node.name: node for node in type_tree.body if isinstance(node, ast.ClassDef)}
aliases = {node.target.id: node.value for node in type_tree.body if isinstance(node, ast.AnnAssign)}


def literal_values(node):
    assert isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Literal"
    values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    return [ast.literal_eval(value) for value in values]


def union_members(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return union_members(node.left) + union_members(node.right)
    return [node]


def compatible(annotation, shape):
    if isinstance(annotation, ast.BinOp):
        members = union_members(annotation)
        options = shape.get("anyOf", [])
        assert len(members) == len(options), (ast.unparse(annotation), shape)
        for member, option in zip(members, options):
            compatible(member, option)
        return
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        assert shape["type"] == "null"
        return
    if isinstance(annotation, ast.Name):
        primitives = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
        if annotation.id in primitives:
            resolved = shape
            if shape.get("$ref") in ("#/$defs/Id", "#/$defs/Digest", "#/$defs/Index", "#/$defs/Value"):
                resolved = schema["$defs"][shape["$ref"].split("/")[-1]]
            assert resolved.get("type") == primitives[annotation.id], (annotation.id, shape)
        else:
            assert shape.get("$ref") == "#/$defs/" + annotation.id, (annotation.id, shape)
        return
    assert isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name)
    outer = annotation.value.id
    if outer == "Literal":
        values = literal_values(annotation)
        actual = shape.get("enum", [shape["const"]] if "const" in shape else [])
        assert set(values) == set(actual), (values, shape)
    elif outer == "list":
        assert shape["type"] == "array"
        compatible(annotation.slice, shape["items"])
    elif outer == "dict":
        assert shape["type"] == "object"
    else:
        raise AssertionError(outer)


for name, node in typed.items():
    fields = {field.target.id: field.annotation for field in node.body if isinstance(field, ast.AnnAssign)}
    if name.endswith("Action"):
        op = literal_values(fields["op"])[0]
        shape = next(item for item in schema["$defs"]["Action"]["oneOf"] if item["properties"]["op"]["const"] == op)
    else:
        shape = schema["$defs"][name]
    assert shape.get("additionalProperties") is False, name
    assert set(fields) == set(shape["properties"]) == set(shape["required"]), name
    for field, annotation in fields.items():
        field_shape = shape["properties"][field]
        if field_shape.get("$ref") in ("#/$defs/Id", "#/$defs/Digest"):
            assert isinstance(annotation, ast.Name) and annotation.id == "str"
        elif field_shape.get("$ref") in ("#/$defs/Index", "#/$defs/Value"):
            assert isinstance(annotation, ast.Name) and annotation.id == "int"
        elif isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name) and annotation.value.id == "list" and field_shape.get("items", {}).get("$ref") == "#/$defs/Index":
            assert isinstance(annotation.slice, ast.Name) and annotation.slice.id == "int"
        elif isinstance(annotation, ast.BinOp) and field in ("provider", "model", "parent_snapshot_id"):
            assert ast.unparse(annotation) == "str | None"
            assert field_shape["anyOf"][0]["$ref"] == "#/$defs/Id"
            assert field_shape["anyOf"][1]["type"] == "null"
        else:
            compatible(annotation, field_shape)
checked("typed_dict_fields_and_types", len(typed))
for name in ("Operation", "ErrorCode"):
    assert set(literal_values(aliases[name])) == set(schema["$defs"][name]["enum"])
assert set(literal_values(aliases["BudgetKind"])) == set(schema["$defs"]["BudgetUsage"]["properties"]) - {"action_attempts"}
checked("public_literal_aliases", 3)

declared_types = set(typed) | set(aliases)
port_classes = {node.name for node in port_tree.body if isinstance(node, ast.ClassDef)}
imports = {entry.name for node in port_tree.body if isinstance(node, ast.ImportFrom) and node.module == "types" for entry in node.names}
assert imports <= declared_types, imports - declared_types
known = declared_types | port_classes | {"str", "int", "float", "bool", "object", "list", "dict", "None"}
method_count = 0
for node in port_tree.body:
    if isinstance(node, ast.ClassDef):
        for method in node.body:
            if isinstance(method, ast.FunctionDef):
                method_count += 1
                annotations = [arg.annotation for arg in method.args.args if arg.annotation] + ([method.returns] if method.returns else [])
                for annotation in annotations:
                    references = {item.id for item in ast.walk(annotation) if isinstance(item, ast.Name)}
                    assert references <= known, (method.name, references - known)
                    assert not (references & declared_types) - imports, (method.name, (references & declared_types) - imports)
checked("port_annotations_and_imports", method_count)

ids = {module["id"] for module in manifest["modules"]}
assert len(ids) == len(manifest["modules"]) == 12
visited = set()
active = set()
by_id = {module["id"]: module for module in manifest["modules"]}


def visit(module_id):
    assert module_id in ids
    assert module_id not in active, "dependency cycle"
    if module_id in visited:
        return
    active.add(module_id)
    for dependency in by_id[module_id]["depends_on"]:
        visit(dependency)
    active.remove(module_id)
    visited.add(module_id)


ownership = []
for module in manifest["modules"]:
    visit(module["id"])
    assert (ROOT / module["card"]).is_file(), module["card"]
    for path in module["owns"]:
        assert not path.startswith("/") and ".." not in path.split("/")
        for other_id, other_path in ownership:
            assert path != other_path and not (other_path.endswith("/") and path.startswith(other_path)) and not (path.endswith("/") and other_path.startswith(path)), (module["id"], path, other_id, other_path)
        ownership.append((module["id"], path))
checked("module_dependency_graph_and_cards", len(ids))
checked("non_overlapping_file_ownership", len(ownership))

for case in golden["hash_cases"]:
    validate("State", case["state"])
    assert digest(case["state"]) == case["state_id"]
checked("canonical_state_hashes", len(golden["hash_cases"]))

required_fields = {"SET": ("index", "value"), "ADD": ("index", "delta"), "COPY": ("source", "target"), "SWAP": ("left", "right")}
for case in golden["transition_cases"]:
    before = case["before"]
    after = before.copy()
    action = case["action"]
    op = action.get("op")
    fields = required_fields.get(op)
    error = None
    if fields is None or set(action) != {"op", *fields} or any(type(action[field]) is not int for field in fields):
        error = "malformed_action"
    else:
        for field in fields:
            low, high = (-8, 8) if field == "value" else (-2, 2) if field == "delta" else (0, 3)
            if not low <= action[field] <= high:
                error = "invalid_argument"
                break
        if error is None and op not in case["allowed_ops"]:
            error = "action_forbidden"
    if error is None:
        validate("Action", action)
        if op == "SET":
            after[action["index"]] = action["value"]
        elif op == "ADD":
            i = action["index"]
            after[i] = min(8, max(-8, after[i] + action["delta"]))
        elif op == "COPY":
            after[action["target"]] = before[action["source"]]
        else:
            i, j = action["left"], action["right"]
            after[i], after[j] = before[j], before[i]
    assert after == case["after"] and error == case["error_code"] and (error is None) == case["accepted"], case["case_id"]
checked("hand_checkable_transition_golden_cases", len(golden["transition_cases"]))

task = golden["task"]
for case in golden["verification_cases"]:
    violations = []
    for target in task["goal"]["targets"]:
        if case["registers"][target["index"]] != target["value"]:
            violations.append("target_mismatch")
    for index in task["goal"]["preserve"]:
        if case["registers"][index] != task["initial"]["registers"][index]:
            violations.append("preserve_violation")
    assert sorted(violations) == sorted(case["violation_codes"])
    assert (not violations) == case["success"]
checked("independent_goal_golden_cases", len(golden["verification_cases"]))

for filename in ("00-README.md", "01-contract.md", "02-integration.md", "04-handoff-prompts.md", "05-research-roadmap.md", "06-acceptance.md"):
    assert (ROOT / filename).is_file()
checked("required_plan_documents", 6)
contract_parts = [name + ":" + hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(manifest["contract_files"])]
contract_digest = "sha256:" + hashlib.sha256(("\n".join(contract_parts) + "\n").encode("utf-8")).hexdigest()
result = {"status": "passed", "checks": checks, "contract_digest": contract_digest,
          "semantics_digest": "sha256:" + hashlib.sha256((ROOT / "01-contract.md").read_bytes()).hexdigest(),
          "scope": "plan_specification_only; application and live provider tests not run"}
print(json.dumps(result, ensure_ascii=False, indent=2))
