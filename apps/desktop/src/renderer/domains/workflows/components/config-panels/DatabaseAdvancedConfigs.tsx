// Source: WebRPA@5ccb900e, components/workflow/config-panels/DatabaseAdvancedConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Textarea } from '../controls/textarea'
import { VariableInput } from '../controls/variable-input'
import { PathInput } from '../controls/path-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { NumberInput } from '../controls/number-input'
import { Switch } from '../controls/switch'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// Oracle连接配置
export function OracleConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || 'localhost'}
            onChange={(v) => onChange('host', v)}
            placeholder="localhost"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 1521}
            onChange={(v) => onChange('port', v)}
            defaultValue={1521}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>服务名</Label>
        <VariableInput
          value={(data.serviceName as string) || ''}
          onChange={(v) => onChange('serviceName', v)}
          placeholder="ORCL"
        />
      </div>

      <div className="space-y-2">
        <Label>用户名</Label>
        <VariableInput
          value={(data.username as string) || ''}
          onChange={(v) => onChange('username', v)}
          placeholder="system"
        />
      </div>

      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="请输入密码"
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>
    </div>
  )
}

// Oracle查询配置
export function OracleQueryConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL查询语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="SELECT * FROM table_name"
          rows={6}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'oracle_result'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="oracle_result"
        />
      </div>
    </div>
  )
}

// Oracle执行配置
export function OracleExecuteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL执行语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="INSERT INTO table_name (col1, col2) VALUES ('val1', 'val2')"
          rows={6}
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          checked={(data.autoCommit as boolean) ?? true}
          onCheckedChange={(v) => onChange('autoCommit', v)}
        />
        <Label>自动提交事务</Label>
      </div>
    </div>
  )
}

// PostgreSQL连接配置
export function PostgreSQLConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || 'localhost'}
            onChange={(v) => onChange('host', v)}
            placeholder="localhost"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 5432}
            onChange={(v) => onChange('port', v)}
            defaultValue={5432}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>数据库名</Label>
        <VariableInput
          value={(data.database as string) || ''}
          onChange={(v) => onChange('database', v)}
          placeholder="postgres"
        />
      </div>

      <div className="space-y-2">
        <Label>用户名</Label>
        <VariableInput
          value={(data.username as string) || ''}
          onChange={(v) => onChange('username', v)}
          placeholder="postgres"
        />
      </div>

      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="请输入密码"
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>
    </div>
  )
}

// PostgreSQL查询配置
export function PostgreSQLQueryConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL查询语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="SELECT * FROM table_name"
          rows={6}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'postgresql_result'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="postgresql_result"
        />
      </div>
    </div>
  )
}

// PostgreSQL执行配置
export function PostgreSQLExecuteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL执行语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="INSERT INTO table_name (col1, col2) VALUES ('val1', 'val2')"
          rows={6}
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          checked={(data.autoCommit as boolean) ?? true}
          onCheckedChange={(v) => onChange('autoCommit', v)}
        />
        <Label>自动提交事务</Label>
      </div>
    </div>
  )
}

// MongoDB连接配置
export function MongoDBConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || 'localhost'}
            onChange={(v) => onChange('host', v)}
            placeholder="localhost"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 27017}
            onChange={(v) => onChange('port', v)}
            defaultValue={27017}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>数据库名</Label>
        <VariableInput
          value={(data.database as string) || ''}
          onChange={(v) => onChange('database', v)}
          placeholder="mydb"
        />
      </div>

      <div className="space-y-2">
        <Label>用户名（可选）</Label>
        <VariableInput
          value={(data.username as string) || ''}
          onChange={(v) => onChange('username', v)}
          placeholder="留空表示无需认证"
        />
      </div>

      <div className="space-y-2">
        <Label>密码（可选）</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="留空表示无需认证"
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>
    </div>
  )
}

// MongoDB查询配置
export function MongoDBFindConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>集合名称</Label>
        <VariableInput
          value={(data.collection as string) || ''}
          onChange={(v) => onChange('collection', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>查询条件（JSON格式）</Label>
        <Textarea
          value={(data.query as string) || '{}'}
          onChange={(e) => onChange('query', e.target.value)}
          placeholder='{"age": {"$gt": 18}}'
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>限制数量（0表示不限制）</Label>
        <NumberInput
          value={(data.limit as number) || 0}
          onChange={(v) => onChange('limit', v)}
          defaultValue={0}
          min={0}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'mongodb_result'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="mongodb_result"
        />
      </div>
    </div>
  )
}

// MongoDB插入配置
export function MongoDBInsertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>集合名称</Label>
        <VariableInput
          value={(data.collection as string) || ''}
          onChange={(v) => onChange('collection', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>文档数据（JSON格式）</Label>
        <Textarea
          value={(data.document as string) || '{}'}
          onChange={(e) => onChange('document', e.target.value)}
          placeholder='{"name": "张三", "age": 25}'
          rows={6}
        />
      </div>
    </div>
  )
}

// MongoDB更新配置
export function MongoDBUpdateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>集合名称</Label>
        <VariableInput
          value={(data.collection as string) || ''}
          onChange={(v) => onChange('collection', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>查询条件（JSON格式）</Label>
        <Textarea
          value={(data.query as string) || '{}'}
          onChange={(e) => onChange('query', e.target.value)}
          placeholder='{"name": "张三"}'
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <Label>更新内容（JSON格式）</Label>
        <Textarea
          value={(data.update as string) || '{}'}
          onChange={(e) => onChange('update', e.target.value)}
          placeholder='{"$set": {"age": 26}}'
          rows={4}
        />
      </div>
    </div>
  )
}

// MongoDB删除配置
export function MongoDBDeleteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>集合名称</Label>
        <VariableInput
          value={(data.collection as string) || ''}
          onChange={(v) => onChange('collection', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>删除条件（JSON格式）</Label>
        <Textarea
          value={(data.query as string) || '{}'}
          onChange={(e) => onChange('query', e.target.value)}
          placeholder='{"age": {"$lt": 18}}'
          rows={4}
        />
      </div>
    </div>
  )
}

// SQL Server连接配置
export function SQLServerConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || 'localhost'}
            onChange={(v) => onChange('host', v)}
            placeholder="localhost"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 1433}
            onChange={(v) => onChange('port', v)}
            defaultValue={1433}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>数据库名</Label>
        <VariableInput
          value={(data.database as string) || ''}
          onChange={(v) => onChange('database', v)}
          placeholder="master"
        />
      </div>

      <div className="space-y-2">
        <Label>用户名</Label>
        <VariableInput
          value={(data.username as string) || ''}
          onChange={(v) => onChange('username', v)}
          placeholder="sa"
        />
      </div>

      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="请输入密码"
        />
      </div>

      <div className="space-y-2">
        <Label>驱动名称</Label>
        <VariableInput
          value={(data.driver as string) || 'ODBC Driver 17 for SQL Server'}
          onChange={(v) => onChange('driver', v)}
          placeholder="ODBC Driver 17 for SQL Server"
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>
    </div>
  )
}

// SQL Server查询配置
export function SQLServerQueryConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL查询语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="SELECT * FROM table_name"
          rows={6}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'sqlserver_result'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="sqlserver_result"
        />
      </div>
    </div>
  )
}

// SQL Server执行配置
export function SQLServerExecuteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL执行语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="INSERT INTO table_name (col1, col2) VALUES ('val1', 'val2')"
          rows={6}
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          checked={(data.autoCommit as boolean) ?? true}
          onCheckedChange={(v) => onChange('autoCommit', v)}
        />
        <Label>自动提交事务</Label>
      </div>
    </div>
  )
}

// SQLite连接配置
export function SQLiteConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>数据库文件路径</Label>
        <PathInput
          value={(data.databasePath as string) || ''}
          onChange={(v) => onChange('databasePath', v)}
          type="file"
          title="选择数据库文件"
          fileTypes={[['SQLite 数据库', '*.db;*.sqlite;*.sqlite3'], ['所有文件', '*.*']]}
          placeholder="C:/data/mydb.db"
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>
    </div>
  )
}

// SQLite查询配置
export function SQLiteQueryConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL查询语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="SELECT * FROM table_name"
          rows={6}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'sqlite_result'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="sqlite_result"
        />
      </div>
    </div>
  )
}

// SQLite执行配置
export function SQLiteExecuteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>SQL执行语句</Label>
        <Textarea
          value={(data.sql as string) || ''}
          onChange={(e) => onChange('sql', e.target.value)}
          placeholder="INSERT INTO table_name (col1, col2) VALUES ('val1', 'val2')"
          rows={6}
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          checked={(data.autoCommit as boolean) ?? true}
          onCheckedChange={(v) => onChange('autoCommit', v)}
        />
        <Label>自动提交事务</Label>
      </div>
    </div>
  )
}

// Redis连接配置
export function RedisConnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || 'localhost'}
            onChange={(v) => onChange('host', v)}
            placeholder="localhost"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 6379}
            onChange={(v) => onChange('port', v)}
            defaultValue={6379}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>密码（可选）</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="留空表示无需认证"
        />
      </div>

      <div className="space-y-2">
        <Label>数据库编号</Label>
        <NumberInput
          value={(data.db as number) || 0}
          onChange={(v) => onChange('db', v)}
          defaultValue={0}
          min={0}
          max={15}
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>
    </div>
  )
}

// Redis GET配置
export function RedisGetConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>键名</Label>
        <VariableInput
          value={(data.key as string) || ''}
          onChange={(v) => onChange('key', v)}
          placeholder="mykey"
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'redis_value'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="redis_value"
        />
      </div>
    </div>
  )
}

// Redis SET配置
export function RedisSetConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>键名</Label>
        <VariableInput
          value={(data.key as string) || ''}
          onChange={(v) => onChange('key', v)}
          placeholder="mykey"
        />
      </div>

      <div className="space-y-2">
        <Label>值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="myvalue"
        />
      </div>

      <div className="space-y-2">
        <Label>过期时间（秒，0表示不过期）</Label>
        <NumberInput
          value={(data.expire as number) || 0}
          onChange={(v) => onChange('expire', v)}
          defaultValue={0}
          min={0}
        />
      </div>
    </div>
  )
}

// Redis DEL配置
export function RedisDelConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>键名</Label>
        <VariableInput
          value={(data.key as string) || ''}
          onChange={(v) => onChange('key', v)}
          placeholder="mykey"
        />
      </div>
    </div>
  )
}

// Redis HGET配置
export function RedisHGetConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>哈希键名</Label>
        <VariableInput
          value={(data.key as string) || ''}
          onChange={(v) => onChange('key', v)}
          placeholder="myhash"
        />
      </div>

      <div className="space-y-2">
        <Label>字段名</Label>
        <VariableInput
          value={(data.field as string) || ''}
          onChange={(v) => onChange('field', v)}
          placeholder="field1"
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'redis_hash_value'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="redis_hash_value"
        />
      </div>
    </div>
  )
}

// Redis HSET配置
export function RedisHSetConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>哈希键名</Label>
        <VariableInput
          value={(data.key as string) || ''}
          onChange={(v) => onChange('key', v)}
          placeholder="myhash"
        />
      </div>

      <div className="space-y-2">
        <Label>字段名</Label>
        <VariableInput
          value={(data.field as string) || ''}
          onChange={(v) => onChange('field', v)}
          placeholder="field1"
        />
      </div>

      <div className="space-y-2">
        <Label>值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="value1"
        />
      </div>
    </div>
  )
}

// Oracle插入配置
export function OracleInsertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"name": "张三", "age": 25}'
          rows={6}
        />
      </div>
    </div>
  )
}

// Oracle更新配置
export function OracleUpdateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>更新数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"age": 26}'
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// Oracle删除配置
export function OracleDeleteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// PostgreSQL插入配置
export function PostgreSQLInsertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"name": "张三", "age": 25}'
          rows={6}
        />
      </div>
    </div>
  )
}

// PostgreSQL更新配置
export function PostgreSQLUpdateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>更新数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"age": 26}'
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// PostgreSQL删除配置
export function PostgreSQLDeleteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// SQL Server插入配置
export function SQLServerInsertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"name": "张三", "age": 25}'
          rows={6}
        />
      </div>
    </div>
  )
}

// SQL Server更新配置
export function SQLServerUpdateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>更新数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"age": 26}'
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// SQL Server删除配置
export function SQLServerDeleteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// SQLite插入配置
export function SQLiteInsertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"name": "张三", "age": 25}'
          rows={6}
        />
      </div>
    </div>
  )
}

// SQLite更新配置
export function SQLiteUpdateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>更新数据（JSON格式）</Label>
        <Textarea
          value={(data.data as string) || '{}'}
          onChange={(e) => onChange('data', e.target.value)}
          placeholder='{"age": 26}'
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// SQLite删除配置
export function SQLiteDeleteConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>表名</Label>
        <VariableInput
          value={(data.tableName as string) || ''}
          onChange={(v) => onChange('tableName', v)}
          placeholder="users"
        />
      </div>

      <div className="space-y-2">
        <Label>WHERE条件</Label>
        <VariableInput
          value={(data.where as string) || ''}
          onChange={(v) => onChange('where', v)}
          placeholder="id = 1"
        />
      </div>
    </div>
  )
}

// ==================== 数据库断开连接配置 ====================

// Oracle断开连接配置
export function OracleDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'oracle_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="oracle_conn"
        />
      </div>
    </div>
  )
}

// PostgreSQL断开连接配置
export function PostgreSQLDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'postgresql_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="postgresql_conn"
        />
      </div>
    </div>
  )
}

// MongoDB断开连接配置
export function MongoDBDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'mongodb_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="mongodb_conn"
        />
      </div>
    </div>
  )
}

// SQL Server断开连接配置
export function SQLServerDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlserver_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlserver_conn"
        />
      </div>
    </div>
  )
}

// SQLite断开连接配置
export function SQLiteDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'sqlite_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="sqlite_conn"
        />
      </div>
    </div>
  )
}

// Redis断开连接配置
export function RedisDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'redis_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="redis_conn"
        />
      </div>
    </div>
  )
}
