from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["building"])


@router.get("/building/list")
def list_buildings(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """List buildings (not soft-deleted)."""
    return db.list_buildings()


@router.get("/building/floors")
def list_floors(
    building_id: int | None = None,
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """List floors (including the level_3d 3D-level mapping)."""
    return db.list_floors(building_id)


@router.get("/building/cell-shapes")
def list_cell_shapes(
    building_id: int | None = None,
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """3D building cell shape settings (driven by building_cell, not soft-deleted)."""
    return db.list_cell_shapes(building_id)


@router.get("/building/floors/{floor_id}/cells")
def list_floor_cells(floor_id: int, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """List floor cells (not soft-deleted)."""
    return db.list_floor_cells(floor_id)


@router.get("/building/floors/{floor_id}/rooms")
def list_floor_rooms(floor_id: int, db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """List floor rooms (including room-cell relations, not soft-deleted)."""
    return db.list_floor_rooms(floor_id)


@router.delete("/building/rooms/{room_id}")
def delete_room(
    room_id: str,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Physically delete a room: occupied cells are released by foreign-key cascade and
        its devices fall back to lobby devices.

        Non-recoverable (a room is just a cell set and can be rebuilt). Confirm before deleting.
        """
    ok = db.delete_room(room_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"ok": True}


class AssignRoomCellRequest(BaseModel):
    floor_id: int
    row_no: int
    col_no: int


@router.post("/building/rooms/{room_id}/cells")
def assign_room_cell(
    room_id: str,
    body: AssignRoomCellRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Atomically switch room↔cell occupancy (one room per cell; removes existing)."""
    result = db.assign_room_cell(room_id, body.floor_id, body.row_no, body.col_no)
    if result == "invalid":
        raise HTTPException(status_code=404, detail="Room or cell not found")
    return {"ok": True, "result": result}


class RotationUpdate(BaseModel):
    floor_id: int
    row_no: int
    col_no: int
    rotation_xyz: str | None = None


@router.patch("/building/cell-rotation")
def update_cell_rotation(
    body: RotationUpdate,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Update a single cell's rotation (rotation_xyz)."""
    ok = db.update_cell_rotation(body.floor_id, body.row_no, body.col_no, body.rotation_xyz)
    if not ok:
        raise HTTPException(status_code=404, detail="Cell not found")
    return {"ok": True}


class AllRotationUpdate(BaseModel):
    building_id: int
    rotation_xyz: str | None = None


@router.patch("/building/cell-rotation-all")
def update_all_cells_rotation(
    body: AllRotationUpdate,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Apply the same rotation to all cells of a building."""
    count = db.update_all_cells_rotation(body.building_id, body.rotation_xyz)
    return {"ok": True, "updated": count}


class RowRotationUpdate(BaseModel):
    building_id: int
    col_no: int
    rotation_xyz: str | None = None


@router.patch("/building/cell-rotation-row")
def update_col_cells_rotation(
    body: RowRotationUpdate,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Apply the same rotation to all cells of a column."""
    count = db.update_col_cells_rotation(body.building_id, body.col_no, body.rotation_xyz)
    return {"ok": True, "updated": count}


class CellEditRequest(BaseModel):
    building_id: int
    row_no: int
    col_no: int
    action: str          # "add" | "delete"
    scope: str           # "single" | "row" | "col" | "append_row" | "append_col"
    floor_id: int | None = None  # required when scope=single
    shape: str | None = None     # "Rect" | "Cylinder" | "Triangle" (shape for new cells on add; default Rect)


class SaveFloorLayoutRequest(BaseModel):
    floor_id: int
    layout: dict[str, list[tuple[int, int]]]  # { room_id: [[row, col], ...], ... }


class ResetGridExtrasRequest(BaseModel):
    building_id: int


@router.post("/building/cell-edit")
def cell_edit(
    body: CellEditRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Add or delete cells (single / row / column)."""
    return db.cell_edit(
        building_id=body.building_id,
        row_no=body.row_no,
        col_no=body.col_no,
        action=body.action,
        scope=body.scope,
        floor_id=body.floor_id,
        shape=body.shape,
    )


@router.patch("/building/undo-edit")
def undo_edit(
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Undo the previous cell edit operation."""
    return db.undo_last_edit()


@router.post("/building/save-floor-layout")
def save_floor_layout(
    body: SaveFloorLayoutRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Batch save floor room↔cell layout (atomically replaces the whole floor's room_cell)."""
    inserted = db.save_floor_layout(body.floor_id, body.layout)
    return {"ok": True, "inserted": inserted}


@router.post("/building/reset-grid-extras")
def reset_grid_extras(
    body: ResetGridExtrasRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Delete all appended cells beyond the 8x12 grid, restoring the original grid."""
    return db.reset_grid_extras(building_id=body.building_id)
