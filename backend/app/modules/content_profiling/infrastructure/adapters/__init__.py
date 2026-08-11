"""The in-code registry of extraction adapters, one per PackageFormat (design 13 §3.4)."""

from app.modules.content_profiling.application.ports import ExtractionAdapterPort
from app.modules.content_profiling.infrastructure.adapters.learnpack_v1 import LearnpackV1Adapter
from app.modules.content_profiling.infrastructure.adapters.learnpack_v2 import LearnpackV2Adapter

ADAPTERS_BY_FORMAT: dict[str, ExtractionAdapterPort] = {
    adapter.package_format: adapter for adapter in (LearnpackV1Adapter(), LearnpackV2Adapter())
}
