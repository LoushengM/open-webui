import json
import time
import uuid
from typing import Any, Optional
from functools import lru_cache

from sqlalchemy.orm import Session
from open_webui.internal.db import Base, get_db, get_db_context
from open_webui.models.groups import Groups
from open_webui.utils.access_control import has_access
from open_webui.models.users import User, UserModel, Users, UserResponse


from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import BigInteger, Boolean, Column, String, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB


from sqlalchemy import or_, func, select, and_, text, cast, or_, and_, func
from sqlalchemy.sql import exists

####################
# Note DB Schema
####################


class Note(Base):
    __tablename__ = "note"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text)

    title = Column(Text)
    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    access_control = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


DOCUMENT_SCHEMA_VERSION = 2


class NoteContentModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    json_content: Optional[dict[str, Any]] = Field(
        default=None,
        alias="json",
        serialization_alias="json",
    )
    html: Optional[str] = None
    md: Optional[str] = None


class NoteCommentModel(BaseModel):
    id: str
    author_id: Optional[str] = None
    content: Optional[str] = None
    anchor: Optional[dict[str, Any]] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class NoteRevisionModel(BaseModel):
    id: str
    author_id: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[int] = None
    delta: Optional[dict[str, Any]] = None


class NoteFootnoteModel(BaseModel):
    id: str
    content: Optional[str] = None
    anchor: Optional[dict[str, Any]] = None


class NoteReferenceModel(BaseModel):
    id: str
    type: Optional[str] = None
    value: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NoteDocumentModel(BaseModel):
    sections: list[dict[str, Any]] = Field(default_factory=list)
    page_settings: dict[str, Any] = Field(default_factory=dict)
    styles: dict[str, Any] = Field(default_factory=dict)
    comments: list[NoteCommentModel] = Field(default_factory=list)
    revisions: list[NoteRevisionModel] = Field(default_factory=list)
    footnotes: list[NoteFootnoteModel] = Field(default_factory=list)
    references: list[NoteReferenceModel] = Field(default_factory=list)


class NoteDataModel(BaseModel):
    content: NoteContentModel = Field(default_factory=NoteContentModel)
    document_schema_version: int = DOCUMENT_SCHEMA_VERSION
    document: NoteDocumentModel = Field(default_factory=NoteDocumentModel)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_shape(cls, value: Any):
        if value is None:
            return {}

        if not isinstance(value, dict):
            return value

        raw_content = value.get("content")
        if isinstance(raw_content, NoteContentModel):
            content = raw_content.model_dump(exclude_none=True, by_alias=True)
        elif isinstance(raw_content, dict):
            content = raw_content
        else:
            content = {}

        # Legacy shape support: direct json/html/md at root.
        for key in ("json", "html", "md"):
            if key in value and key not in content:
                content[key] = value.get(key)

        document = value.get("document")
        if isinstance(document, NoteDocumentModel):
            document = document.model_dump(exclude_none=True)
        elif not isinstance(document, dict):
            document = {}

        document = {
            "sections": document.get("sections") if isinstance(document.get("sections"), list) else [],
            "page_settings": document.get("page_settings") if isinstance(document.get("page_settings"), dict) else {},
            "styles": document.get("styles") if isinstance(document.get("styles"), dict) else {},
            "comments": document.get("comments") if isinstance(document.get("comments"), list) else [],
            "revisions": document.get("revisions") if isinstance(document.get("revisions"), list) else [],
            "footnotes": document.get("footnotes") if isinstance(document.get("footnotes"), list) else [],
            "references": document.get("references") if isinstance(document.get("references"), list) else [],
        }

        return {
            "content": content,
            "document_schema_version": value.get(
                "document_schema_version", DOCUMENT_SCHEMA_VERSION
            ),
            "document": document,
        }


def _document_has_extended_features(document: NoteDocumentModel) -> bool:
    return any(
        [
            bool(document.sections),
            bool(document.page_settings),
            bool(document.styles),
            bool(document.comments),
            bool(document.revisions),
            bool(document.footnotes),
            bool(document.references),
        ]
    )


def normalize_note_data(data: Optional[dict[str, Any] | NoteDataModel]) -> Optional[dict[str, Any]]:
    if data is None:
        return None

    normalized = NoteDataModel.model_validate(data)
    return normalized.model_dump(exclude_none=True, by_alias=True)


def maybe_downgrade_note_data(data: Optional[dict[str, Any] | NoteDataModel]) -> Optional[dict[str, Any]]:
    """Downgrade back to legacy shape when no document-level features are used."""
    if data is None:
        return None

    normalized = NoteDataModel.model_validate(data)
    if _document_has_extended_features(normalized.document):
        return normalized.model_dump(exclude_none=True, by_alias=True)

    return {"content": normalized.content.model_dump(exclude_none=True, by_alias=True)}


def merge_note_data(
    base: Optional[dict[str, Any] | NoteDataModel],
    incoming: Optional[dict[str, Any] | NoteDataModel],
):
    if incoming is None:
        return maybe_downgrade_note_data(normalize_note_data(base))

    base_model = NoteDataModel.model_validate(base or {})

    incoming_payload = (
        incoming.model_dump(exclude_none=True, by_alias=True)
        if isinstance(incoming, NoteDataModel)
        else incoming
    )
    incoming_payload = incoming_payload or {}

    incoming_content = incoming_payload.get("content")
    if not isinstance(incoming_content, dict):
        incoming_content = {
            key: incoming_payload.get(key)
            for key in ("json", "html", "md")
            if key in incoming_payload
        }

    merged_content = NoteContentModel.model_validate(
        {
            **base_model.content.model_dump(exclude_none=True, by_alias=True),
            **incoming_content,
        }
    )

    merged_document = base_model.document.model_dump(exclude_none=True)
    incoming_document = incoming_payload.get("document")
    if isinstance(incoming_document, dict):
        merged_document.update(incoming_document)

    merged = NoteDataModel(
        content=merged_content,
        document_schema_version=max(
            base_model.document_schema_version,
            incoming_payload.get("document_schema_version", DOCUMENT_SCHEMA_VERSION),
        ),
        document=NoteDocumentModel.model_validate(merged_document),
    )

    return maybe_downgrade_note_data(merged.model_dump(exclude_none=True, by_alias=True))


class NoteModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str

    title: str
    data: Optional[NoteDataModel | dict[str, Any]] = None
    meta: Optional[dict] = None

    access_control: Optional[dict] = None

    created_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch


####################
# Forms
####################


class NoteForm(BaseModel):
    title: str
    data: Optional[NoteDataModel | dict[str, Any]] = None
    meta: Optional[dict] = None
    access_control: Optional[dict] = None


class NoteUpdateForm(BaseModel):
    title: Optional[str] = None
    data: Optional[NoteDataModel | dict[str, Any]] = None
    meta: Optional[dict] = None
    access_control: Optional[dict] = None




class NoteRevisionForm(BaseModel):
    update: list[int]
    content: Optional[dict] = None


class NoteCommentForm(BaseModel):
    text: str
    anchor_from: int
    anchor_to: int


class NoteCommentUpdateForm(BaseModel):
    text: Optional[str] = None
    anchor_from: Optional[int] = None
    anchor_to: Optional[int] = None
    resolved: Optional[bool] = None

class NoteUserResponse(NoteModel):
    user: Optional[UserResponse] = None


class NoteItemResponse(BaseModel):
    id: str
    title: str
    data: Optional[NoteDataModel | dict[str, Any]]
    updated_at: int
    created_at: int
    user: Optional[UserResponse] = None


class NoteListResponse(BaseModel):
    items: list[NoteUserResponse]
    total: int


class NoteTable:
    def _has_permission(self, db, query, filter: dict, permission: str = "read"):
        group_ids = filter.get("group_ids", [])
        user_id = filter.get("user_id")
        dialect_name = db.bind.dialect.name

        conditions = []

        # Handle read_only permission separately
        if permission == "read_only":
            # For read_only, we want items where:
            # 1. User has explicit read permission (via groups or user-level)
            # 2. BUT does NOT have write permission
            # 3. Public items are NOT considered read_only

            read_conditions = []

            # Group-level read permission
            if group_ids:
                group_read_conditions = []
                for gid in group_ids:
                    if dialect_name == "sqlite":
                        group_read_conditions.append(
                            Note.access_control["read"]["group_ids"].contains([gid])
                        )
                    elif dialect_name == "postgresql":
                        group_read_conditions.append(
                            cast(
                                Note.access_control["read"]["group_ids"],
                                JSONB,
                            ).contains([gid])
                        )

                if group_read_conditions:
                    read_conditions.append(or_(*group_read_conditions))

            # Combine read conditions
            if read_conditions:
                has_read = or_(*read_conditions)
            else:
                # If no read conditions, return empty result
                return query.filter(False)

            # Now exclude items where user has write permission
            write_exclusions = []

            # Exclude items owned by user (they have implicit write)
            if user_id:
                write_exclusions.append(Note.user_id != user_id)

            # Exclude items where user has explicit write permission via groups
            if group_ids:
                group_write_conditions = []
                for gid in group_ids:
                    if dialect_name == "sqlite":
                        group_write_conditions.append(
                            Note.access_control["write"]["group_ids"].contains([gid])
                        )
                    elif dialect_name == "postgresql":
                        group_write_conditions.append(
                            cast(
                                Note.access_control["write"]["group_ids"],
                                JSONB,
                            ).contains([gid])
                        )

                if group_write_conditions:
                    # User should NOT have write permission
                    write_exclusions.append(~or_(*group_write_conditions))

            # Exclude public items (items without access_control)
            write_exclusions.append(Note.access_control.isnot(None))
            write_exclusions.append(cast(Note.access_control, String) != "null")

            # Combine: has read AND does not have write AND not public
            if write_exclusions:
                query = query.filter(and_(has_read, *write_exclusions))
            else:
                query = query.filter(has_read)

            return query

        # Original logic for other permissions (read, write, etc.)
        # Public access conditions
        if group_ids or user_id:
            conditions.extend(
                [
                    Note.access_control.is_(None),
                    cast(Note.access_control, String) == "null",
                ]
            )

        # User-level permission (owner has all permissions)
        if user_id:
            conditions.append(Note.user_id == user_id)

        # Group-level permission
        if group_ids:
            group_conditions = []
            for gid in group_ids:
                if dialect_name == "sqlite":
                    group_conditions.append(
                        Note.access_control[permission]["group_ids"].contains([gid])
                    )
                elif dialect_name == "postgresql":
                    group_conditions.append(
                        cast(
                            Note.access_control[permission]["group_ids"],
                            JSONB,
                        ).contains([gid])
                    )
            conditions.append(or_(*group_conditions))

        if conditions:
            query = query.filter(or_(*conditions))

        return query

    def insert_new_note(
        self, user_id: str, form_data: NoteForm, db: Optional[Session] = None
    ) -> Optional[NoteModel]:
        with get_db_context(db) as db:
            note = NoteModel(
                **{
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    **{
                        **form_data.model_dump(),
                        "data": maybe_downgrade_note_data(
                            normalize_note_data(form_data.data)
                        ),
                    },
                    "created_at": int(time.time_ns()),
                    "updated_at": int(time.time_ns()),
                }
            )

            new_note = Note(**note.model_dump())

            db.add(new_note)
            db.commit()
            return note

    def get_notes(
        self, skip: int = 0, limit: int = 50, db: Optional[Session] = None
    ) -> list[NoteModel]:
        with get_db_context(db) as db:
            query = db.query(Note).order_by(Note.updated_at.desc())
            if skip is not None:
                query = query.offset(skip)
            if limit is not None:
                query = query.limit(limit)
            notes = query.all()
            return [self._to_note_model(note) for note in notes]

    def _to_note_model(self, note: Note) -> NoteModel:
        note_model = NoteModel.model_validate(note)
        note_model.data = normalize_note_data(note_model.data)
        return note_model

    def search_notes(
        self,
        user_id: str,
        filter: dict = {},
        skip: int = 0,
        limit: int = 30,
        db: Optional[Session] = None,
    ) -> NoteListResponse:
        with get_db_context(db) as db:
            query = db.query(Note, User).outerjoin(User, User.id == Note.user_id)
            if filter:
                query_key = filter.get("query")
                if query_key:
                    # Normalize search by removing hyphens and spaces (e.g., "todo" matches "to-do" and "to do")
                    normalized_query = query_key.replace("-", "").replace(" ", "")
                    query = query.filter(
                        or_(
                            func.replace(
                                func.replace(Note.title, "-", ""), " ", ""
                            ).ilike(f"%{normalized_query}%"),
                            func.replace(
                                func.replace(
                                    cast(Note.data["content"]["md"], Text), "-", ""
                                ),
                                " ",
                                "",
                            ).ilike(f"%{normalized_query}%"),
                        )
                    )

                view_option = filter.get("view_option")
                if view_option == "created":
                    query = query.filter(Note.user_id == user_id)
                elif view_option == "shared":
                    query = query.filter(Note.user_id != user_id)

                # Apply access control filtering
                if "permission" in filter:
                    permission = filter["permission"]
                else:
                    permission = "write"

                query = self._has_permission(
                    db,
                    query,
                    filter,
                    permission=permission,
                )

                order_by = filter.get("order_by")
                direction = filter.get("direction")

                if order_by == "name":
                    if direction == "asc":
                        query = query.order_by(Note.title.asc())
                    else:
                        query = query.order_by(Note.title.desc())
                elif order_by == "created_at":
                    if direction == "asc":
                        query = query.order_by(Note.created_at.asc())
                    else:
                        query = query.order_by(Note.created_at.desc())
                elif order_by == "updated_at":
                    if direction == "asc":
                        query = query.order_by(Note.updated_at.asc())
                    else:
                        query = query.order_by(Note.updated_at.desc())
                else:
                    query = query.order_by(Note.updated_at.desc())

            else:
                query = query.order_by(Note.updated_at.desc())

            # Count BEFORE pagination
            total = query.count()

            if skip:
                query = query.offset(skip)
            if limit:
                query = query.limit(limit)

            items = query.all()

            notes = []
            for note, user in items:
                notes.append(
                    NoteUserResponse(
                        **self._to_note_model(note).model_dump(),
                        user=(
                            UserResponse(**UserModel.model_validate(user).model_dump())
                            if user
                            else None
                        ),
                    )
                )

            return NoteListResponse(items=notes, total=total)

    def get_notes_by_user_id(
        self,
        user_id: str,
        permission: str = "read",
        skip: int = 0,
        limit: int = 50,
        db: Optional[Session] = None,
    ) -> list[NoteModel]:
        with get_db_context(db) as db:
            user_group_ids = [
                group.id for group in Groups.get_groups_by_member_id(user_id, db=db)
            ]

            query = db.query(Note).order_by(Note.updated_at.desc())
            query = self._has_permission(
                db, query, {"user_id": user_id, "group_ids": user_group_ids}, permission
            )

            if skip is not None:
                query = query.offset(skip)
            if limit is not None:
                query = query.limit(limit)

            notes = query.all()
            return [self._to_note_model(note) for note in notes]

    def get_note_by_id(
        self, id: str, db: Optional[Session] = None
    ) -> Optional[NoteModel]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == id).first()
            return self._to_note_model(note) if note else None

    def update_note_by_id(
        self, id: str, form_data: NoteUpdateForm, db: Optional[Session] = None
    ) -> Optional[NoteModel]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == id).first()
            if not note:
                return None

            form_data = form_data.model_dump(exclude_unset=True)

            if "title" in form_data:
                note.title = form_data["title"]
            if "data" in form_data:
                note.data = merge_note_data(note.data, form_data["data"])
            if "meta" in form_data:
                note.meta = {**note.meta, **form_data["meta"]}

            if "access_control" in form_data:
                note.access_control = form_data["access_control"]

            note.updated_at = int(time.time_ns())

            db.commit()
            return self._to_note_model(note) if note else None

    def delete_note_by_id(self, id: str, db: Optional[Session] = None) -> bool:
        try:
            with get_db_context(db) as db:
                db.query(Note).filter(Note.id == id).delete()
                db.commit()
                return True
        except Exception:
            return False

    def insert_revision_event(
        self,
        note_id: str,
        user_id: str,
        user_name: str,
        update: list[int],
        content: Optional[dict] = None,
        db: Optional[Session] = None,
    ) -> Optional[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return None

            data = note.data or {}
            revisions = data.get("revisions") or []
            revision = {
                "id": str(uuid.uuid4()),
                "author_id": user_id,
                "author_name": user_name,
                "timestamp": int(time.time_ns()),
                "update": update,
                "content": content or {},
                "status": "pending",
            }
            revisions.append(revision)
            data["revisions"] = revisions
            note.data = data
            note.updated_at = int(time.time_ns())
            db.commit()
            return revision

    def get_note_revisions(self, note_id: str, db: Optional[Session] = None) -> list[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return []
            return (note.data or {}).get("revisions") or []

    def update_revision_status(
        self, note_id: str, revision_id: str, status: str, db: Optional[Session] = None
    ) -> Optional[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return None

            data = note.data or {}
            revisions = data.get("revisions") or []
            updated_revision = None
            for revision in revisions:
                if revision.get("id") == revision_id:
                    revision["status"] = status
                    revision["reviewed_at"] = int(time.time_ns())
                    updated_revision = revision
                    break

            if not updated_revision:
                return None

            data["revisions"] = revisions
            note.data = data
            note.updated_at = int(time.time_ns())
            db.commit()
            return updated_revision

    def get_note_comments(self, note_id: str, db: Optional[Session] = None) -> list[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return []
            return (note.data or {}).get("comments") or []

    def insert_note_comment(
        self,
        note_id: str,
        user_id: str,
        user_name: str,
        form_data: NoteCommentForm,
        db: Optional[Session] = None,
    ) -> Optional[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return None

            data = note.data or {}
            comments = data.get("comments") or []
            comment = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "user_name": user_name,
                "text": form_data.text,
                "anchor_from": form_data.anchor_from,
                "anchor_to": form_data.anchor_to,
                "resolved": False,
                "created_at": int(time.time_ns()),
                "updated_at": int(time.time_ns()),
            }
            comments.append(comment)
            data["comments"] = comments
            note.data = data
            note.updated_at = int(time.time_ns())
            db.commit()
            return comment

    def update_note_comment(
        self,
        note_id: str,
        comment_id: str,
        form_data: NoteCommentUpdateForm,
        db: Optional[Session] = None,
    ) -> Optional[dict]:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return None

            data = note.data or {}
            comments = data.get("comments") or []
            payload = form_data.model_dump(exclude_unset=True)
            updated_comment = None
            for comment in comments:
                if comment.get("id") == comment_id:
                    comment.update(payload)
                    comment["updated_at"] = int(time.time_ns())
                    updated_comment = comment
                    break

            if not updated_comment:
                return None

            data["comments"] = comments
            note.data = data
            note.updated_at = int(time.time_ns())
            db.commit()
            return updated_comment

    def delete_note_comment(
        self, note_id: str, comment_id: str, db: Optional[Session] = None
    ) -> bool:
        with get_db_context(db) as db:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                return False

            data = note.data or {}
            comments = data.get("comments") or []
            updated_comments = [c for c in comments if c.get("id") != comment_id]
            if len(updated_comments) == len(comments):
                return False

            data["comments"] = updated_comments
            note.data = data
            note.updated_at = int(time.time_ns())
            db.commit()
            return True


Notes = NoteTable()
