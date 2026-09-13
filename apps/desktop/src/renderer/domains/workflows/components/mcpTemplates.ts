// Source: WebRPA@5ccb900e, components/workflow/mcpTemplates.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 推荐 MCP 服务器模板
 *
 * 设计原则：
 * - 仅做"一键预填"，不会自动启用、不会自动连接
 * - 用户必须手动确认表单内容（路径/Key/Token）才能保存
 * - 内置的能力都是 WebRPA 471 个模块覆盖不到、又有官方维护的 MCP server
 */

export interface MCPTemplate {
  id: string
  name: string                    // 默认填入服务器名
  title: string                   // 列表显示名
  description: string             // 一句话说明用途
  icon: string                    // emoji（仅模板列表内部使用）
  category: 'file' | 'dev' | 'web' | 'data' | 'ai'
  recommended?: boolean           // 是否高亮推荐
  needsConfig: string[]           // 哪些字段需要用户填（仅提示）
  homepage?: string               // 文档/源码地址

  // 配置预填
  transport: 'stdio' | 'sse' | 'http'
  command?: string
  args?: string[]                 // 数组中带 <PLACEHOLDER> 的需用户改
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  autoApprove?: string[]
}

export const MCP_TEMPLATES: MCPTemplate[] = [
  // ============ 文件 / 系统 ============
  {
    id: 'filesystem',
    name: 'filesystem',
    title: '文件系统',
    description: '让 AI 直接读写你指定目录下的文件、列出目录、搜索内容',
    icon: '📁',
    category: 'file',
    recommended: true,
    needsConfig: ['命令参数最后一项：要授权 AI 访问的根目录'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-filesystem', '<填入授权目录绝对路径，例如 D:\\Documents>'],
  },
  {
    id: 'git',
    name: 'git',
    title: 'Git 仓库',
    description: '让 AI 操作本地 Git 仓库（status / log / diff / 提交等）',
    icon: '🌿',
    category: 'dev',
    needsConfig: ['命令参数 --repository 后填仓库根目录'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/git',
    transport: 'stdio',
    command: 'uvx',
    args: ['mcp-server-git', '--repository', '<填入 Git 仓库绝对路径>'],
  },

  // ============ 开发工具 ============
  {
    id: 'github',
    name: 'github',
    title: 'GitHub',
    description: '操作 GitHub Issues / PR / 仓库搜索 / 代码读取',
    icon: '🐙',
    category: 'dev',
    recommended: true,
    needsConfig: ['环境变量 GITHUB_PERSONAL_ACCESS_TOKEN 填你的 PAT'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/github',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-github'],
    env: {
      GITHUB_PERSONAL_ACCESS_TOKEN: '<填入 GitHub Personal Access Token>',
    },
  },

  // ============ 数据库 ============
  {
    id: 'sqlite',
    name: 'sqlite',
    title: 'SQLite 数据库',
    description: '让 AI 直接查询 SQLite 数据库（自然语言转 SQL + 执行）',
    icon: '🗄️',
    category: 'data',
    needsConfig: ['命令参数 --db-path 填数据库文件路径'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite',
    transport: 'stdio',
    command: 'uvx',
    args: ['mcp-server-sqlite', '--db-path', '<填入 .db 文件绝对路径>'],
  },

  // ============ 网络 / 搜索 ============
  {
    id: 'fetch',
    name: 'fetch',
    title: '通用 HTTP 抓取',
    description: '让 AI 抓取任意网页内容（HTML 转 Markdown 友好格式）',
    icon: '🌐',
    category: 'web',
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/fetch',
    transport: 'stdio',
    command: 'uvx',
    args: ['mcp-server-fetch'],
    autoApprove: ['fetch'],
  },
  {
    id: 'brave-search',
    name: 'brave-search',
    title: 'Brave 搜索',
    description: '让 AI 用 Brave 搜索引擎联网搜索（隐私友好，独立索引）',
    icon: '🔍',
    category: 'web',
    needsConfig: ['环境变量 BRAVE_API_KEY 填 Brave API Key'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-brave-search'],
    env: {
      BRAVE_API_KEY: '<填入 Brave API Key, 在 https://api.search.brave.com 申请>',
    },
  },
  {
    id: 'tavily',
    name: 'tavily',
    title: 'Tavily 搜索（AI 友好）',
    description: '专为 AI 设计的搜索引擎，返回结构化精炼摘要而非原始网页',
    icon: '✨',
    category: 'web',
    recommended: true,
    needsConfig: ['环境变量 TAVILY_API_KEY 填 Tavily API Key'],
    homepage: 'https://github.com/tavily-ai/tavily-mcp',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', 'tavily-mcp@latest'],
    env: {
      TAVILY_API_KEY: '<填入 Tavily API Key, 在 https://tavily.com 注册免费 1000 次/月>',
    },
  },

  // ============ AI 增强 ============
  {
    id: 'sequential-thinking',
    name: 'sequential-thinking',
    title: '思维链增强',
    description: '让 AI 在做复杂任务前显式分步推理（适合搭建复杂工作流）',
    icon: '🧠',
    category: 'ai',
    recommended: true,
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-sequential-thinking'],
    autoApprove: ['sequentialthinking'],
  },
  {
    id: 'memory',
    name: 'memory',
    title: '知识图谱记忆',
    description: '让 AI 通过实体-关系图谱建立持久化的跨会话长期记忆',
    icon: '🧷',
    category: 'ai',
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/memory',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-memory'],
  },

  // ============ 测试 ============
  {
    id: 'everything',
    name: 'test-everything',
    title: '官方测试 server',
    description: '官方测试用 server，含 echo/add 等 13 个示例工具，仅用于验证 MCP 链路',
    icon: '🧪',
    category: 'ai',
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/everything',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-everything'],
  },

  // ============ 数据库（补充） ============
  {
    id: 'postgres',
    name: 'postgres',
    title: 'PostgreSQL 数据库',
    description: '让 AI 连接 PostgreSQL，进行只读查询与表结构检视',
    icon: '🐘',
    category: 'data',
    needsConfig: ['命令参数最后一项填数据库连接串 postgresql://user:pwd@host/db'],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/postgres',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-postgres', '<填入 postgresql://用户:密码@主机:5432/库名>'],
  },

  // ============ 网络 / 浏览器（补充） ============
  {
    id: 'puppeteer',
    name: 'puppeteer',
    title: '浏览器自动化(Puppeteer)',
    description: '让 AI 控制无头浏览器：打开页面、点击、填表、截图、执行 JS',
    icon: '🕹️',
    category: 'web',
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/puppeteer',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-puppeteer'],
  },

  // ============ AI 增强（补充） ============
  {
    id: 'time',
    name: 'time',
    title: '时间 / 时区',
    description: '让 AI 获取当前时间、做时区换算（避免模型对“现在”判断错误）',
    icon: '🕐',
    category: 'ai',
    needsConfig: [],
    homepage: 'https://github.com/modelcontextprotocol/servers/tree/main/src/time',
    transport: 'stdio',
    command: 'uvx',
    args: ['mcp-server-time'],
    autoApprove: ['get_current_time', 'convert_time'],
  },
]

export const TEMPLATE_CATEGORIES: Record<string, string> = {
  file: '文件 / 系统',
  dev: '开发',
  data: '数据库',
  web: '网络 / 搜索',
  ai: 'AI 增强',
}
