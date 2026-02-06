import json
import logging
from typing import Optional
from urllib.parse import quote


from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from open_webui.socket.main import sio

from open_webui.models.groups import Groups
from open_webui.models.users import Users, UserResponse
from open_webui.models.notes import (
    NoteListResponse,
    Notes,
    NoteModel,
    NoteForm,
    NoteUserResponse,
    NoteCommentForm,
    NoteCommentUpdateForm,
)
from open_webui.utils.notes_docx_conversion import import_docx, export_note_to_docx

from open_webui.config import (
    BYPASS_ADMIN_ACCESS_CONTROL,
    ENABLE_ADMIN_CHAT_ACCESS,
    ENABLE_ADMIN_EXPORT,
)
from open_webui.constants import ERROR_MESSAGES


from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_access, has_permission
from open_webui.internal.db import get_session
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

router = APIRouter()

############################
# GetNotes
############################


class NoteItemResponse(BaseModel):
    id: str
    title: str
    data: Optional[dict]
    updated_at: int
    created_at: int
    user: Optional[UserResponse] = None


class NoteDocxImportResponse(BaseModel):
    note: NoteModel
    report: dict


@router.get("/", response_model=list[NoteItemResponse])
async def get_notes(
    request: Request,
    page: Optional[int] = None,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    limit = None
    skip = None
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

    notes = Notes.get_notes_by_user_id(user.id, "read", skip=skip, limit=limit, db=db)
    if not notes:
        return []

    user_ids = list(set(note.user_id for note in notes))
    users = {user.id: user for user in Users.get_users_by_user_ids(user_ids, db=db)}

    return [
        NoteUserResponse(
            **{
                **note.model_dump(),
                "user": UserResponse(**users[note.user_id].model_dump()),
            }
        )
        for note in notes
        if note.user_id in users
    ]


@router.get("/search", response_model=NoteListResponse)
async def search_notes(
    request: Request,
    query: Optional[str] = None,
    view_option: Optional[str] = None,
    permission: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    limit = None
    skip = None
    if page is not None:
        limit = 60
        skip = (page - 1) * limit

    filter = {}
    if query:
        filter["query"] = query
    if view_option:
        filter["view_option"] = view_option
    if permission:
        filter["permission"] = permission
    if order_by:
        filter["order_by"] = order_by
    if direction:
        filter["direction"] = direction

    if not user.role == "admin" or not BYPASS_ADMIN_ACCESS_CONTROL:
        groups = Groups.get_groups_by_member_id(user.id, db=db)
        if groups:
            filter["group_ids"] = [group.id for group in groups]

        filter["user_id"] = user.id

    return Notes.search_notes(user.id, filter, skip=skip, limit=limit, db=db)


############################
# CreateNewNote
############################


@router.post("/create", response_model=Optional[NoteModel])
async def create_new_note(
    request: Request,
    form_data: NoteForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    try:
        note = Notes.insert_new_note(user.id, form_data, db=db)
        return note
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetNoteById
############################


class NoteResponse(NoteModel):
    write_access: bool = False


@router.get("/{id}", response_model=Optional[NoteResponse])
async def get_note_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    note = Notes.get_note_by_id(id, db=db)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role != "admin" and (
        user.id != note.user_id
        and (
            not has_access(
                user.id, type="read", access_control=note.access_control, db=db
            )
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    write_access = (
        user.role == "admin"
        or (user.id == note.user_id)
        or has_access(
            user.id,
            type="write",
            access_control=note.access_control,
            strict=False,
            db=db,
        )
    )

    return NoteResponse(**note.model_dump(), write_access=write_access)


############################
# UpdateNoteById
############################


@router.post("/{id}/update", response_model=Optional[NoteModel])
async def update_note_by_id(
    request: Request,
    id: str,
    form_data: NoteForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    note = Notes.get_note_by_id(id, db=db)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role != "admin" and (
        user.id != note.user_id
        and not has_access(
            user.id, type="write", access_control=note.access_control, db=db
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    # Check if user can share publicly
    if (
        user.role != "admin"
        and form_data.access_control == None
        and not has_permission(
            user.id,
            "sharing.public_notes",
            request.app.state.config.USER_PERMISSIONS,
            db=db,
        )
    ):
        form_data.access_control = {}

    try:
        note = Notes.update_note_by_id(id, form_data, db=db)
        await sio.emit(
            "note-events",
            note.model_dump(),
            to=f"note:{note.id}",
        )

        return note
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )




@router.get("/{id}/revisions", response_model=list[dict])
async def get_note_revisions(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _ensure_note_access(request, id, user, db, access_type="read")
    return Notes.get_note_revisions(id, db=db)


@router.post("/{id}/revisions/{revision_id}/{action}", response_model=dict)
async def review_note_revision(
    request: Request,
    id: str,
    revision_id: str,
    action: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    note = _ensure_note_access(request, id, user, db, access_type="write")

    if action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.INVALID_INPUT)

    status_value = "accepted" if action == "accept" else "rejected"
    revision = Notes.update_revision_status(id, revision_id, status_value, db=db)
    if not revision:
        raise HTTPException(status_code=404, detail=ERROR_MESSAGES.NOT_FOUND)

    payload = {
        "note_id": id,
        "type": "revision_reviewed",
        "action": action,
        "revision": revision,
        "transformed_operations": revision.get("update", []),
        "transformed_at": revision.get("reviewed_at"),
    }

    await sio.emit("note-events", payload, to=f"note:{id}")
    await sio.emit("ydoc:revision:action", payload, room=f"doc_note:{id}")

    return payload


@router.get("/{id}/comments", response_model=list[dict])
async def get_note_comments(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _ensure_note_access(request, id, user, db, access_type="read")
    return Notes.get_note_comments(id, db=db)


@router.post("/{id}/comments/create", response_model=dict)
async def create_note_comment(
    request: Request,
    id: str,
    form_data: NoteCommentForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _ensure_note_access(request, id, user, db, access_type="write")
    comment = Notes.insert_note_comment(id, user.id, user.name, form_data, db=db)

    await sio.emit(
        "note-events",
        {"id": id, "type": "comment_created", "comment": comment},
        to=f"note:{id}",
    )
    return comment


@router.post("/{id}/comments/{comment_id}/update", response_model=dict)
async def update_note_comment(
    request: Request,
    id: str,
    comment_id: str,
    form_data: NoteCommentUpdateForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _ensure_note_access(request, id, user, db, access_type="write")
    comment = Notes.update_note_comment(id, comment_id, form_data, db=db)
    if not comment:
        raise HTTPException(status_code=404, detail=ERROR_MESSAGES.NOT_FOUND)

    await sio.emit(
        "note-events",
        {"id": id, "type": "comment_updated", "comment": comment},
        to=f"note:{id}",
    )
    return comment


@router.delete("/{id}/comments/{comment_id}/delete", response_model=bool)
async def delete_note_comment(
    request: Request,
    id: str,
    comment_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    _ensure_note_access(request, id, user, db, access_type="write")
    deleted = Notes.delete_note_comment(id, comment_id, db=db)

    if deleted:
        await sio.emit(
            "note-events",
            {"id": id, "type": "comment_deleted", "comment_id": comment_id},
            to=f"note:{id}",
        )

    return deleted

############################
# DeleteNoteById
############################


@router.delete("/{id}/delete", response_model=bool)
async def delete_note_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    note = Notes.get_note_by_id(id, db=db)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role != "admin" and (
        user.id != note.user_id
        and not has_access(
            user.id, type="write", access_control=note.access_control, db=db
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        note = Notes.delete_note_by_id(id, db=db)
        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.post("/import/docx", response_model=NoteDocxImportResponse)
async def import_note_docx(
    request: Request,
    file: UploadFile = File(...),
    store_original_attachment: bool = Form(False),
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx files are supported",
        )

    try:
        content = await file.read()
        conversion = import_docx(
            content, file.filename, store_original_attachment=store_original_attachment
        )

        meta = {
            "docx_import": {
                "report": conversion.report,
            }
        }

        if conversion.original_attachment is not None:
            meta["docx_import"]["original_attachment"] = conversion.original_attachment

        note = Notes.insert_new_note(
            user.id,
            NoteForm(
                title=conversion.title,
                data={
                    "content": {
                        "json": None,
                        "html": conversion.html,
                        "md": conversion.markdown,
                    }
                },
                meta=meta,
                access_control={},
            ),
            db=db,
        )

        return NoteDocxImportResponse(note=note, report=conversion.report)
    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DOCX import failed: {e}",
        )


@router.get("/{id}/export/docx")
async def export_note_docx(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    if user.role != "admin" and not has_permission(
        user.id, "features.notes", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    note = Notes.get_note_by_id(id, db=db)
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if user.role != "admin" and (
        user.id != note.user_id
        and (
            not has_access(
                user.id, type="read", access_control=note.access_control, db=db
            )
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    markdown_content = ((note.data or {}).get("content") or {}).get("md", "")
    title = note.title or "note"

    try:
        docx_bytes, report = export_note_to_docx(title, markdown_content)
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"DOCX export failed: {e}",
        )

    filename = f"{title}.docx"
    safe_filename = quote(filename)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
        "X-Docx-Export-Report": quote(json.dumps(report)),
    }

    return StreamingResponse(
        iter([docx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
