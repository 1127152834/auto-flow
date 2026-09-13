import type { QuickSearch } from './components/RecordQueryToolbar'
import { emptyRecordQuery, type FilterExpression, type RecordQuery } from './record-query'
import { encodeRecordKey } from './record-route'
import type { RecordKey } from './records-api'
export type RecordReturnIdentity = { workspaceKey: string; projectId: string; tableId: string; datasetGeneration: string }
const validIdentity = (value: unknown): value is RecordReturnIdentity => Boolean(value) && typeof value === 'object' && ['workspaceKey', 'projectId', 'tableId', 'datasetGeneration'].every(key => typeof (value as Record<string, unknown>)[key] === 'string' && (value as Record<string, string>)[key].length > 0)
const validKey = (value: unknown): value is RecordKey => { if (!value || typeof value !== 'object') return false; const key = value as RecordKey; if (!['text', 'integer', 'uuid'].includes(key.type) || typeof key.value !== 'string') return false; try { encodeRecordKey(key); return true } catch { return false } }
export type TableViewState = { identity?: RecordReturnIdentity; originRowKey?: RecordKey; quickSearch: QuickSearch; query: RecordQuery; page: number; visibleFieldIds: string[] | null; scrollY: number };
export const tableViewKey = (workspace: string, project: string, table: string) => `autoflow:table-view:${JSON.stringify([workspace, project, table])}`;
const validFilter = (value: unknown, depth = 1): value is FilterExpression => {
  if (!value || typeof value !== "object" || depth > 5) return false;
  const node = value as Record<string, unknown>;
  if (node.type === "compare") return typeof node.fieldId === "string" && typeof node.operator === "string";
  if (node.type === "status") return typeof node.operator === "string" && (node.statusId === undefined || typeof node.statusId === "string");
  if (node.type === "not") return validFilter(node.item, depth + 1);
  return (node.type === "all" || node.type === "any") && Array.isArray(node.items) && node.items.length <= 50 && node.items.every(item => validFilter(item, depth + 1));
};
const validOrder = (value: unknown): value is RecordQuery["orderBy"] => Array.isArray(value) && value.length <= 8 && value.every(item => {
  if (!item || typeof item !== "object") return false;
  const order = item as Record<string, unknown>;
  return (order.direction === "asc" || order.direction === "desc") && (typeof order.fieldId === "string" || ["status", "createdAt", "updatedAt", "recordKey"].includes(String(order.systemField)));
});
export const readTableView = (key: string): TableViewState => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) ?? "null") as Partial<TableViewState> | null;
    const visible = saved?.visibleFieldIds;
    return { identity: validIdentity(saved?.identity) ? saved.identity : undefined, originRowKey: validKey(saved?.originRowKey) ? saved.originRowKey : undefined, quickSearch: { fieldId: typeof saved?.quickSearch?.fieldId === "string" ? saved.quickSearch.fieldId : null, keyword: typeof saved?.quickSearch?.keyword === "string" ? saved.quickSearch.keyword : "" }, query: validFilter(saved?.query?.filter) && validOrder(saved?.query?.orderBy) ? saved.query! : emptyRecordQuery(), page: Number.isSafeInteger(saved?.page) && saved!.page! > 0 && saved!.page! <= 2147483647 ? saved!.page! : 1, visibleFieldIds: visible === null || Array.isArray(visible) && visible.length <= 1000 && visible.every(id => typeof id === "string") ? visible ?? null : null, scrollY: typeof saved?.scrollY === "number" && Number.isFinite(saved.scrollY) && saved.scrollY >= 0 ? saved.scrollY : 0 };
  } catch { return { quickSearch: { fieldId: null, keyword: "" }, query: emptyRecordQuery(), page: 1, visibleFieldIds: null, scrollY: 0 } }
};
