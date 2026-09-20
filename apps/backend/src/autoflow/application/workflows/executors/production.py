from __future__ import annotations

from .advanced_browser import ADVANCED_BROWSER_EXECUTORS
from .ai import AIChatExecutor, AIVisionExecutor
from .ai_media import AI_MEDIA_EXECUTORS
from .ai_scraper import AI_SCRAPER_EXECUTORS
from .ai_tasks import AI_TASK_EXECUTORS
from .ai_vision_act import AIVisionActExecutor
from .base import ModuleExecutor
from .basic import (
    ClickElementExecutor,
    GetElementInfoExecutor,
    InputTextExecutor,
    OpenPageExecutor,
    ScreenshotExecutor,
)
from .captcha import CAPTCHA_EXECUTORS
from .control_variable import CONTROL_VARIABLE_EXECUTORS
from .custom_module import CustomModuleExecutor
from .data_structure import (
    DictGetExecutor,
    DictKeysExecutor,
    DictOperationExecutor,
    ListExportExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListOperationExecutor,
    RegexExtractExecutor,
    StringCaseExecutor,
    StringConcatExecutor,
    StringJoinExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringSubstringExecutor,
    StringTrimExecutor,
)
from .dict_advanced import (
    DictDeepCopyExecutor,
    DictFilterExecutor,
    DictFlattenExecutor,
    DictGetPathExecutor,
    DictInvertExecutor,
    DictMapValuesExecutor,
    DictMergeExecutor,
    DictSortExecutor,
)
from .external_http import EXTERNAL_HTTP_EXECUTORS
from .firecrawl import FIRECRAWL_EXECUTORS
from .input_prompt import InputPromptExecutor
from .list_advanced import (
    ListCartesianProductExecutor,
    ListChunkExecutor,
    ListCountExecutor,
    ListDifferenceExecutor,
    ListFilterExecutor,
    ListFindExecutor,
    ListFlattenExecutor,
    ListIntersectionExecutor,
    ListMapExecutor,
    ListMergeExecutor,
    ListRemoveEmptyExecutor,
    ListReverseExecutor,
    ListSampleExecutor,
    ListShuffleExecutor,
    ListUnionExecutor,
)
from .logging import LOG_EXECUTORS
from .math_advanced import (
    MathClampExecutor,
    MathExpExecutor,
    MathFactorialExecutor,
    MathGcdExecutor,
    MathLcmExecutor,
    MathLogExecutor,
    MathPercentageExecutor,
    MathPermutationExecutor,
    MathRandomAdvancedExecutor,
    MathTrigExecutor,
)
from .math_list_ops import (
    ListAverageExecutor,
    ListMaxExecutor,
    ListMinExecutor,
    ListSliceExecutor,
    ListSortExecutor,
    ListSumExecutor,
    ListUniqueExecutor,
    MathAbsExecutor,
    MathBaseConvertExecutor,
    MathFloorExecutor,
    MathModuloExecutor,
    MathPowerExecutor,
    MathRoundExecutor,
    MathSqrtExecutor,
)
from .media_recognition import MEDIA_RECOGNITION_EXECUTORS
from .messaging import MESSAGE_EXECUTORS
from .network_capture import NetworkCaptureExecutor
from .network_monitor import (
    NetworkMonitorStartExecutor,
    NetworkMonitorStopExecutor,
    NetworkMonitorWaitExecutor,
)
from .page_load import PageLoadCompleteExecutor, WaitPageLoadExecutor
from .registry import ExecutorRegistry
from .ssh import SSH_EXECUTORS
from .statistics import (
    MedianExecutor,
    ModeExecutor,
    NormalizeExecutor,
    PercentileExecutor,
    StandardizeExecutor,
    StdevExecutor,
    VarianceExecutor,
)
from .string_convert import (
    CsvGenerateExecutor,
    CsvParseExecutor,
    ListToStringAdvancedExecutor,
)
from .subflow import SubflowExecutor
from .switch_tab import SwitchTabExecutor
from .table import (
    TableAddColumnExecutor,
    TableAddRowExecutor,
    TableClearExecutor,
    TableDeleteRowExecutor,
    TableExportExecutor,
    TableGetCellExecutor,
    TableSetCellExecutor,
)
from .table_extract import ExtractTableDataExecutor
from .utility_tools import (
    HEXToCMYKExecutor,
    MD5EncryptExecutor,
    RandomPasswordGeneratorExecutor,
    RGBToCMYKExecutor,
    RGBToHSVExecutor,
    SHAEncryptExecutor,
    TimestampConverterExecutor,
    URLEncodeDecodeExecutor,
    UUIDGeneratorExecutor,
)
from .visual import VISUAL_EXECUTORS
from .web_basic import WEB_BASIC_EXECUTORS
from .workflow_chain import RunWorkflowFileExecutor

PRODUCTION_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    CustomModuleExecutor,
    OpenPageExecutor,
    ClickElementExecutor,
    InputTextExecutor,
    GetElementInfoExecutor,
    ScreenshotExecutor,
    AIChatExecutor,
    AIVisionExecutor,
    AIVisionActExecutor,
    *AI_MEDIA_EXECUTORS,
    *AI_TASK_EXECUTORS,
    *AI_SCRAPER_EXECUTORS,
    *FIRECRAWL_EXECUTORS,
    *EXTERNAL_HTTP_EXECUTORS,
    *LOG_EXECUTORS,
    *MESSAGE_EXECUTORS,
    *SSH_EXECUTORS,
    *CAPTCHA_EXECUTORS,
    *MEDIA_RECOGNITION_EXECUTORS,
    InputPromptExecutor,
    RunWorkflowFileExecutor,
    SubflowExecutor,
    WaitPageLoadExecutor,
    PageLoadCompleteExecutor,
    ListOperationExecutor,
    ListGetExecutor,
    ListLengthExecutor,
    ListExportExecutor,
    DictOperationExecutor,
    DictGetExecutor,
    DictKeysExecutor,
    RegexExtractExecutor,
    StringReplaceExecutor,
    StringSplitExecutor,
    StringJoinExecutor,
    StringConcatExecutor,
    StringTrimExecutor,
    StringCaseExecutor,
    StringSubstringExecutor,
    ListSumExecutor,
    ListAverageExecutor,
    ListMaxExecutor,
    ListMinExecutor,
    ListSortExecutor,
    ListUniqueExecutor,
    ListSliceExecutor,
    MathRoundExecutor,
    MathBaseConvertExecutor,
    MathFloorExecutor,
    MathModuloExecutor,
    MathAbsExecutor,
    MathSqrtExecutor,
    MathPowerExecutor,
    MathLogExecutor,
    MathTrigExecutor,
    MathExpExecutor,
    MathGcdExecutor,
    MathLcmExecutor,
    MathFactorialExecutor,
    MathPermutationExecutor,
    MathPercentageExecutor,
    MathClampExecutor,
    MathRandomAdvancedExecutor,
    MedianExecutor,
    ModeExecutor,
    VarianceExecutor,
    StdevExecutor,
    PercentileExecutor,
    NormalizeExecutor,
    StandardizeExecutor,
    RandomPasswordGeneratorExecutor,
    URLEncodeDecodeExecutor,
    MD5EncryptExecutor,
    SHAEncryptExecutor,
    TimestampConverterExecutor,
    RGBToHSVExecutor,
    RGBToCMYKExecutor,
    HEXToCMYKExecutor,
    UUIDGeneratorExecutor,
    ListReverseExecutor,
    ListFindExecutor,
    ListCountExecutor,
    ListFilterExecutor,
    ListMapExecutor,
    ListMergeExecutor,
    ListFlattenExecutor,
    ListChunkExecutor,
    ListRemoveEmptyExecutor,
    ListIntersectionExecutor,
    ListUnionExecutor,
    ListDifferenceExecutor,
    ListCartesianProductExecutor,
    ListShuffleExecutor,
    ListSampleExecutor,
    DictMergeExecutor,
    DictFilterExecutor,
    DictMapValuesExecutor,
    DictInvertExecutor,
    DictSortExecutor,
    DictDeepCopyExecutor,
    DictGetPathExecutor,
    DictFlattenExecutor,
    CsvParseExecutor,
    CsvGenerateExecutor,
    ListToStringAdvancedExecutor,
    TableAddRowExecutor,
    TableAddColumnExecutor,
    TableSetCellExecutor,
    TableGetCellExecutor,
    TableDeleteRowExecutor,
    TableClearExecutor,
    TableExportExecutor,
    NetworkMonitorStartExecutor,
    NetworkMonitorWaitExecutor,
    NetworkMonitorStopExecutor,
    *WEB_BASIC_EXECUTORS,
    *ADVANCED_BROWSER_EXECUTORS,
    SwitchTabExecutor,
    ExtractTableDataExecutor,
    NetworkCaptureExecutor,
    *CONTROL_VARIABLE_EXECUTORS,
    *VISUAL_EXECUTORS,
)


def build_production_executor_registry() -> ExecutorRegistry:
    registry = ExecutorRegistry()
    for executor in PRODUCTION_EXECUTORS:
        registry.register(executor)
    return registry
