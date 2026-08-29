"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-29

Creates all seven tables for the AI Shorts Generator:
users, refresh_tokens, projects, shorts, broll_segments, subtitle_segments,
render_jobs - with foreign keys, indexes and status CHECK constraints.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users -------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("oauth_provider", sa.String(length=50), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- refresh_tokens --------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_refresh_tokens_user_id_users",
        ),
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_token", "refresh_tokens", ["token"], unique=True
    )

    # --- projects ------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("transcript", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_projects_user_id_users",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'fetching', 'transcribing', 'analyzing', "
            "'ready', 'failed')",
            name="ck_projects_status",
        ),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)

    # --- shorts ------------------------------------------------------
    op.create_table(
        "shorts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=16), nullable=False),
        sa.Column("end_time", sa.String(length=16), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("hashtags", sa.JSON(), nullable=True),
        sa.Column("editing", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_shorts_project_id_projects",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'queued', 'rendering', 'rendered', 'failed')",
            name="ck_shorts_status",
        ),
    )
    op.create_index("ix_shorts_project_id", "shorts", ["project_id"], unique=False)

    # --- broll_segments ------------------------------------------------------
    op.create_table(
        "broll_segments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("short_id", sa.Integer(), nullable=False),
        sa.Column("start", sa.String(length=16), nullable=False),
        sa.Column("end", sa.String(length=16), nullable=False),
        sa.Column("original_start", sa.String(length=16), nullable=True),
        sa.Column("original_end", sa.String(length=16), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("search_keywords", sa.JSON(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=True),
        sa.Column("transition", sa.String(length=32), nullable=True),
        sa.Column("placement", sa.String(length=16), nullable=True),
        sa.Column(
            "use_broll",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("asset_url", sa.String(length=2048), nullable=True),
        sa.Column("asset_source", sa.String(length=32), nullable=True),
        sa.Column(
            "asset_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.ForeignKeyConstraint(
            ["short_id"],
            ["shorts.id"],
            ondelete="CASCADE",
            name="fk_broll_segments_short_id_shorts",
        ),
        sa.CheckConstraint(
            "type IS NULL OR type IN ('stock_video', 'image', 'screenshot', "
            "'screen_recording', 'chart', 'animation', 'news_image', "
            "'original_cutaway')",
            name="ck_broll_segments_type",
        ),
        sa.CheckConstraint(
            "transition IS NULL OR transition IN ('smooth_cut', 'quick_cut', "
            "'fade', 'dissolve')",
            name="ck_broll_segments_transition",
        ),
        sa.CheckConstraint(
            "placement IS NULL OR placement IN ('start', 'middle', 'end')",
            name="ck_broll_segments_placement",
        ),
        sa.CheckConstraint(
            "asset_source IS NULL OR asset_source IN ('pexels', 'pixabay', "
            "'original')",
            name="ck_broll_segments_asset_source",
        ),
        sa.CheckConstraint(
            "asset_status IN ('pending', 'fetched', 'not_found', 'skipped')",
            name="ck_broll_segments_asset_status",
        ),
    )
    op.create_index(
        "ix_broll_segments_short_id", "broll_segments", ["short_id"], unique=False
    )

    # --- subtitle_segments -------------------------------------------------
    op.create_table(
        "subtitle_segments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("short_id", sa.Integer(), nullable=False),
        sa.Column("start", sa.String(length=16), nullable=False),
        sa.Column("end", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("highlight_words", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["short_id"],
            ["shorts.id"],
            ondelete="CASCADE",
            name="fk_subtitle_segments_short_id_shorts",
        ),
    )
    op.create_index(
        "ix_subtitle_segments_short_id",
        "subtitle_segments",
        ["short_id"],
        unique=False,
    )

    # --- render_jobs -----------------------------------------------------
    op.create_table(
        "render_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("short_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "progress", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("output_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "output_format",
            sa.String(length=16),
            nullable=False,
            server_default="mp4",
        ),
        sa.Column(
            "video_codec",
            sa.String(length=16),
            nullable=False,
            server_default="h264",
        ),
        sa.Column(
            "audio_codec",
            sa.String(length=16),
            nullable=False,
            server_default="aac",
        ),
        sa.Column(
            "resolution",
            sa.String(length=16),
            nullable=False,
            server_default="1080x1920",
        ),
        sa.Column(
            "aspect_ratio",
            sa.String(length=16),
            nullable=False,
            server_default="9:16",
        ),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["short_id"],
            ["shorts.id"],
            ondelete="CASCADE",
            name="fk_render_jobs_short_id_shorts",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_render_jobs_user_id_users",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', "
            "'cancelled')",
            name="ck_render_jobs_status",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_render_jobs_progress_range",
        ),
        sa.CheckConstraint(
            "stage IS NULL OR stage IN ('downloading', 'trimming', 'broll', "
            "'captions', 'encoding', 'uploading')",
            name="ck_render_jobs_stage",
        ),
    )
    op.create_index(
        "ix_render_jobs_short_id", "render_jobs", ["short_id"], unique=False
    )
    op.create_index(
        "ix_render_jobs_user_id", "render_jobs", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_render_jobs_user_id", table_name="render_jobs")
    op.drop_index("ix_render_jobs_short_id", table_name="render_jobs")
    op.drop_table("render_jobs")

    op.drop_index(
        "ix_subtitle_segments_short_id", table_name="subtitle_segments"
    )
    op.drop_table("subtitle_segments")

    op.drop_index("ix_broll_segments_short_id", table_name="broll_segments")
    op.drop_table("broll_segments")

    op.drop_index("ix_shorts_project_id", table_name="shorts")
    op.drop_table("shorts")

    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_refresh_tokens_token", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
