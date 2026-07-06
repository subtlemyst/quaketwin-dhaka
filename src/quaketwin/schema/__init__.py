"""Pydantic models aligned with PostGIS schema (data/schema/dhaka_graph.sql)."""

from quaketwin.schema.building import BuildingProfile
from quaketwin.schema.inventory import DataSourceRecord, DataSourceStatus

__all__ = ["BuildingProfile", "DataSourceRecord", "DataSourceStatus"]
