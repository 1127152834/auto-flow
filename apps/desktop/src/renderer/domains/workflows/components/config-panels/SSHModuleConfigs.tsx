// Source: WebRPA@5ccb900e, components/workflow/config-panels/SSHModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { NumberInput } from '../controls/number-input'
import { Textarea } from '../controls/textarea'
import { PathInput } from '../controls/path-input'
import { useGlobalConfigStore } from '../../hooks/stores/globalConfigStore'
import { useEffect } from 'react'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// SSH连接配置
export function SSHConnectConfig({ data, onChange }: ConfigProps) {
  const { config } = useGlobalConfigStore()

  useEffect(() => {
    if (!data.host && config.ssh?.host) {
      onChange('host', config.ssh.host)
    }
    if (!data.port && config.ssh?.port) {
      onChange('port', config.ssh.port)
    }
    if (!data.username && config.ssh?.username) {
      onChange('username', config.ssh.username)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>主机地址</Label>
          <VariableInput
            value={(data.host as string) || ''}
            onChange={(v) => onChange('host', v)}
            placeholder="192.168.1.100"
          />
        </div>
        <div className="space-y-2">
          <Label>端口</Label>
          <NumberInput
            value={(data.port as number) || 22}
            onChange={(v) => onChange('port', v)}
            defaultValue={22}
            min={1}
            max={65535}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>用户名</Label>
        <VariableInput
          value={(data.username as string) || ''}
          onChange={(v) => onChange('username', v)}
          placeholder="root"
        />
      </div>

      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput
          value={(data.password as string) || ''}
          onChange={(v) => onChange('password', v)}
          placeholder="请输入密码（或使用密钥文件）"
        />
      </div>

      <div className="space-y-2">
        <Label>密钥文件路径（可选）</Label>
        <PathInput
          value={(data.keyFile as string) || ''}
          onChange={(v) => onChange('keyFile', v)}
          type="file"
          title="选择私钥文件"
          fileTypes={[['私钥文件', '*.pem;*.key;id_rsa;id_ed25519'], ['所有文件', '*.*']]}
          placeholder="C:/Users/user/.ssh/id_rsa"
        />
      </div>

      <div className="space-y-2">
        <Label>超时时间（秒）</Label>
        <NumberInput
          value={(data.timeout as number) || 30}
          onChange={(v) => onChange('timeout', v)}
          defaultValue={30}
          min={1}
          max={300}
        />
      </div>

      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'ssh_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="ssh_conn"
        />
      </div>
    </div>
  )
}

// SSH执行命令配置
export function SSHExecuteCommandConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'ssh_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="ssh_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>命令</Label>
        <Textarea
          value={(data.command as string) || ''}
          onChange={(e) => onChange('command', e.target.value)}
          placeholder="ls -la"
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>输出变量名</Label>
        <VariableNameInput
          value={(data.outputVariable as string) || 'ssh_output'}
          onChange={(v) => onChange('outputVariable', v)}
          placeholder="ssh_output"
        />
      </div>

      <div className="space-y-2">
        <Label>错误变量名</Label>
        <VariableNameInput
          value={(data.errorVariable as string) || 'ssh_error'}
          onChange={(v) => onChange('errorVariable', v)}
          placeholder="ssh_error"
        />
      </div>

      <div className="space-y-2">
        <Label>退出码变量名</Label>
        <VariableNameInput
          value={(data.exitCodeVariable as string) || 'ssh_exit_code'}
          onChange={(v) => onChange('exitCodeVariable', v)}
          placeholder="ssh_exit_code"
        />
      </div>

      <div className="space-y-2">
        <Label>超时时间（秒）</Label>
        <NumberInput
          value={(data.timeout as number) || 30}
          onChange={(v) => onChange('timeout', v)}
          defaultValue={30}
          min={1}
          max={300}
        />
      </div>
    </div>
  )
}

// SSH上传文件配置
export function SSHUploadFileConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'ssh_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="ssh_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>本地文件路径</Label>
        <PathInput
          type="file"
          value={(data.localPath as string) || ''}
          onChange={(v) => onChange('localPath', v)}
          placeholder="C:/data/file.txt"
        />
      </div>

      <div className="space-y-2">
        <Label>远程文件路径</Label>
        <VariableInput
          value={(data.remotePath as string) || ''}
          onChange={(v) => onChange('remotePath', v)}
          placeholder="/home/user/file.txt"
        />
      </div>
    </div>
  )
}

// SSH下载文件配置
export function SSHDownloadFileConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'ssh_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="ssh_conn"
        />
      </div>

      <div className="space-y-2">
        <Label>远程文件路径</Label>
        <VariableInput
          value={(data.remotePath as string) || ''}
          onChange={(v) => onChange('remotePath', v)}
          placeholder="/home/user/file.txt"
        />
      </div>

      <div className="space-y-2">
        <Label>本地文件路径</Label>
        <PathInput
          type="file"
          value={(data.localPath as string) || ''}
          onChange={(v) => onChange('localPath', v)}
          placeholder="C:/data/file.txt"
        />
      </div>
    </div>
  )
}

// SSH断开连接配置
export function SSHDisconnectConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>连接名称</Label>
        <VariableInput
          value={(data.connectionName as string) || 'ssh_conn'}
          onChange={(v) => onChange('connectionName', v)}
          placeholder="ssh_conn"
        />
      </div>
    </div>
  )
}
