"""Test folder/group CRUD operations and tree API via HTTP endpoints."""
import uuid
import pytest
from fastapi.testclient import TestClient
from src.api.server import create_app


@pytest.fixture
def client(tmp_path):
    """Create test client with isolated DB."""
    app = create_app(data_root=tmp_path)
    return TestClient(app)


def _gid():
    """Generate unique group_id."""
    return uuid.uuid4().hex[:12]


def test_create_root_folder(client):
    """F.16: Create root folder."""
    gid = _gid()
    resp = client.post("/group/create", json={"group_id": gid, "name": "Test Folder"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["group_id"] == gid
    assert data["name"] == "Test Folder"


def test_create_child_folder(client):
    """F.16: Create child folder with parent_id."""
    root_id = _gid()
    child_id = _gid()
    
    resp = client.post("/group/create", json={"group_id": root_id, "name": "Root"})
    assert resp.status_code == 200
    
    resp = client.post("/group/create", json={"group_id": child_id, "name": "Child", "parent_id": root_id})
    assert resp.status_code == 200


def test_create_child_with_nonexistent_parent_fails(client):
    """F.16: Create child with nonexistent parent should return 400."""
    child_id = _gid()
    resp = client.post("/group/create", json={"group_id": child_id, "name": "Child", "parent_id": "nonexistent"})
    assert resp.status_code == 400
    assert "parent group" in resp.json()["detail"].lower()


def test_create_duplicate_group_fails(client):
    """F.16: Create group with duplicate group_id should return 409."""
    gid = _gid()
    client.post("/group/create", json={"group_id": gid, "name": "First"})
    resp = client.post("/group/create", json={"group_id": gid, "name": "Duplicate"})
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


def test_get_group_tree(client):
    """F.16: Get hierarchical group tree."""
    root_id = _gid()
    child1_id = _gid()
    child2_id = _gid()
    grandchild_id = _gid()
    
    client.post("/group/create", json={"group_id": root_id, "name": "Root"})
    client.post("/group/create", json={"group_id": child1_id, "name": "Child 1", "parent_id": root_id})
    client.post("/group/create", json={"group_id": child2_id, "name": "Child 2", "parent_id": root_id})
    client.post("/group/create", json={"group_id": grandchild_id, "name": "Grandchild", "parent_id": child1_id})
    
    resp = client.get("/group/tree")
    assert resp.status_code == 200
    data = resp.json()["data"]
    
    # Check tree structure
    assert "tree" in data
    assert "roots" in data
    
    # Find root in roots
    root_node = next((r for r in data["roots"] if r["group_id"] == root_id), None)
    assert root_node is not None
    
    # Check children in tree
    children = data["tree"].get(root_id, [])
    assert len(children) == 2
    
    # Check grandchild
    grandchild_children = data["tree"].get(child1_id, [])
    assert len(grandchild_children) == 1
    assert grandchild_children[0]["group_id"] == grandchild_id


def test_update_folder(client):
    """F.16: Update folder name."""
    gid = _gid()
    client.post("/group/create", json={"group_id": gid, "name": "Old Name"})
    resp = client.post("/group/update", json={"group_id": gid, "name": "New Name", "sort_order": 0})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "New Name"


def test_update_nonexistent_folder_returns_404(client):
    """F.16: Update nonexistent folder should return 404."""
    resp = client.post("/group/update", json={"group_id": "nonexistent", "name": "Name"})
    assert resp.status_code == 404


def test_delete_leaf_folder(client):
    """F.16: Delete leaf folder (no children)."""
    gid = _gid()
    client.post("/group/create", json={"group_id": gid, "name": "Leaf"})
    resp = client.post("/group/delete", json={"group_id": gid})
    assert resp.status_code == 200


def test_delete_parent_with_children_returns_conflict(client):
    """F.17: Delete parent with children should return 409 Conflict."""
    root_id = _gid()
    child_id = _gid()
    
    client.post("/group/create", json={"group_id": root_id, "name": "Root"})
    client.post("/group/create", json={"group_id": child_id, "name": "Child", "parent_id": root_id})
    
    resp = client.post("/group/delete", json={"group_id": root_id})
    assert resp.status_code == 409
    assert "move or delete child groups first" in resp.json()["detail"].lower()


def test_delete_default_folder_returns_validation_error(client):
    """F.18: Delete default folder (group_id='0') should return 400."""
    # Ensure default group exists
    resp = client.post("/group/delete", json={"group_id": "0"})
    assert resp.status_code == 400
    assert "default group" in resp.json()["detail"].lower()


def test_delete_nonexistent_folder_returns_404(client):
    """F.16: Delete nonexistent folder should return 404."""
    resp = client.post("/group/delete", json={"group_id": "nonexistent_group_id"})
    assert resp.status_code == 404


def test_list_groups(client):
    """F.16: List all groups with profile counts."""
    root_id = _gid()
    child_id = _gid()
    
    client.post("/group/create", json={"group_id": root_id, "name": "Root"})
    client.post("/group/create", json={"group_id": child_id, "name": "Child", "parent_id": root_id})
    
    resp = client.get("/group/list")
    assert resp.status_code == 200
    data = resp.json()["data"]
    
    assert "list" in data
    groups = data["list"]
    
    # Find root and child in list
    root_group = next((g for g in groups if g["group_id"] == root_id), None)
    child_group = next((g for g in groups if g["group_id"] == child_id), None)
    
    assert root_group is not None
    assert child_group is not None


def test_update_folder_sort_order(client):
    """F.16: Update folder sort_order."""
    gid = _gid()
    client.post("/group/create", json={"group_id": gid, "name": "Folder", "sort_order": 5})
    resp = client.post("/group/update", json={"group_id": gid, "name": "Folder", "sort_order": 10})
    assert resp.status_code == 200
    # Verify sort_order persisted via group/list
    groups = client.get("/group/list").json()["data"]["list"]
    g = next((g for g in groups if g["group_id"] == gid), None)
    assert g is not None
    assert g["sort_order"] == 10


def test_group_tree_empty(client):
    """F.16: Group tree works with no custom groups."""
    resp = client.get("/group/tree")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "tree" in data
    assert "roots" in data
