import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { StreamingApiClient } from "../../../shared/api/client";
import type { components } from "../../../shared/api/generated";
import { Modal } from "../../../shared/components/Modal";
import { notify } from "../../../shared/components/Toaster";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "../../../shared/components/ui/alert-dialog";
import { Badge } from "../../../shared/components/ui/badge";
import { Button } from "../../../shared/components/ui/button";
import { Skeleton } from "../../../shared/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../../shared/components/ui/tabs";
import { createProjectDataApi } from "../api";
import { createDataCatalogApi } from "../catalog-api";
import { DataRecordsTable } from "../components/DataRecordsTable";
import { DataDeletionDialog } from "../components/DataDeletionDialog";
import { DataTableSourcePanel } from "../components/DataTableSourcePanel";
import { DataTableFormDialog } from "../components/DataTableFormDialog";
import { ExcelExportWorkflow } from "../components/ExcelExportWorkflow";
import { ExcelImportWizard } from "../components/ExcelImportWizard";
import { FieldEditorDialog } from "../components/FieldEditorDialog";
import { RecordQueryToolbar, composeRecordQuery, type QuickSearch } from "../components/RecordQueryToolbar";
import { readTableView, tableViewKey, type TableViewState } from "../record-return-state";
import { RecordDetailPage } from "./RecordDetailPage";
import { RecordEditPage } from "./RecordEditPage";
import { RecordFieldsView } from "../components/RecordFieldsView";
import { RecordEditorForm } from "../components/RecordEditorForm";
import type { RecordLocation } from "../../projects/types";
import { RecordEditorDialog } from "../components/RecordEditorDialog";
import { RecordStatusDialog } from "../components/RecordStatusDialog";
import { RecordStatusBatchDialog } from "../components/RecordStatusBatchDialog";
import { StatusEditorDialog } from "../components/StatusEditorDialog";
import { emptyRecordQuery, parseRecordQuery, recordQueryDraft, type FilterExpression, type RecordQuery } from "../record-query";
import { createRecordsApi, type RecordKey } from "../records-api";
import { createExcelApi } from "../excel-api";
import { createProjectFileClient } from "../project-file-client";
import { createStatusBatchApi } from "../status-batch-api";
import type { DataTableTab } from "../types";
import {
  useDataTableEditing,
  type EditingContext,
} from "../use-data-table-editing";
import { useRecordSelection } from "../use-record-selection";

type Schema = components["schemas"];
type Table = Schema["DataTableView"];
export type DataTableDetailPageProps = {
  workspaceKey: string;
  instanceId: string;
  projectId: string;
  tableId: string;
  tab: DataTableTab;
  record?: RecordLocation;
  onRecordNavigate?(record?: RecordLocation): void;
  client: StreamingApiClient;
  disabled?: boolean;
  readonly?: boolean;
  onBack(): void;
  onTabChange(tab: DataTableTab): void;
  registerLeaveGuard(guard: (() => Promise<boolean>) | null): void;
};
const labels: Record<DataTableTab, string> = {
  records: "记录",
  fields: "字段",
  statuses: "状态",
  source: "来源",
  settings: "设置",
};
const errorMessage = (value: unknown) =>
  value instanceof Error ? value.message : "读取数据失败";
const base64url = (value: unknown) => {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
};
const sanitizeQuery = (query: RecordQuery, fieldIds: Set<string>, statusIds: Set<string>): RecordQuery => {
  const walk = (node: FilterExpression): FilterExpression | null => {
    if (node.type === "compare") return fieldIds.has(node.fieldId) ? node : null;
    if (node.type === "status") return !node.statusId || statusIds.has(node.statusId) ? node : null;
    if (node.type === "not") { const item = walk(node.item); return item ? { ...node, item } : null }
    const items = node.items.map(walk).filter((item): item is FilterExpression => item !== null);
    if (node.type === "any" && items.length === 0) return null;
    return { ...node, items };
  };
  return { filter: walk(query.filter) ?? { type: "all", items: [] }, orderBy: query.orderBy.filter(order => !("fieldId" in order) || fieldIds.has(order.fieldId)) };
};
function cellLabel(value: Schema["DataCellView"]): string {
  if (!value.readable) return "不可读取";
  if (value.error) return `读取失败：${value.error}`;
  if (value.value === null) return "空值";
  if (value.value === "") return "空字符串";
  if (typeof value.value === "boolean") return value.value ? "是" : "否";
  if (typeof value.value === "object")
    return `${value.value.value}${value.value.precision === "datetime" ? ` ${value.value.offset ?? "无时区"}` : ""}`;
  return String(value.value);
}

export function DataTableDetailPage(props: DataTableDetailPageProps) {
  return (
    <DataTableDetail
      key={JSON.stringify([props.workspaceKey, props.projectId, props.tableId])}
      {...props}
    />
  );
}

function DataTableDetail({
  workspaceKey,
  instanceId,
  projectId,
  tableId,
  tab,
  record: recordLocation,
  onRecordNavigate,
  client,
  disabled = false,
  readonly = false,
  onBack,
  onTabChange,
  registerLeaveGuard,
}: DataTableDetailPageProps) {
  const cache = useQueryClient();
  const viewStateKey = tableViewKey(workspaceKey, projectId, tableId);
  const initialView = useRef<TableViewState | null>(null);
  if (!initialView.current) initialView.current = readTableView(viewStateKey);
  const [table, setTable] = useState<Table | null>(null);
  const [quickSearch, setQuickSearch] = useState<QuickSearch>(initialView.current.quickSearch);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryNotice, setQueryNotice] = useState<string | null>(null);
  const [query, setQuery] = useState<RecordQuery>(() => structuredClone(initialView.current!.query)),
    [recordPage, setRecordPage] = useState(initialView.current.page),
    [visibleFieldIds, setVisibleFieldIds] = useState<string[] | null>(() => initialView.current!.visibleFieldIds),
    [scrollY, setScrollY] = useState(initialView.current.scrollY),
    [generationWarning, setGenerationWarning] = useState<string | null>(null),
    [filterSession, setFilterSession] = useState(0);
  const [detailTarget, setDetailTarget] = useState<{
      key: RecordKey;
      generation: string;
    } | null>(null),
    [detailIntent, setDetailIntent] = useState<"view" | "status">("view"),
    [leaveOpen, setLeaveOpen] = useState(false),
    [discardTarget, setDiscardTarget] = useState<"editor" | "all">("all"),
    [editorDirty, setEditorDirty] = useState(false),
    [workflow, setWorkflow] = useState<{ kind: "batch" | "replace" | "export"; session: string } | null>(null),
    [conflictLatest, setConflictLatest] = useState<{ context: EditingContext; input: Parameters<ReturnType<typeof useDataTableEditing>["replaceEditor"]>[1]; summary: string } | null>(null),
    [conflictLoading, setConflictLoading] = useState(false),
    [conflictError, setConflictError] = useState<string | null>(null);
  const leaveResolve = useRef<((allowed: boolean) => void) | null>(null),
    leaveAction = useRef<(() => void) | null>(null),
    editorDirtyRef = useRef(editorDirty),
    workflowDirtyRef = useRef(false),
    workflowBusyRef = useRef(false),
    workflowScope = useRef({ workspaceKey, projectId, tableId, instanceId, client, disabled }),
    conflictTicket = useRef(0);
  const prefix = useMemo(
    () =>
      [
        workspaceKey,
        instanceId,
        "project-data",
        projectId,
        "table",
        tableId,
      ] as const,
    [workspaceKey, instanceId, projectId, tableId],
  );
  const tableApi = useMemo(
    () => createProjectDataApi(client, projectId),
    [client, projectId],
  );
  const tableQuery = useQuery({
    queryKey: [...prefix, "view"],
    queryFn: ({ signal }) => tableApi.get(tableId, signal),
    placeholderData: (previous) => previous,
  });
  const originRowKey = useRef<RecordKey | undefined>(initialView.current.originRowKey);
  useEffect(() => { if (recordLocation || !table) return; try { sessionStorage.setItem(viewStateKey, JSON.stringify({ identity: { workspaceKey, projectId, tableId, datasetGeneration: table.datasetGeneration }, originRowKey: originRowKey.current, query, quickSearch, page: recordPage, visibleFieldIds, scrollY })) } catch { /* view state remains usable in memory */ } }, [query, quickSearch, recordPage, scrollY, viewStateKey, visibleFieldIds, recordLocation, table, workspaceKey, projectId, tableId]);
  useEffect(() => { const save = () => { if (!recordLocation) setScrollY(window.scrollY) }; window.addEventListener("scroll", save, { passive: true }); return () => window.removeEventListener("scroll", save) }, [recordLocation]);
  useEffect(() => {
    const next = tableQuery.data;
    if (!next) return;
    if (
      table &&
      table.datasetGeneration !== next.datasetGeneration &&
      (editorDirtyRef.current || workflowDirtyRef.current)
    ) {
      setGenerationWarning("数据已更新，请先处理当前编辑草稿再载入。");
      return;
    }
    if ((table && table.datasetGeneration !== next.datasetGeneration) || (!table && initialView.current?.identity && (initialView.current.identity.datasetGeneration !== next.datasetGeneration || initialView.current.identity.workspaceKey !== workspaceKey || initialView.current.identity.projectId !== projectId || initialView.current.identity.tableId !== tableId))) {
      originRowKey.current = undefined;
      setQuery(emptyRecordQuery());
      setQuickSearch({ fieldId: null, keyword: "" });
      setQueryNotice("数据已更新，查询条件已重置。");
      setRecordPage(1);
      setVisibleFieldIds(null);
      setFilterSession((value) => value + 1);
      setDetailTarget(null);
    }
    setTable(next);
    setGenerationWarning(null);
  }, [table, tableQuery.data, workspaceKey, projectId, tableId]);
  const generation = table?.datasetGeneration;
  const catalogApi = useMemo(
    () =>
      generation
        ? createDataCatalogApi(client, {
            projectId,
            tableId,
            datasetGeneration: generation,
          })
        : null,
    [client, generation, projectId, tableId],
  );
  const catalogQuery = useQuery({
    queryKey: [...prefix, generation, "catalog"],
    queryFn: async ({ signal }) => {
      if (!catalogApi) throw new Error("数据表不可用");
      return Promise.all([
        catalogApi.fields(signal),
        catalogApi.statuses(signal),
      ]);
    },
    enabled: Boolean(catalogApi) && !generationWarning,
  });
  const recordsApi = useMemo(
    () =>
      generation
        ? createRecordsApi(client, {
            projectId,
            tableId,
            datasetGeneration: generation,
          })
        : null,
    [client, generation, projectId, tableId],
  );
  const fields = catalogQuery.data?.[0].items ?? [], statuses = catalogQuery.data?.[1].items ?? [];
  const effectiveQuery = useMemo(() => {
    if (!catalogQuery.data) return null;
    const schema = catalogQuery.data[0].items;
    try { return parseRecordQuery(recordQueryDraft(composeRecordQuery(schema, query, quickSearch)), schema, catalogQuery.data[1].items) } catch { return null }
  }, [catalogQuery.data, query, quickSearch]);
  const recordsQuery = useQuery({
    queryKey: [...prefix, generation, "records", effectiveQuery, recordPage],
    queryFn: ({ signal }) => {
      if (!recordsApi || !effectiveQuery) throw new Error("数据表不可用");
      return recordsApi.list(
        {
          filter: effectiveQuery.filter,
          orderBy: effectiveQuery.orderBy,
          page: recordPage,
          pageSize: 50,
        },
        signal,
      );
    },
    enabled: !recordLocation && Boolean(recordsApi && effectiveQuery) && !generationWarning,
  });
  const recordTarget = recordLocation && recordLocation.mode !== "create" ? { generation: recordLocation.datasetGeneration, key: recordLocation.recordKey } : detailTarget;
  const detailQuery = useQuery({
    queryKey: [
      ...prefix,
      recordTarget?.generation,
      "record",
      recordTarget?.key,
    ],
    queryFn: ({ signal }) => {
      if (
        !recordsApi ||
        !recordTarget ||
        recordTarget.generation !== generation
      )
        throw new Error("记录不可用");
      return recordsApi.get(recordTarget.key, signal);
    },
    enabled: Boolean(
      recordsApi && recordTarget && recordTarget.generation === generation,
    ),
  });
  const page = recordsQuery.data;
  const restoredScroll = useRef(false);
  useLayoutEffect(() => { if (recordLocation) { restoredScroll.current = false; return } if (!restoredScroll.current && page) { restoredScroll.current = true; window.scrollTo({ top: scrollY, behavior: "auto" }); const identity = JSON.stringify(originRowKey.current); Array.from(document.querySelectorAll<HTMLButtonElement>("[data-record-open]")).find(node => node.dataset.recordOpen === identity)?.focus({ preventScroll: true }) } }, [page, scrollY, recordLocation]);
  useEffect(() => {
    if (!catalogQuery.data) return;
    const available = new Set(catalogQuery.data[0].items.map(item => item.ref.fieldId)), availableStatuses = new Set(catalogQuery.data[1].items.map(item => item.statusId));
    if (visibleFieldIds !== null) { const next = visibleFieldIds.filter(id => available.has(id)); if (next.length !== visibleFieldIds.length) { setVisibleFieldIds(next); setQueryNotice("表结构已更新，已移除不可用的显示列。") } }
    const nextQuery = sanitizeQuery(query, available, availableStatuses);
    if (JSON.stringify(nextQuery) !== JSON.stringify(query)) { setQuery(nextQuery); setRecordPage(1); setQueryError(null); setQueryNotice("表结构已更新，已移除不可用的查询条件。") }
    if (!catalogQuery.data[0].items.some(field => field.ref.fieldId === quickSearch.fieldId && field.type === "string")) {
      const first = catalogQuery.data[0].items.find(field => field.type === "string")?.ref.fieldId ?? null;
      if (quickSearch.fieldId !== first || quickSearch.keyword) { setQuickSearch({ fieldId: first, keyword: "" }); if (quickSearch.keyword) { setRecordPage(1); setQueryNotice("搜索字段已变更，请重新搜索。") } }
    }
  }, [catalogQuery.data, query, quickSearch, visibleFieldIds]);
  const selection = useRecordSelection({ workspaceKey, projectId, tableId, datasetGeneration: generation ?? "" });
  const context = useMemo<EditingContext | null>(
    () =>
      table && generation && !generationWarning && catalogQuery.data
        ? {
            scope: {
              workspaceKey,
              projectId,
              tableId,
              datasetGeneration: generation,
            },
            table,
            fields: catalogQuery.data[0],
            statuses: catalogQuery.data[1],
          }
        : null,
    [
      catalogQuery.data,
      generation,
      generationWarning,
      projectId,
      table,
      tableId,
      workspaceKey,
    ],
  );
  const editing = useDataTableEditing({
    workspaceKey,
    context,
    client,
    instanceId,
    disabled,
    readonly,
    onSaved: (kind, operationKey, result) => {
      editorDirtyRef.current = false; setEditorDirty(false);
      if (recordLocation && onRecordNavigate) {
        if ((kind === "recordCreate" || kind === "recordEdit" || kind === "recordStatus") && result && typeof result === "object" && "ref" in result) {
          const saved = result as Schema["DataRecordView"];
          cache.setQueryData([...prefix, saved.ref.datasetGeneration, "record", saved.ref.recordKey], saved);
          if (kind !== "recordStatus" || recordLocation.mode === "create" || recordLocation.datasetGeneration !== saved.ref.datasetGeneration || recordLocation.recordKey.type !== saved.ref.recordKey.type || recordLocation.recordKey.value !== saved.ref.recordKey.value) queueMicrotask(() => onRecordNavigate({ mode: "detail", datasetGeneration: saved.ref.datasetGeneration, recordKey: saved.ref.recordKey }));
        } else if (kind === "recordDelete") queueMicrotask(() => onRecordNavigate());
      }
      void cache.invalidateQueries({ queryKey: prefix });
      void cache.invalidateQueries({
        queryKey: [
          workspaceKey,
          instanceId,
          "project-data",
          projectId,
          "tables",
        ],
      });
      if (kind === "recordDelete") setDetailTarget(null);
      notify({
        title: ({ tableEdit: "数据表已保存", recordCreate: "记录已创建", recordEdit: "记录已保存", recordStatus: "业务状态已更新", recordDelete: "记录已删除", fieldCreate: "字段已创建", fieldEdit: "字段已保存", statusCreate: "业务状态已创建", statusEdit: "业务状态已保存", statusDelete: "业务状态已删除" })[kind],
        tone: "success",
        operationId: JSON.stringify([workspaceKey, projectId, tableId, generation, operationKey]),
      });
    },
  });
  const activatedRecordRoute = useRef<string | null>(null);
  const routeIdentity = recordLocation ? JSON.stringify(recordLocation) : null;
  useEffect(() => {
    if (activatedRecordRoute.current !== routeIdentity) {
      if (editing.recoveryBlocked || !editing.canLeave()) return;
      if (editing.editor && !editing.close()) return;
      editorDirtyRef.current = false; setEditorDirty(false);
      if (!recordLocation) { activatedRecordRoute.current = null; return }
      if (!context || disabled || generationWarning) return;
      if (recordLocation.mode !== "create" && (!detailQuery.data || recordLocation.datasetGeneration !== generation)) return;
      if (recordLocation.mode === "create") editing.open({ kind: "recordCreate" });
      else if (recordLocation.mode === "edit") editing.open({ kind: "recordEdit", record: detailQuery.data! });
      activatedRecordRoute.current = routeIdentity;
    }
  }, [recordLocation, routeIdentity, context, disabled, generationWarning, generation, detailQuery.data, editing]);
  useEffect(() => {
    if (recordLocation?.mode === "detail" && recordLocation.datasetGeneration === generation && context && detailQuery.data && !editing.editor && !editing.busy && !editing.recoveryBlocked && editing.canLeave() && !disabled && !generationWarning) {
      editing.open({ kind: "recordStatus", record: detailQuery.data });
    }
  }, [recordLocation, generation, context, detailQuery.data, editing, disabled, generationWarning]);
  const stableWorkflowScope = JSON.stringify([workspaceKey, projectId, tableId]);
  const workflowContext = JSON.stringify([workspaceKey, instanceId, projectId, tableId]);
  useLayoutEffect(() => { workflowScope.current = { workspaceKey, projectId, tableId, instanceId, client, disabled: disabled || Boolean(generationWarning) }; conflictTicket.current += 1; setConflictLoading(false); setConflictLatest(null); setConflictError(null) }, [client, disabled, generationWarning, instanceId, projectId, tableId, workspaceKey]);
  const files = useMemo(() => createProjectFileClient(client, window.autoflow, projectId, () => {
    const current = workflowScope.current;
    return current.workspaceKey === workspaceKey && current.projectId === projectId && current.tableId === tableId && current.instanceId === instanceId && current.client === client && !current.disabled;
  }), [client, instanceId, projectId, tableId, workspaceKey]);
  const excelApi = useMemo(() => createExcelApi(client, files, projectId), [client, files, projectId]);
  const statusBatchApi = useMemo(() => createStatusBatchApi(client, projectId, tableId), [client, projectId, tableId]);
  useLayoutEffect(() => {
    editorDirtyRef.current = editorDirty;
  }, [editorDirty]);
  const askDiscardOnce = useCallback(
    (target: "editor" | "all" = "all", action?: () => void) => {
      if (leaveResolve.current) return Promise.resolve(false);
      return new Promise<boolean>((resolve) => {
        const dirty =
          target === "editor"
            ? editorDirtyRef.current || workflowDirtyRef.current
            : editorDirtyRef.current || workflowDirtyRef.current;
        if (!dirty) {
          action?.();
          resolve(true);
          return;
        }
        leaveResolve.current = resolve;
        leaveAction.current = action ?? null;
        setDiscardTarget(target);
        setLeaveOpen(true);
      });
    },
    [],
  );
  useLayoutEffect(() => {
    registerLeaveGuard(() => {
      if (!editing.canLeave() || workflowBusyRef.current) return Promise.resolve(false);
      return !editorDirtyRef.current && !workflowDirtyRef.current
        ? Promise.resolve(true)
        : askDiscardOnce("all");
    });
    return () => registerLeaveGuard(null);
  }, [askDiscardOnce, editing, registerLeaveGuard]);
  useEffect(
    () => () => {
      leaveResolve.current?.(false);
    },
    [],
  );
  const acceptLatestGeneration = () => {
    if (!editing.canLeave()) return;
    void askDiscardOnce("all", () => {
      const next = tableQuery.data;
      if (!next) return;
      editing.close();
      closeWorkflow();
      setEditorDirty(false);
      setFilterSession((value) => value + 1);
      setQuery(emptyRecordQuery());
      setQuickSearch({ fieldId: null, keyword: "" });
      setQueryNotice("数据已更新，查询条件已重置。");
      setRecordPage(1);
      setDetailTarget(null);
      setTable(next);
      setGenerationWarning(null);
    });
  };
  useEffect(() => {
    if (detailIntent === "status" && detailQuery.data && detailTarget) {
      try {
        editing.open({ kind: "recordStatus", record: detailQuery.data });
        setDetailTarget(null);
        setDetailIntent("view");
      } catch {
        /* active editor remains authoritative */
      }
    }
  }, [detailIntent, detailQuery.data, detailTarget, editing]);
  useEffect(() => {
    if (page && recordPage > Math.max(1, Math.ceil(page.total / page.pageSize)))
      setRecordPage(Math.max(1, Math.ceil(page.total / page.pageSize)));
  }, [page, recordPage]);
  const writable = Boolean(
    context && !readonly && !disabled && !generationWarning && !editing.recoveryBlocked,
  );
  const openWorkflow = (kind: "batch" | "replace" | "export") => {
    if (disabled || workflow || editing.editor || (kind === "export" && !effectiveQuery) || (kind !== "export" && !writable) || (kind === "batch" && selection.count === 0)) return;
    workflowDirtyRef.current = false; workflowBusyRef.current = false;
    setWorkflow({ kind, session: crypto.randomUUID() });
  };
  const closeWorkflow = () => { workflowDirtyRef.current = false; workflowBusyRef.current = false; setWorkflow(null) };
  const workflowSettled = () => { selection.clear(); void cache.invalidateQueries({ queryKey: [...prefix, generation, "records"] }); void cache.invalidateQueries({ queryKey: [...prefix, generation, "catalog"] }) };
  const loadConflictLatest = async () => {
    const editor = editing.editor;
    if (!editor || !editing.conflict || disabled || conflictLoading) return;
    const ticket = ++conflictTicket.current, usedClient = client, usedInstance = instanceId;
    setConflictLoading(true); setConflictError(null); setConflictLatest(null);
    try {
      const latestTable = await tableApi.get(tableId);
      if ((editor.kind === "recordEdit" || editor.kind === "recordStatus" || editor.kind === "recordDelete") && latestTable.datasetGeneration !== editor.record.ref.datasetGeneration) throw new Error("数据已更新，原记录已失效；请保留当前草稿并返回后重新选择记录。");
      const scope = { workspaceKey, projectId, tableId, datasetGeneration: latestTable.datasetGeneration };
      const catalog = createDataCatalogApi(usedClient, scope), [latestFields, latestStatuses] = await Promise.all([catalog.fields(), catalog.statuses()]);
      const latestContext: EditingContext = { scope, table: latestTable, fields: latestFields, statuses: latestStatuses };
      let input: Parameters<typeof editing.replaceEditor>[1], summary: string;
      if (editor.kind === "recordEdit" || editor.kind === "recordStatus" || editor.kind === "recordDelete") {
        const latestRecord = await createRecordsApi(usedClient, scope).get(editor.record.ref.recordKey);
        input = { kind: editor.kind, record: latestRecord };
        summary = latestRecord.values.map(cell => `${latestFields.items.find(field => field.ref.fieldId === cell.fieldId)?.name ?? "字段"}：${cellLabel(cell)}`).join("；") || "记录当前没有字段值";
      } else if (editor.kind === "fieldEdit") {
        const latestField = latestFields.items.find(field => field.ref.fieldId === editor.field.ref.fieldId); if (!latestField) throw new Error("该字段已不存在");
        input = { kind: editor.kind, field: latestField }; summary = `字段“${latestField.name}”的最新定义已载入`;
      } else if (editor.kind === "statusEdit" || editor.kind === "statusDelete") {
        const latestStatus = latestStatuses.items.find(status => status.statusId === editor.status.statusId); if (!latestStatus) throw new Error("该业务状态已不存在");
        input = { kind: editor.kind, status: latestStatus }; summary = `业务状态“${latestStatus.name}”的最新资料已载入`;
      } else { input = { kind: editor.kind }; summary = "数据表的最新结构已载入" }
      const current = workflowScope.current;
      if (ticket !== conflictTicket.current || current.client !== usedClient || current.instanceId !== usedInstance || current.workspaceKey !== workspaceKey || current.projectId !== projectId || current.tableId !== tableId) return;
      setConflictLatest({ context: latestContext, input, summary });
    } catch (caught) { if (ticket === conflictTicket.current) setConflictError(errorMessage(caught)) }
    finally { if (ticket === conflictTicket.current) setConflictLoading(false) }
  };
  const closeEditor = () =>
    askDiscardOnce("editor", () => {
      editing.close();
      setEditorDirty(false);
    });
  const errorActions = editing.notAccepted ? (
    <div className="flex gap-2">
      <Button
        onClick={() => void editing.retryOriginal().catch(() => undefined)}
      >
        重试原请求
      </Button>
      <Button variant="ghost" onClick={() => editing.discardUnaccepted()}>
        放弃未接受请求
      </Button>
    </div>
  ) : editing.conflict ? (
    <Button disabled={disabled || conflictLoading} onClick={() => void loadConflictLatest()}>
      载入最新资料
    </Button>
  ) : undefined;
  const routeRecord = recordLocation && recordLocation.mode !== "create" && recordLocation.datasetGeneration === generation ? detailQuery.data : undefined;
  const routeError = recordLocation && recordLocation.mode !== "create" && table && recordLocation.datasetGeneration !== generation
    ? "这条记录属于已替换的数据，请返回记录列表选择当前记录。"
    : detailQuery.error ? errorMessage(detailQuery.error) : catalogQuery.error ? errorMessage(catalogQuery.error) : null;
  const candidateEditor = editing.editor?.kind === "recordCreate" || editing.editor?.kind === "recordEdit" ? editing.editor : null;
  const matchesRoute = (ref: Schema["DataRecordRef"]) => recordLocation && recordLocation.mode !== "create" && ref.projectId === projectId && ref.tableId === tableId && ref.datasetGeneration === recordLocation.datasetGeneration && ref.recordKey.type === recordLocation.recordKey.type && ref.recordKey.value === recordLocation.recordKey.value;
  const recordEditor = candidateEditor && candidateEditor.scope.datasetGeneration === generation && (recordLocation?.mode === "create" && candidateEditor.kind === "recordCreate" || recordLocation?.mode === "edit" && candidateEditor.kind === "recordEdit" && matchesRoute(candidateEditor.record.ref)) ? candidateEditor : null;
  const foreignRecovery = Boolean(recordLocation && editing.recoveryPending && editing.editor && !(recordEditor || (editing.editor.kind === "recordStatus" || editing.editor.kind === "recordDelete") && matchesRoute(editing.editor.record.ref)));

  const backToRecords = () => onRecordNavigate?.();
  const openRecordFromList = (record: Schema["DataRecordView"]) => {
    originRowKey.current = record.ref.recordKey;
    try { sessionStorage.setItem(viewStateKey, JSON.stringify({ identity: { workspaceKey, projectId, tableId, datasetGeneration: generation }, originRowKey: record.ref.recordKey, query, quickSearch, page: recordPage, visibleFieldIds, scrollY: window.scrollY })) } catch { /* retain the in-memory return context */ }
    onRecordNavigate?.({ mode: "detail", datasetGeneration: record.ref.datasetGeneration, recordKey: record.ref.recordKey });
  };
  const recordContent = recordLocation?.mode === "detail" ? <RecordDetailPage
    title={routeRecord ? fields.map(field => routeRecord.values.find(cell => cell.fieldId === field.ref.fieldId && cell.readable && !cell.error && typeof cell.value === "string" && cell.value)).find(Boolean)?.value as string || "记录详情" : "记录详情"}
    loading={detailQuery.isFetching || catalogQuery.isPending} error={routeError} readonly={!writable} disabled={disabled || editing.busy || editing.recoveryPending}
    fieldsView={routeRecord && catalogQuery.data ? <RecordFieldsView key={JSON.stringify([workspaceKey, instanceId, routeRecord.ref])} fields={fields} record={routeRecord} /> : undefined}
    statusForm={routeRecord && editing.editor?.kind === "recordStatus" && matchesRoute(editing.editor.record.ref) ? <RecordStatusDialog key={editing.editor.session} presentation="inline" open sessionKey={editing.editor.session} submissionEpoch={instanceId}
      record={editing.editor.record} statuses={editing.editor.statuses.items} readonly={!writable} saving={editing.busy && editing.recoveryPending} recoveryPending={editing.recoveryPending} error={editing.error} errorActions={errorActions}
      onSubmit={editing.submitRecordStatus} onRecover={editing.recover} onOpenChange={() => undefined} onRequestClose={closeEditor}
      onDirtyChange={value => { editing.onDirtyChange(value); editorDirtyRef.current = value; setEditorDirty(value) }} onSavingChange={editing.onSavingChange} /> : routeRecord ? <p className="text-sm">{routeRecord.statusId ? statuses.find(status => status.statusId === routeRecord.statusId)?.name ?? "状态不可用" : "未设置"}</p> : undefined}
    createdAt={routeRecord?.createdAt} updatedAt={routeRecord?.updatedAt} onBack={backToRecords}
    onEdit={() => { if (recordLocation.mode === "detail") onRecordNavigate?.({ ...recordLocation, mode: "edit" }) }}
    onDelete={() => { if (routeRecord && editing.canLeave()) void askDiscardOnce("editor", () => { editing.close(); editing.open({ kind: "recordDelete", record: routeRecord }) }) }}
    onRetry={() => { void detailQuery.refetch(); void catalogQuery.refetch() }} />
    : recordLocation ? <RecordEditPage mode={recordLocation.mode === "create" ? "create" : "edit"}
      loading={!recordEditor && !routeError && !editing.recoveryBlocked && !foreignRecovery} error={routeError} disabled={disabled || editing.busy || editing.recoveryPending} onBack={backToRecords}
      onStatus={recordLocation.mode === "edit" ? () => onRecordNavigate?.({ ...recordLocation, mode: "detail" }) : undefined}
      statusName={routeRecord?.statusId ? statuses.find(status => status.statusId === routeRecord.statusId)?.name ?? "状态不可用" : "未设置"}
      onRetry={() => { void detailQuery.refetch(); void catalogQuery.refetch() }}
      footer={<>{editorDirty ? <span className="mr-auto text-sm text-muted">未保存的修改</span> : null}<Button variant="ghost" disabled={disabled || editing.busy || editing.recoveryPending} onClick={backToRecords}>取消</Button>{editing.recoveryPending ? <Button type="submit" form="record" data-record-action="recover" disabled={disabled || editing.busy}>核对保存结果</Button> : <Button type="submit" form="record" variant="primary" disabled={disabled || editing.busy || !writable || recordLocation.mode === "edit" && !editorDirty}>{editing.busy ? "正在保存…" : recordLocation.mode === "create" ? "创建记录" : "保存修改"}</Button>}</>}
      editorForm={recordEditor ? <RecordEditorForm key={recordEditor.session} id="record" presentation="page" externalActions mode={recordEditor.kind === "recordCreate" ? "create" : "edit"}
        sessionKey={recordEditor.session} submissionEpoch={instanceId} initialSubmittedValues={recordEditor.submittedValues} fields={recordEditor.fields.items} initialRecord={recordEditor.kind === "recordEdit" ? recordEditor.record : undefined}
        identityFieldId={recordEditor.table.identity.mode === "field" ? recordEditor.table.identity.fieldId : undefined}
        saving={editing.busy && editing.recoveryPending} recoveryPending={editing.recoveryPending} readonly={readonly || !writable} error={editing.error} errorActions={errorActions}
        footerClassName="sticky bottom-0 z-10 -mx-6 -mb-6 mt-4 flex justify-end gap-2 border-t border-line bg-surface p-4"
        onCancel={backToRecords} onSubmit={editing.submitRecord} onRecover={editing.recover}
        onDirtyChange={value => { editing.onDirtyChange(value); editorDirtyRef.current = value; setEditorDirty(value) }} onSavingChange={editing.onSavingChange} /> : undefined} /> : null;
  const loadingTable = tableQuery.isPending && !table,
    tableError = tableQuery.error ? errorMessage(tableQuery.error) : null;
  if (loadingTable && !table)
    return (
      <div role="status" aria-label="正在加载数据表">
        <Skeleton className="h-28" />
      </div>
    );
  if (!table)
    return (
      <section role="alert" className="rounded-card border border-line p-6">
        <p>{tableError ?? "数据表不可用"}</p>
        <div className="flex gap-2">
          <Button onClick={() => void tableQuery.refetch()}>重新载入</Button>
          <Button variant="ghost" onClick={onBack}>
            返回数据表
          </Button>
        </div>
      </section>
    );
  return (
    <section className="grid min-w-0 gap-3" data-table-detail>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-3"><Button size="sm" variant="ghost" className="px-0" disabled={disabled} onClick={onBack}>
            返回数据表
          </Button>
          {recordLocation ? <span className="break-words text-sm text-muted">{table.name}</span> : <h1 className="m-0 break-words text-2xl font-semibold">{table.name}</h1>}
        <Badge>
          {readonly
            ? "只读"
            : table.sourceKind === "local"
              ? "本地数据"
              : table.sourceKind === "excel"
                ? "Excel 导入"
                : table.sourceKind === "sheets"
                  ? "Google Sheets"
                  : "来源未配置"}
        </Badge>
          </div>{!recordLocation ? <p className="mb-0 mt-1 truncate text-sm text-muted" title={table.description || "暂无说明"}>{table.description || "暂无说明"}</p> : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {writable && !recordLocation ? <Button disabled={Boolean(workflow || editing.editor)} onClick={() => openWorkflow("replace")}>重新导入 Excel</Button> : null}
          {tab !== "records" && !recordLocation ? <Button disabled={disabled || !effectiveQuery || Boolean(workflow || editing.editor)} onClick={() => openWorkflow("export")}>导出 Excel</Button> : null}
        </div>
      </header>
      {tableError ? (
        <p role="alert">
          {tableError}
          <Button onClick={() => void tableQuery.refetch()}>重新载入</Button>
        </p>
      ) : null}
      {generationWarning ? (
        <p role="alert">
          {generationWarning}{" "}
          <Button onClick={acceptLatestGeneration}>处理草稿并载入新数据</Button>
        </p>
      ) : null}
      {foreignRecovery ? <div role="alert" className="rounded-control border border-clay/30 bg-clay/5 p-4 text-sm"><p>另一个记录的保存结果尚未确认，请先核对原请求。当前地址的表单尚未开启。</p><Button disabled={disabled || editing.busy} onClick={() => void editing.recover().catch(() => undefined)}>核对原记录保存结果</Button>{editing.error ? <p>{editing.error}</p> : null}{errorActions}</div> : null}
      {editing.recoveryBlocked ? <p role="alert">{editing.error ?? "本地保存恢复记录异常，当前数据表已禁止写入。"}</p> : null}
      <Tabs
        value={tab}
        onValueChange={(value) => onTabChange(value as DataTableTab)}
      >
        <TabsList className="w-full justify-start overflow-x-auto">
          {(Object.keys(labels) as DataTableTab[]).map((value) => (
            <TabsTrigger key={value} value={value} disabled={disabled}>
              {labels[value]}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="records" className="grid gap-3">
          {!recordLocation ? <>
          <RecordQueryToolbar
            fields={fields} statuses={statuses} query={query} visibleFieldIds={visibleFieldIds} quickSearch={quickSearch}
            resetKey={`${projectId}:${tableId}:${generation}:${table.tableRevision}:${catalogQuery.data?.[0].tableRevision}:${filterSession}`}
            disabled={disabled || Boolean(generationWarning) || !catalogQuery.data || Boolean(workflow || editing.editor)} readonly={!writable}
            exportDisabled={!effectiveQuery} queryError={queryError ?? undefined}
            selectionCount={selection.count} onClearSelection={selection.clear}
            onCreate={() => onRecordNavigate ? onRecordNavigate({ mode: "create" }) : editing.open({ kind: "recordCreate" })} onBatchStatus={() => openWorkflow("batch")} onExport={() => { if (effectiveQuery) openWorkflow("export") }}
            onApplyQuery={next => { try { composeRecordQuery(fields, next, quickSearch); setQuery(next); setRecordPage(1); setQueryError(null); return true } catch (error) { setQueryError(errorMessage(error)); return false } }}
            onApplySearch={next => { try { composeRecordQuery(fields, query, next); setQuickSearch(next); setRecordPage(1); setQueryError(null); return true } catch (error) { setQueryError(errorMessage(error)); return false } }}
            onApplyColumns={setVisibleFieldIds}
          />
          {catalogQuery.data && !effectiveQuery && !generationWarning ? <p role="alert" className="text-sm text-danger">当前查询条件不可用，请调整筛选或清空搜索后重试。</p> : null}
          {queryNotice ? <p role="status" className="text-sm text-muted">{queryNotice}</p> : null}
          <DataRecordsTable
            toolbar={false}
            page={page}
            fields={fields}
            statuses={statuses}
            visibleFieldIds={visibleFieldIds ?? undefined}
            loading={recordsQuery.isFetching || catalogQuery.isFetching}
            error={
              recordsQuery.error
                ? errorMessage(recordsQuery.error)
                : catalogQuery.error
                  ? errorMessage(catalogQuery.error)
                  : undefined
            }
            hasFilters={
              Boolean(quickSearch.keyword) || query.filter.type !== "all" ||
              query.filter.items.length > 0 ||
              query.orderBy.length > 0
            }
            readonly={!writable}
            disabled={disabled || Boolean(generationWarning)}
            selection={selection}
            onBulkStatus={writable ? () => openWorkflow("batch") : undefined}
            onRetry={() =>
              void (catalogQuery.error
                ? catalogQuery.refetch()
                : recordsQuery.refetch())
            }
            onCreate={
              writable
                ? () => onRecordNavigate ? onRecordNavigate({ mode: "create" }) : editing.open({ kind: "recordCreate" })
                : undefined
            }
            onStatusChange={
              writable
                ? (record) => {
                    originRowKey.current = record.ref.recordKey;
              if (onRecordNavigate) { openRecordFromList(record); return }
                    setDetailIntent("status");
                    setDetailTarget({
                      key: record.ref.recordKey,
                      generation: record.ref.datasetGeneration,
                    });
                  }
                : undefined
            }
            onOpen={(record) => {
              originRowKey.current = record.ref.recordKey;
              if (onRecordNavigate) { openRecordFromList(record); return }
              setDetailIntent("view");
              setDetailTarget({
                key: record.ref.recordKey,
                generation: record.ref.datasetGeneration,
              });
            }}
            onPageChange={setRecordPage}
          />
          </> : recordContent}
        </TabsContent>
        <TabsContent value="fields">
          <section aria-label="字段目录" className="grid gap-3">
            {writable ? (
              <div>
                <Button
                  variant="primary"
                  onClick={() => editing.open({ kind: "fieldCreate" })}
                >
                  新建字段
                </Button>
              </div>
            ) : null}
            {catalogQuery.isPending ? (
              <Skeleton className="h-24" />
            ) : catalogQuery.error ? (
              <p role="alert">
                {errorMessage(catalogQuery.error)}{" "}
                <Button onClick={() => void catalogQuery.refetch()}>
                  重新载入
                </Button>
              </p>
            ) : fields.length === 0 ? (
              <p>暂无字段</p>
            ) : (
              fields.map((field) => (
                <article
                  key={field.ref.fieldId}
                  className="rounded-card border border-line p-4"
                >
                  <h2 className="m-0 break-words text-base font-semibold">
                    {field.name}
                  </h2>
                  <p className="text-sm text-muted">
                    {field.type === "string"
                      ? "文本"
                      : field.type === "number"
                        ? "数字"
                        : field.type === "boolean"
                          ? "布尔"
                          : "日期"}{" "}
                    · {field.required ? "必填" : "可选"} ·{" "}
                    {field.formula
                      ? "公式字段"
                      : field.writable
                        ? "可写"
                        : "只读"}
                  </p>
                  {writable && field.writable && !field.formula ? (
                    <Button
                      variant="ghost"
                      aria-label={`编辑字段 ${field.name}`}
                      onClick={() => editing.open({ kind: "fieldEdit", field })}
                    >
                      编辑
                    </Button>
                  ) : null}
                </article>
              ))
            )}
          </section>
        </TabsContent>
        <TabsContent value="statuses">
          <section aria-label="状态目录" className="grid gap-3">
            {writable ? (
              <div>
                <Button
                  variant="primary"
                  onClick={() => editing.open({ kind: "statusCreate" })}
                >
                  新建状态
                </Button>
              </div>
            ) : null}
            {catalogQuery.isPending ? (
              <Skeleton className="h-24" />
            ) : catalogQuery.error ? (
              <p role="alert">
                {errorMessage(catalogQuery.error)}{" "}
                <Button onClick={() => void catalogQuery.refetch()}>
                  重新载入
                </Button>
              </p>
            ) : statuses.length === 0 ? (
              <p>暂无状态</p>
            ) : (
              statuses.map((status) => (
                <article
                  key={status.statusId}
                  className="flex flex-wrap items-center gap-3 rounded-card border border-line p-4"
                >
                  <span
                    aria-label={`颜色 ${status.color}`}
                    className="h-4 w-4 rounded-full"
                    style={{ backgroundColor: status.color }}
                  />
                  <strong>{status.name}</strong>
                  <span className="text-sm text-muted">顺序 {status.order}</span>
                  {writable ? (
                    <>
                      <Button
                        variant="ghost"
                        aria-label={`编辑状态 ${status.name}`}
                        onClick={() =>
                          editing.open({ kind: "statusEdit", status })
                        }
                      >
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label={`删除状态 ${status.name}`}
                        onClick={() =>
                          editing.open({ kind: "statusDelete", status })
                        }
                      >
                        删除
                      </Button>
                    </>
                  ) : null}
                </article>
              ))
            )}
          </section>
        </TabsContent>
        <TabsContent value="source">
          <DataTableSourcePanel table={table} />
        </TabsContent>
        <TabsContent value="settings">
          <section className="grid gap-4 rounded-card border border-line p-5">
          {writable ? <div><Button onClick={() => editing.open({ kind: "tableEdit" })}>编辑数据表</Button></div> : null}
          <dl className="grid gap-3">
            <dt>名称</dt>
            <dd className="break-words">{table.name}</dd>
            <dt>说明</dt>
            <dd className="break-words">{table.description || "暂无说明"}</dd>
            <dt>更新时间</dt>
            <dd>{table.updatedAt}</dd>
          </dl>
          </section>
        </TabsContent>
      </Tabs>
      <Modal
        open={detailTarget !== null && detailIntent === "view"}
        onOpenChange={(open) => {
          if (!open) setDetailTarget(null);
        }}
        title="记录详情"
        description={
          detailTarget
            ? `${detailTarget.key.type} · ${detailTarget.key.value}`
            : ""
        }
        size="small"
      >
        <div className="grid gap-3">
          {detailQuery.error ? (
            <p role="alert">
              {errorMessage(detailQuery.error)}{" "}
              <Button onClick={() => void detailQuery.refetch()}>
                重新载入
              </Button>
            </p>
          ) : !detailQuery.data ? (
            <Skeleton className="h-24" />
          ) : (
            <>
              {detailQuery.data.values.map((cell) => (
                <div key={cell.fieldId}>
                  <strong>
                    {fields.find((field) => field.ref.fieldId === cell.fieldId)
                      ?.name ?? cell.fieldId}
                  </strong>
                  <p className="whitespace-pre-wrap break-words">
                    {cellLabel(cell)}
                  </p>
                </div>
              ))}
              {writable ? (
                <div className="flex gap-2">
                  <Button
                    onClick={() => {
                      editing.open({
                        kind: "recordEdit",
                        record: detailQuery.data!,
                      });
                      setDetailTarget(null);
                    }}
                  >
                    编辑记录
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => {
                      editing.open({
                        kind: "recordDelete",
                        record: detailQuery.data!,
                      });
                      setDetailTarget(null);
                    }}
                  >
                    删除记录
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </Modal>
      {editing.editor?.kind === "tableEdit" ? <DataTableFormDialog key={editing.editor.session} open mode="edit" sessionKey={editing.editor.session} submissionEpoch={instanceId} initialValues={{ name: editing.editor.table.name, description: editing.editor.table.description }} saving={editing.busy && editing.recoveryPending} recoveryPending={editing.recoveryPending} readonly={readonly || !writable} error={editing.error} errorActions={errorActions}
        onOpenChange={open => { if (!open) editing.close() }} onRequestClose={closeEditor} onSubmit={editing.submitTable} onRecover={editing.recover}
        onDirtyChange={value => { editing.onDirtyChange(value); setEditorDirty(value) }} onSavingChange={editing.onSavingChange} /> : null}
      {!recordLocation && (editing.editor?.kind === "recordCreate" ||
      editing.editor?.kind === "recordEdit") ? (
        <RecordEditorDialog
          key={editing.editor.session}
          open
          mode={editing.editor.kind === "recordCreate" ? "create" : "edit"}
          sessionKey={editing.editor.session}
          submissionEpoch={instanceId}
          fields={editing.editor.fields.items}
          initialRecord={
            editing.editor.kind === "recordEdit"
              ? editing.editor.record
              : undefined
          }
          identityFieldId={
            editing.editor.table.identity.mode === "field"
              ? editing.editor.table.identity.fieldId
              : undefined
          }
          saving={editing.busy && editing.recoveryPending}
          recoveryPending={editing.recoveryPending}
          readonly={readonly || !writable}
          error={editing.error}
          errorActions={errorActions}
          onOpenChange={(open) => {
            if (!open) editing.close();
          }}
          onRequestClose={closeEditor}
          onSubmit={editing.submitRecord}
          onRecover={editing.recover}
          onDirtyChange={(value) => {
            editing.onDirtyChange(value);
            setEditorDirty(value);
          }}
          onSavingChange={editing.onSavingChange}
        />
      ) : null}
      {editing.editor?.kind === "fieldCreate" ||
      editing.editor?.kind === "fieldEdit" ? (
        <FieldEditorDialog
          key={editing.editor.session}
          open
          mode={editing.editor.kind === "fieldCreate" ? "create" : "edit"}
          sessionKey={editing.editor.session}
          submissionEpoch={instanceId}
          initialField={
            editing.editor.kind === "fieldEdit"
              ? editing.editor.field
              : undefined
          }
          isIdentityField={
            editing.editor.kind === "fieldEdit" &&
            editing.editor.table.identity.mode === "field" &&
            editing.editor.table.identity.fieldId ===
              editing.editor.field.ref.fieldId
          }
          saving={editing.busy && editing.recoveryPending}
          recoveryPending={editing.recoveryPending}
          readonly={readonly || !writable}
          error={editing.error}
          errorActions={errorActions}
          onOpenChange={(open) => {
            if (!open) editing.close();
          }}
          onRequestClose={closeEditor}
          onPreview={editing.previewField}
          onSubmit={editing.submitField}
          onRecover={editing.recover}
          onDirtyChange={(value) => {
            editing.onDirtyChange(value);
            setEditorDirty(value);
          }}
          onSavingChange={editing.onSavingChange}
        />
      ) : null}
      {editing.editor?.kind === "statusCreate" ||
      editing.editor?.kind === "statusEdit" ? (
        <StatusEditorDialog
          key={editing.editor.session}
          open
          mode={editing.editor.kind === "statusCreate" ? "create" : "edit"}
          sessionKey={editing.editor.session}
          submissionEpoch={instanceId}
          initialValues={
            editing.editor.kind === "statusEdit"
              ? editing.editor.status
              : undefined
          }
          saving={editing.busy && editing.recoveryPending}
          recoveryPending={editing.recoveryPending}
          readonly={readonly || !writable}
          error={editing.error}
          errorActions={errorActions}
          onOpenChange={(open) => {
            if (!open) editing.close();
          }}
          onRequestClose={closeEditor}
          onSubmit={editing.submitStatus}
          onRecover={editing.recover}
          onDirtyChange={(value) => {
            editing.onDirtyChange(value);
            setEditorDirty(value);
          }}
          onSavingChange={editing.onSavingChange}
        />
      ) : null}
      {editing.editor?.kind === "recordStatus" && recordLocation?.mode !== "detail" ? (
        <RecordStatusDialog
          key={editing.editor.session}
          open
          sessionKey={editing.editor.session}
          submissionEpoch={instanceId}
          record={editing.editor.record}
          statuses={editing.editor.statuses.items}
          saving={editing.busy && editing.recoveryPending}
          recoveryPending={editing.recoveryPending}
          readonly={readonly || !writable}
          error={editing.error}
          errorActions={errorActions}
          onOpenChange={(open) => {
            if (!open) editing.close();
          }}
          onRequestClose={closeEditor}
          onSubmit={editing.submitRecordStatus}
          onRecover={editing.recover}
          onDirtyChange={(value) => {
            editing.onDirtyChange(value);
            setEditorDirty(value);
          }}
          onSavingChange={editing.onSavingChange}
        />
      ) : null}
      {editing.editor?.kind === "recordDelete" ||
      editing.editor?.kind === "statusDelete" ? (
        <DataDeletionDialog
          key={editing.editor.session}
          open
          kind={editing.editor.kind === "recordDelete" ? "record" : "status"}
          targetName={
            editing.editor.kind === "recordDelete"
              ? `${editing.editor.record.ref.recordKey.type} · ${editing.editor.record.ref.recordKey.value}`
              : "status" in editing.editor
                ? editing.editor.status.name
                : ""
          }
          submissionEpoch={instanceId}
          impact={editing.impact as Schema["DeletionImpactReport"] | null}
          saving={editing.busy && editing.recoveryPending}
          recoveryPending={editing.recoveryPending}
          readonly={readonly || !writable}
          error={editing.error}
          errorActions={errorActions}
          onOpenChange={(open) => {
            if (!open) editing.close();
          }}
          onRequestClose={closeEditor}
          onPreview={editing.previewDelete}
          onConfirm={editing.confirmDelete}
          onRecover={editing.recover}
        />
      ) : null}
      {workflow?.kind === "batch" ? <RecordStatusBatchDialog open sessionKey={workflow.session} contextKey={workflowContext} storageScopeKey={stableWorkflowScope} targets={selection.targets} statuses={statuses} api={statusBatchApi} readonly={!writable} disabled={disabled || Boolean(generationWarning)}
        onClose={() => { if (workflowDirtyRef.current) { void askDiscardOnce("editor", closeWorkflow) } else closeWorkflow() }}
        onDirtyChange={value => { workflowDirtyRef.current = value }} onBusyChange={value => { workflowBusyRef.current = value }}
        onSettled={workflowSettled} onCompleted={operation => notify({ title: "批量状态已更新", tone: "success", operationId: JSON.stringify([workspaceKey, operation.operationId]) })} /> : null}
      {workflow?.kind === "replace" ? <ExcelImportWizard open mode="replace" sessionKey={workflow.session} scopeKey={stableWorkflowScope} contextKey={workflowContext} api={excelApi} files={files} table={table} existingFields={fields} readonly={readonly} disabled={disabled || Boolean(generationWarning)}
        onClose={closeWorkflow} onDirtyChange={value => { workflowDirtyRef.current = value }} onBusyChange={value => { workflowBusyRef.current = value }}
        onCompleted={operation => { closeWorkflow(); if (operation.status !== "succeeded" || !operation.result || !("table" in operation.result)) return; cache.setQueryData([...prefix, "view"], operation.result.table); void cache.invalidateQueries({ queryKey: prefix }); notify({ title: "Excel 数据已更新", tone: "success", operationId: JSON.stringify([workspaceKey, operation.operationId]) }) }} /> : null}
      {workflow?.kind === "export" && effectiveQuery ? <ExcelExportWorkflow open sessionKey={workflow.session} scopeKey={stableWorkflowScope} contextKey={workflowContext} table={table} fields={fields} statuses={statuses} api={excelApi} files={files}
        filter={base64url(effectiveQuery.filter)} orderBy={base64url(effectiveQuery.orderBy)} readonly={readonly} disabled={disabled || Boolean(generationWarning)}
        onClose={closeWorkflow} onDirtyChange={value => { workflowDirtyRef.current = value }} onBusyChange={value => { workflowBusyRef.current = value }}
        onCompleted={operation => { closeWorkflow(); notify({ title: "Excel 导出已完成", tone: "success", operationId: JSON.stringify([workspaceKey, operation.operationId]) }) }} /> : null}
      <AlertDialog open={Boolean(conflictLatest || conflictError)} onOpenChange={open => { if (!open && !conflictLoading) { setConflictLatest(null); setConflictError(null) } }}><AlertDialogContent><AlertDialogTitle>用最新资料重新编辑？</AlertDialogTitle><AlertDialogDescription>{conflictError ?? conflictLatest?.summary ?? "正在载入最新资料…"}</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={conflictLoading}>保留当前草稿</Button></AlertDialogCancel>{conflictLatest ? <AlertDialogAction asChild><Button onClick={() => { editing.replaceEditor(conflictLatest.context, conflictLatest.input); setConflictLatest(null); setConflictError(null); setEditorDirty(false) }}>重新编辑</Button></AlertDialogAction> : <Button disabled={conflictLoading} onClick={() => void loadConflictLatest()}>重试载入</Button>}</div></AlertDialogContent></AlertDialog>
      <AlertDialog
        open={leaveOpen}
        onOpenChange={(next) => {
          if (!next) {
            setLeaveOpen(false);
            leaveResolve.current?.(false);
            leaveResolve.current = null;
            leaveAction.current = null;
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>放弃未保存的修改？</AlertDialogTitle>
          <AlertDialogDescription>
            {discardTarget === "editor"
              ? "未保存的记录、字段或状态修改将丢失。"
              : `${editorDirtyRef.current ? "未保存的记录、字段或状态修改；" : ""}${workflowDirtyRef.current ? "未完成的批量或文件设置；" : ""}将丢失。`}
          </AlertDialogDescription>
          <div className="flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button autoFocus>继续编辑</Button>
            </AlertDialogCancel>
            <AlertDialogAction asChild>
              <Button
                variant="danger"
                onClick={() => {
                  if (!editing.canLeave()) return;
                  const action = leaveAction.current;
                  setLeaveOpen(false);
                  if (discardTarget === "all") {
                                  setFilterSession((value) => value + 1);
                  }
                  setEditorDirty(false);
                  workflowDirtyRef.current = false;
                  editing.close();
                  closeWorkflow();
                  leaveResolve.current?.(true);
                  leaveResolve.current = null;
                  leaveAction.current = null;
                  action?.();
                }}
              >
                放弃并离开
              </Button>
            </AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
